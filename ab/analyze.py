"""Analyse the prompt v2 experiment and apply its pre-registered decision rule.

Online results are read from the database and the simulator's intent file. Offline results
come from two saved eval runs on the same tasks. No decision is given before the planned
number of messages has been sent and each variant has its minimum.

Usage: uv run python -m ab.analyze
"""

import hashlib
import json
from pathlib import Path

import yaml

from ab.assign import assign, load_experiment
from app.config import PROJECT_ROOT, get_settings
from app.storage.db import create_database
from app.storage.repository import Repository
from evals.benchmark_retrieval import load_benchmark_config
from evals.report_header import report_header
from evals.stats import (
    bootstrap_ci,
    bootstrap_difference,
    mcnemar_exact,
    percentile,
    two_proportion_p,
    wilson_interval,
)

EXPERIMENT = PROJECT_ROOT / "experiments" / "prompt_v2.yaml"
RUN = "abv2"
RAW_ONLINE = PROJECT_ROOT / "reports" / "raw" / "ab_prompt_v2_online.json"
REPORT = PROJECT_ROOT / "reports" / "ab_prompt_v2.md"
ALPHA = 0.05


def expected_behaviour(intent: str, still_gaps: set[str]) -> str:
    """The pre-registered, crude label."""
    return "escalate" if intent in still_gaps else "answer"


def export_online(experiment: dict, still_gaps: set[str]) -> list[dict]:
    """Join stored turns to intents. Saved without message text, so the report can be rebuilt."""
    settings = get_settings()
    truth_file = PROJECT_ROOT / "data" / "sim" / f"{RUN}.jsonl"
    if not truth_file.exists():
        return []
    truth = {}
    for line in truth_file.read_text().splitlines():
        record = json.loads(line)
        truth[record["request_id"]] = record
    repository = Repository(create_database(settings.resolve(settings.database_path)))
    rows = []
    for turn in repository.turns("simulation"):
        record = truth.get(turn.request_id)
        if record is None:
            continue
        if turn.variant != assign(experiment, turn.user_id):
            raise SystemExit(f"{turn.request_id} was served by the wrong variant")
        rows.append(
            {
                "message_id": record["message_id"],
                "variant": turn.variant,
                "prompt_version": turn.prompt_version,
                "model": turn.model,
                "expected": expected_behaviour(record["intent"], still_gaps),
                "behavior": turn.behavior,
                "escalate": turn.escalate,
                "latency_ms": turn.latency_ms - (turn.llm_wait_ms or 0),
                "tokens": (turn.input_tokens or 0) + (turn.output_tokens or 0),
                "system_error": any(
                    e in ("llm_error", "retrieval_error") for e in turn.guardrail_events
                ),
            }
        )
    return sorted(rows, key=lambda r: r["message_id"])


def sample_ratio_chi_square(counts: dict[str, int], allocation: dict[str, float]) -> float:
    """How far the real split is from the planned one."""
    total = sum(counts.values())
    return sum(
        (counts[name] - total * share) ** 2 / (total * share) for name, share in allocation.items()
    )


def guardrail_breaches(control: dict, treatment: dict, limits: dict, with_latency: bool) -> list:
    """Names of the guardrails the treatment breaks. Inputs hold the summary numbers."""
    breaches = []
    if (
        treatment["escalation_rate"] - control["escalation_rate"]
        > limits["escalation_rate_max_increase"] + 1e-9
    ):
        breaches.append("escalation_rate")
    if with_latency and (
        treatment["latency_p95"] > control["latency_p95"] * limits["latency_p95_max_ratio"]
    ):
        breaches.append("latency_p95")
    if treatment["mean_tokens"] > control["mean_tokens"] * limits["mean_total_tokens_max_ratio"]:
        breaches.append("mean_total_tokens")
    return breaches


def effect(difference: float, p_value: float) -> str:
    """'better', 'worse' or 'unclear' for the treatment."""
    if p_value >= ALPHA or difference == 0:
        return "unclear"
    return "better" if difference > 0 else "worse"


def decide(offline: dict | None, online: dict | None) -> tuple[str, list[str]]:
    """The rule in the experiment file. Each input has 'effect', 'breaches', and offline
    also 'behaviour_difference'."""
    if offline is None or online is None:
        return "no decision yet", ["Offline and online results are both needed."]
    reasons = []
    for name, part in (("offline", offline), ("online", online)):
        reasons.append(f"{name} primary metric: {part['effect']}")
        reasons += [f"{name} guardrail broken: {b}" for b in part["breaches"]]
    parts = (offline, online)
    if any(p["effect"] == "worse" or p["breaches"] for p in parts):
        return "don't ship", reasons
    if any(p["effect"] == "better" for p in parts):
        if offline["behaviour_difference"] < 0:
            return "inconclusive", [*reasons, "offline behaviour accuracy went down"]
        return "ship", reasons
    return "inconclusive", reasons


def summarise(rows: list[dict]) -> dict:
    """Guardrail numbers for one arm."""
    return {
        "escalation_rate": sum(r["escalate"] for r in rows) / len(rows),
        "latency_p95": percentile([r["latency_ms"] for r in rows], 95),
        "mean_tokens": sum(r["tokens"] for r in rows) / len(rows),
    }


def rate(count: int, total: int) -> str:
    """'12/300 = 0.040 [0.023, 0.069]'."""
    low, high = wilson_interval(count, total)
    return f"{count}/{total} = {count / total:.3f} [{low:.3f}, {high:.3f}]"


def online_section(experiment: dict, rows: list[dict], boot: dict) -> tuple[list[str], dict | None]:
    """Report lines and the input for the decision (None until the sample is complete)."""
    plan = experiment["online"]
    arms = {name: [r for r in rows if r["variant"] == name] for name in experiment["variants"]}
    counts = {name: len(group) for name, group in arms.items()}
    lines = ["## Online: simulated traffic through the live API (phi4-mini)", ""]
    if len(rows) < plan["messages_sent"] or min(counts.values()) < plan["min_per_variant"]:
        lines.append(
            f"**Not complete: {len(rows)}/{plan['messages_sent']} messages. No results are "
            "shown before the planned sample is reached.**"
        )
        return lines, None
    errors = sum(r["system_error"] for r in rows)
    chi = sample_ratio_chi_square(counts, experiment["allocation"])
    ratio_ok = chi <= plan["sample_ratio_check"]["max_chi_square"]
    lines += [
        f"{len(rows)} messages, one per simulated user. Split: {counts}. Sample ratio "
        f"chi-square {chi:.2f}: {'passes' if ratio_ok else '**FAILS, experiment invalid**'}. "
        f"System errors: {errors}.",
        "",
        "| Metric | Control (v1) | Treatment (v2) |",
        "|---|---|---|",
    ]
    control, treatment = arms["control"], arms["treatment"]
    correct = {n: [r["behavior"] == r["expected"] for r in g] for n, g in arms.items()}
    lines.append(
        "| **Behaviour accuracy (primary)** | "
        + " | ".join(rate(sum(correct[n]), counts[n]) for n in ("control", "treatment"))
        + " |"
    )
    for label, keep in (
        ("Refusal rate (any refusal is wrong)", lambda r: r["behavior"] == "refuse"),
        ("Escalation rate", lambda r: r["escalate"]),
    ):
        cells = [rate(sum(map(keep, g)), len(g)) for g in (control, treatment)]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    summary = {name: summarise(group) for name, group in arms.items()}
    for label, key, unit in (
        ("Latency p95", "latency_p95", " ms"),
        ("Mean tokens per message", "mean_tokens", ""),
    ):
        cells = [f"{summary[n][key]:.0f}{unit}" for n in ("control", "treatment")]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    difference, low, high = bootstrap_difference(
        correct["control"], correct["treatment"], boot["resamples"], boot["seed"]
    )
    p_value = two_proportion_p(
        sum(correct["control"]), len(control), sum(correct["treatment"]), len(treatment)
    )
    breaches = guardrail_breaches(
        summary["control"], summary["treatment"], experiment["guardrails"], with_latency=True
    )
    lines += [
        "",
        f"- Behaviour accuracy, v2 minus v1: {difference:+.3f} [{low:+.3f}, {high:+.3f}], "
        f"two-proportion p = {p_value:.3f}.",
        f"- Guardrails broken: {', '.join(breaches) or 'none'}.",
    ]
    if not ratio_ok:
        return lines, None
    return lines, {"effect": effect(difference, p_value), "breaches": breaches}


def offline_rows(path: Path) -> list[dict]:
    """The graded rows of a saved eval run."""
    return json.loads(path.read_text())["rows"]


def offline_section(
    experiment: dict, first: Path, second: Path, boot: dict
) -> tuple[list[str], dict | None]:
    """Paired comparison on the tasks both runs graded. Needs every task graded."""
    lines = ["## Offline: paired comparison on eval set v2 (Groq)", ""]
    if not (first.exists() and second.exists()):
        lines.append("**Not run yet.**")
        return lines, None
    saved = [json.loads(p.read_text()) for p in (first, second)]
    a, b = ({r["id"]: r for r in run["rows"]} for run in saved)
    total = saved[0]["meta"]["task_count"]
    ids = [i for i in a if i in b and a[i]["passed"] is not None and b[i]["passed"] is not None]
    if len(ids) < total:
        lines.append(f"**Not complete: {len(ids)}/{total} tasks graded under both prompts.**")
        return lines, None
    lines += [
        "| Tasks | n | Pass rate v1 | Pass rate v2 | v2 minus v1 [95% paired bootstrap] | "
        "Only v1 passed | Only v2 passed | McNemar p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    results = {}
    groups = {
        "All": ids,
        "From eval v1": [i for i in ids if i.startswith("v1-")],
        "Mined": [i for i in ids if not i.startswith("v1-")],
    }
    for label, chosen in groups.items():
        for metric, key in (
            ("pass", lambda r: bool(r["passed"])),
            ("behaviour", lambda r: bool(r["checks"]["behaviour_correct"])),
        ):
            if metric == "behaviour" and label != "All":
                continue
            va, vb = [key(a[i]) for i in chosen], [key(b[i]) for i in chosen]
            diffs = [int(y) - int(x) for x, y in zip(va, vb, strict=True)]
            low, high = bootstrap_ci(diffs, boot["resamples"], boot["seed"])
            only_a = sum(x and not y for x, y in zip(va, vb, strict=True))
            only_b = sum(y and not x for x, y in zip(va, vb, strict=True))
            p_value = mcnemar_exact(only_a, only_b)
            difference = sum(diffs) / len(diffs)
            name = label if metric == "pass" else "All, behaviour accuracy instead"
            lines.append(
                f"| {name} | {len(chosen)} | {sum(va) / len(va):.3f} | {sum(vb) / len(vb):.3f} "
                f"| {difference:+.3f} [{low:+.3f}, {high:+.3f}] | {only_a} | {only_b} "
                f"| {p_value:.4f} |"
            )
            if label == "All":
                results[metric] = (difference, p_value)

    def arm(rows: dict) -> dict:
        used = [rows[i] for i in ids]
        tokens = [
            (r["input_tokens"] or 0) + (r["output_tokens"] or 0)
            for r in used
            if r["input_tokens"] is not None
        ]
        return {
            "escalation_rate": sum(r["escalate_flag"] for r in used) / len(used),
            "mean_tokens": sum(tokens) / len(tokens),
        }

    arms = (arm(a), arm(b))
    breaches = guardrail_breaches(*arms, experiment["guardrails"], with_latency=False)
    for label, key in (("Escalation rate", "escalation_rate"), ("Mean tokens", "mean_tokens")):
        lines.append("")
        lines.append(f"- {label}: v1 {arms[0][key]:.3f}, v2 {arms[1][key]:.3f}.")
    lines += ["", f"- Guardrails broken: {', '.join(breaches) or 'none'}."]
    return lines, {
        "effect": effect(*results["pass"]),
        "breaches": breaches,
        "behaviour_difference": results["behaviour"][0],
    }


def main() -> None:
    """Build the report."""
    experiment = load_experiment(EXPERIMENT)
    settings = get_settings()
    boot = load_benchmark_config()["bootstrap"]
    gaps = yaml.safe_load((PROJECT_ROOT / "loop" / "cycle1" / "gaps.yaml").read_text())
    rows = export_online(experiment, set(gaps["still_gaps"]))
    if rows:
        RAW_ONLINE.write_text(json.dumps(rows, indent=1) + "\n")
    elif RAW_ONLINE.exists():
        rows = json.loads(RAW_ONLINE.read_text())
    raw = PROJECT_ROOT / "reports" / "raw"
    name = "groq-openai-gpt-oss-20b_prompt"
    offline_lines, offline = offline_section(
        experiment, raw / f"eval_v2_{name}-v1.json", raw / f"eval_v2_{name}-v2.json", boot
    )
    online_lines, online = online_section(experiment, rows, boot)
    decision, reasons = decide(offline, online)
    notes = (PROJECT_ROOT / "experiments" / "prompt_v2_notes.md").read_text().strip()
    lines = [
        report_header(
            "A/B test: prompt v1 against prompt v2",
            settings,
            eval_set="evals/sets/v2.jsonl and the Banking77 A/B pool",
            models={
                "Offline generator": settings.groq_generator_model,
                "Online generator": f"ollama:{settings.ollama_model}",
                "Experiment file SHA-256": hashlib.sha256(EXPERIMENT.read_bytes()).hexdigest(),
            },
            judge_used=True,
        ),
        "",
        f"## Decision: **{decision}**",
        "",
        *[f"- {r}" for r in reasons],
        "",
        "Decision rule applied by code (`ab/analyze.py`). Decisions and notes are by Claude "
        "Code, **not reviewed by a human**. The offline pass rate depends on a judge that is "
        "not validated.",
        "",
        notes,
        "",
        *offline_lines,
        "",
        *online_lines,
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Decision: {decision}. Wrote {REPORT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
