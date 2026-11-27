"""Data loop cycle 1 report: what mining found, and before/after the new articles.

Reads saved eval and holdout results. Scoring the planted gaps needs the simulator's
intent file; that happens here, after labelling, never during mining.

Usage: uv run python -m loop.report
"""

import json
import re
from collections import Counter
from collections.abc import Callable

import yaml

from app.config import PROJECT_ROOT, get_settings
from evals.benchmark_retrieval import load_benchmark_config
from evals.report_header import report_header
from evals.stats import bootstrap_ci, mcnemar_exact
from loop.review import read_lines

FOLDER = PROJECT_ROOT / "loop" / "cycle1"
RAW = PROJECT_ROOT / "reports" / "raw"
SCORE = RAW / "loop_cycle1_gap_score.json"
REPORT = PROJECT_ROOT / "reports" / "data_loop_cycle_1.md"
EVAL = "eval_v2_groq-openai-gpt-oss-20b_prompt-v1"


def planted_gaps() -> set[str]:
    """The 10 intents originally left without an article (from the coverage table)."""
    text = (PROJECT_ROOT / "data" / "kb" / "COVERAGE.md").read_text()
    table = text.split("## Planted gaps")[1].split("## All intents")[0]
    return set(re.findall(r"^\| `([a-z_]+)` \|", table, re.MULTILINE))


def score_gaps(queue: list[dict], reviews: dict[str, dict], truth: dict[str, str]) -> dict:
    """How many planted gaps mining and labelling found, and what else was called a gap."""
    planted = planted_gaps()
    intents = {
        item["item_id"]: {
            truth[r] for r in [item["request_id"], *item["duplicate_request_ids"]] if r in truth
        }
        for item in queue
    }
    in_queue = set().union(*intents.values()) & planted
    flagged = [i for i, r in reviews.items() if r.get("cause") == "needs_new_article"]
    found = set().union(set(), *(intents[i] for i in flagged)) & planted
    return {
        "planted": len(planted),
        "planted_in_mined_traffic": sorted(set(truth.values()) & planted),
        "planted_in_queue": sorted(in_queue),
        "planted_labelled_new_article": sorted(found),
        "new_article_items": len(flagged),
        "new_article_items_not_planted": sum(not intents[i] & planted for i in flagged),
    }


def p_text(p_value: float) -> str:
    """Three decimals, never a misleading 0.000."""
    return "<0.001" if p_value < 0.001 else f"{p_value:.3f}"


def paired(before: list[bool], after: list[bool], boot: dict) -> str:
    """Table cells: before, after, change with a paired bootstrap interval, McNemar."""
    n = len(before)
    diffs = [int(a) - int(b) for b, a in zip(before, after, strict=True)]
    low, high = bootstrap_ci(diffs, boot["resamples"], boot["seed"])
    gained = sum(d == 1 for d in diffs)
    lost = sum(d == -1 for d in diffs)
    return (
        f"{sum(before)}/{n} = {sum(before) / n:.3f} | {sum(after)}/{n} = {sum(after) / n:.3f} "
        f"| {sum(diffs) / n:+.3f} [{low:+.3f}, {high:+.3f}] | {gained} / {lost} "
        f"| {p_text(mcnemar_exact(lost, gained))}"
    )


HEAD = [
    "| Tasks | Measure | Before | After | Change [95% paired bootstrap] | Gained / lost "
    "| McNemar p |",
    "|---|---|---|---|---|---|---|",
]


def comparison(
    before: dict, after: dict, groups: dict[str, list[str]], measures: dict[str, Callable], boot
) -> list[str]:
    """One row per group and measure."""
    lines = list(HEAD)
    for group, ids in groups.items():
        for name, measure in measures.items():
            cells = paired(
                [measure(before[i]) for i in ids], [measure(after[i]) for i in ids], boot
            )
            lines.append(f"| {group} ({len(ids)}) | {name} | {cells} |")
    return lines


def load_run(suffix: str) -> dict:
    """A saved eval run as id -> row. Every task must be graded."""
    saved = json.loads((RAW / f"{EVAL}{suffix}.json").read_text())
    rows = {r["id"]: r for r in saved["rows"]}
    if len(rows) != saved["meta"]["task_count"] or any(r["passed"] is None for r in rows.values()):
        raise SystemExit(f"{EVAL}{suffix} is incomplete")
    return rows


def resolved(row: dict) -> bool:
    """Answered without a hand-off, and judged faithful."""
    return row["behavior"] == "answer" and not row["escalate"] and row["faithful"] is True


def main() -> None:
    """Build the report."""
    settings = get_settings()
    boot = load_benchmark_config()["bootstrap"]
    queue = read_lines(FOLDER / "queue.jsonl")
    reviews = {r["item_id"]: r for r in read_lines(FOLDER / "reviews.jsonl")}
    mining = json.loads((FOLDER / "mining_summary.json").read_text())
    truth_file = PROJECT_ROOT / "data" / "sim" / "sim1.jsonl"
    if truth_file.exists():
        truth = {r["request_id"]: r["intent"] for r in read_lines(truth_file)}
        SCORE.write_text(json.dumps(score_gaps(queue, reviews, truth), indent=2) + "\n")
    score = json.loads(SCORE.read_text())
    gaps = yaml.safe_load((FOLDER / "gaps.yaml").read_text())

    before, after = load_run("_kb-before"), load_run("")
    tasks = read_lines(PROJECT_ROOT / "evals" / "sets" / "v2.jsonl")
    changed = [t["id"] for t in tasks if "changed_from_v1" in t.get("provenance", {})]
    mined = [i for i in after if i.startswith("v2-")]
    unchanged = [i for i in after if i not in changed and i not in mined]
    measures = {
        "pass": lambda r: bool(r["passed"]),
        "right behaviour": lambda r: bool(r["checks"]["behaviour_correct"]),
    }
    eval_lines = comparison(
        before,
        after,
        {
            "Mined failures": mined,
            "Eval v1 tasks whose gap was filled": changed,
            "All other eval v1 tasks (harm check)": unchanged,
            "All of eval v2": list(after),
        },
        measures,
        boot,
    )
    lost = [i for i in unchanged if before[i]["passed"] and not after[i]["passed"]]

    hold = {
        side: {r["id"]: r for r in json.loads((RAW / f"holdout_cycle1_{side}.json").read_text())}
        for side in ("before", "after")
    }
    ids = {
        group: [i for i, r in hold["after"].items() if r["group"] == group]
        for group in ("filled", "other")
    }
    hold_lines = comparison(
        hold["before"],
        hold["after"],
        {"Never mined, filled topics": ids["filled"], "Never mined, other topics": ids["other"]},
        {
            "resolved": resolved,
            "answered, no hand-off": lambda r: r["behavior"] == "answer" and not r["escalate"],
            "shown text judged unfaithful": lambda r: r["faithful"] is False,
        },
        boot,
    )
    new_ids = set(gaps["new_articles"].values())
    cites_new = sum(bool(new_ids & set(hold["after"][i]["cited"])) for i in ids["filled"])

    verdicts = Counter(r["verdict"] for r in reviews.values())
    causes = Counter(r["cause"] for r in reviews.values() if r["verdict"] == "failure")
    notes = (FOLDER / "report_notes.md").read_text().strip()
    lines = [
        report_header(
            "Data loop, cycle 1: from logged failures to new articles",
            settings,
            eval_set="evals/sets/v2.jsonl and the Banking77 loop holdout pool",
            models={"Generator LLM": settings.groq_generator_model},
            judge_used=True,
        ),
        "",
        "**All 49 queue labels, the 8 new articles and every reference answer are by Claude "
        "Code. No person has reviewed them.** The judge is not validated.",
        "",
        notes,
        "",
        "## Mining",
        "",
        f"{mining['turns_mined']} stored turns (simulated traffic answered by llama3.2:3b in "
        f"Phase 2) gave {mining['candidates']} candidates, {mining['queue_items']} queue items "
        f"after merging duplicates, in {mining['clusters']} groups. Signals (a turn can have "
        f"several): {mining['signals']}.",
        "",
        f"Labels: {dict(verdicts)}. Causes of the confirmed failures: {dict(causes)}.",
        "",
        "## Planted gaps (scored afterwards)",
        "",
        f"- Planted gaps present in the mined traffic: {len(score['planted_in_mined_traffic'])} "
        f"of {score['planted']}.",
        f"- With at least one message in the queue: {len(score['planted_in_queue'])}.",
        f"- Labelled 'needs new article': {len(score['planted_labelled_new_article'])} "
        f"({', '.join(score['planted_labelled_new_article'])}).",
        f"- 'Needs new article' items that were not a planted gap: "
        f"{score['new_article_items_not_planted']} of {score['new_article_items']}.",
        "- **Not an independent test of labelling:** the labeller had read the list of "
        "planted gaps in the project files before labelling. The mining code reads only the "
        "database.",
        "",
        "## Before and after on eval set v2",
        "",
        "Same code, prompt v1 and models; only the knowledge base differs. 'Before' is scored "
        "against the v2 labels, so tasks that now expect an answer are bound to look bad "
        "before. The mined rows show whether the fix works on the questions it was made for, "
        "**not** how well it generalises.",
        "",
        *eval_lines,
        "",
        f"Other eval v1 tasks that passed before and fail after: {len(lost)}"
        + (f" ({', '.join(f'`{i}`' for i in lost)})." if lost else "."),
        "",
        "## Never-mined messages",
        "",
        f"{len(ids['filled'])} holdout messages on the filled topics and {len(ids['other'])} "
        "random ones from other topics. 'Resolved' means answered without hand-off and judged "
        "faithful. It does not show that the answer solves the problem.",
        "",
        *hold_lines,
        "",
        f"After the fix, {cites_new}/{len(ids['filled'])} filled-topic replies cite one of the "
        "new articles.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
