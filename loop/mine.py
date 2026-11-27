"""Find failure candidates in the stored turns and write the review queue.

Reads ONLY the database. It must never read data/sim/ (intent labels) or
data/kb/COVERAGE.md (the planted gaps): mining has to find problems from what the app saw.

Signals: escalation, weak search, out-of-scope refusal (possibly a wrong refusal), judge
flagged as unfaithful, a blocked output (including blocked fee claims), system error and
thumbs down. Redacting personal data is not a signal. Stored replies made before the claim
check existed are re-checked here and get a 'fee_claim' signal.

Near-identical messages are merged, the rest are grouped by meaning, and groups are ranked
by how many turns they cover.

Usage: uv run python -m loop.mine
"""

import json
from collections import Counter

import numpy as np
import yaml

from app.config import PROJECT_ROOT, get_settings
from app.guardrails.claims import Fact, claim_problems, load_facts
from app.guardrails.output import parse_bot_answer
from app.rag.models import build_embedder
from app.storage.db import FailureSignal, Turn, create_database
from app.storage.repository import Repository


def load_loop_config() -> dict:
    """config/loop.yaml."""
    return yaml.safe_load((PROJECT_ROOT / "config" / "loop.yaml").read_text())


def signal_names(
    turn: Turn, stored: list[FailureSignal], facts: dict[str, list[Fact]]
) -> list[str]:
    """Why this turn is a candidate. An empty list means it is not."""
    names = set()
    for item in stored:
        if item.signal != "guardrail":
            names.add(item.signal)
        elif item.detail == "out_of_scope":
            names.add("out_of_scope_refusal")
        elif item.detail == "output_check:fee_claim_mismatch":
            names.add("fee_claim")
        elif item.detail.startswith("output_check:"):
            names.add("blocked_output")
    reply = parse_bot_answer(turn.model_reply or "")
    if reply and reply.behavior != "refuse":
        cited = [a for a in reply.cited_article_ids if a in turn.context]
        if claim_problems(reply.answer, cited, facts):
            names.add("fee_claim")
    return sorted(names)


def merge_duplicates(similarity: np.ndarray, threshold: float) -> list[list[int]]:
    """Each item joins the first earlier group whose first member is nearly identical."""
    groups: list[list[int]] = []
    for index in range(len(similarity)):
        for group in groups:
            if similarity[index, group[0]] >= threshold:
                group.append(index)
                break
        else:
            groups.append([index])
    return groups


Clusters = list[list[list[int]]]  # clusters of duplicate groups of item indexes


def cluster(similarity: np.ndarray, groups: list[list[int]], threshold: float) -> Clusters:
    """Average-linkage clustering of duplicate groups, stopping below the threshold."""
    clusters = [[group] for group in groups]
    while len(clusters) > 1:
        best, pair = threshold, None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                left = [g[0] for g in clusters[i]]
                right = [g[0] for g in clusters[j]]
                score = float(similarity[np.ix_(left, right)].mean())
                if score >= best:
                    best, pair = score, (i, j)
        if pair is None:
            return clusters
        clusters[pair[0]] += clusters.pop(pair[1])
    return clusters


def build_queue(candidates: list[dict], vectors: np.ndarray, config: dict) -> list[dict]:
    """Queue items, largest group first. Each item is one question (duplicates merged)."""
    unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    similarity = unit @ unit.T
    groups = merge_duplicates(similarity, config["duplicate_similarity"])
    clusters = cluster(similarity, groups, config["cluster_similarity"])
    clusters.sort(
        key=lambda c: (-sum(len(g) for g in c), min(candidates[g[0]]["request_id"] for g in c))
    )
    queue = []
    for number, members in enumerate(clusters, start=1):
        turns = sum(len(g) for g in members)
        signals = Counter(s for g in members for i in g for s in candidates[i]["signals"])
        for group in members:
            first = candidates[group[0]]
            queue.append(
                {
                    "item_id": f"c{config['cycle']}-{len(queue) + 1:03d}",
                    "cluster": number,
                    "cluster_turns": turns,
                    "cluster_signals": dict(sorted(signals.items())),
                    "duplicate_request_ids": [candidates[i]["request_id"] for i in group[1:]],
                    **first,
                }
            )
    return queue


def main() -> None:
    """Mine the database and write loop/cycle<N>/queue.jsonl."""
    settings, config = get_settings(), load_loop_config()
    output = PROJECT_ROOT / "loop" / f"cycle{config['cycle']}" / "queue.jsonl"
    if output.exists():
        raise SystemExit(f"{output.name} exists; reviews refer to it. Start a new cycle.")
    repository = Repository(create_database(settings.resolve(settings.database_path)))
    facts = load_facts(settings.resolve(settings.money_facts_path))
    by_turn: dict[str, list[FailureSignal]] = {}
    for item in repository.signals():
        by_turn.setdefault(item.request_id, []).append(item)
    turns = repository.turns(config["source"])
    candidates = []
    for turn in turns:
        names = signal_names(turn, by_turn.get(turn.request_id, []), facts)
        if names:
            reply = parse_bot_answer(turn.model_reply or "")
            candidates.append(
                {
                    "request_id": turn.request_id,
                    "message": turn.redacted_message,
                    "signals": names,
                    "behavior": turn.behavior,
                    "answer": turn.answer,
                    "model_reply": reply.answer if reply else None,
                    "cited": turn.cited_article_ids,
                    "retrieved_articles": list(turn.context),
                    "top_score": turn.top_score,
                    "model": f"{turn.provider}:{turn.model}",
                }
            )
    if not candidates:
        raise SystemExit("No failure candidates found.")
    embedder = build_embedder(settings.embedding_model, "cpu")
    vectors = np.asarray(embedder.embed_documents([c["message"] for c in candidates]))
    queue = build_queue(candidates, vectors, config)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in queue))
    summary = {
        "turns_mined": len(turns),
        "candidates": len(candidates),
        "queue_items": len(queue),
        "clusters": queue[-1]["cluster"],
        "signals": dict(sorted(Counter(s for c in candidates for s in c["signals"]).items())),
    }
    (output.parent / "mining_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
