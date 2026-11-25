"""Summarise the production signals stored in the database. Calls no model.

It never reads the simulator's ground-truth file: only what a real service would know.

Usage: uv run python -m evals.traffic_report --source simulation
"""

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, Settings, get_settings
from app.storage.db import FailureSignal, LiveJudgment, Turn, create_database
from app.storage.repository import Repository
from evals.benchmark_retrieval import load_benchmark_config
from evals.eval_report import Rates
from evals.report_header import report_header


def build_report(repository: Repository, settings: Settings, source: str, rates: Rates) -> str:
    """The report text for one traffic source."""
    turns: Sequence[Turn] = repository.turns(source)
    if not turns:
        raise SystemExit(f"No stored turns with source '{source}'.")
    ids = {turn.request_id for turn in turns}
    signals: list[FailureSignal] = [s for s in repository.signals() if s.request_id in ids]
    with Session(repository.engine) as session:
        judgments = [j for j in session.scalars(select(LiveJudgment)).all() if j.request_id in ids]
    rows = [{"turn": t} for t in turns]

    def values(key: str) -> list[str]:
        return sorted({str(getattr(t, key)) for t in turns})

    flagged = {s.request_id for s in signals}
    latencies = [t.latency_ms for t in turns if t.llm_latency_ms is not None]
    tokens = [t.input_tokens + t.output_tokens for t in turns if t.input_tokens is not None]
    lines = [
        report_header(
            f"Production signals: '{source}' traffic",
            settings,
            eval_set="none (stored traffic; no labels are used)",
            models={
                "Generator LLM": ", ".join(
                    f"{t}" for t in sorted({f"{x.provider}:{x.model}" for x in turns})
                ),
                "Variant": ", ".join(values("variant")),
                "Knowledge base fingerprint": ", ".join(values("kb_fingerprint")),
                "Traffic recorded": f"{min(t.created_at for t in turns):%Y-%m-%d %H:%M} to "
                f"{max(t.created_at for t in turns):%Y-%m-%d %H:%M} UTC",
            },
            judge_used=bool(judgments),
            overrides={"Prompt version": ", ".join(values("prompt_version"))},
        ),
        "These are signals, not accuracy: nothing here says whether a reply was right.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Turns | {len(turns)} from {len({t.user_id for t in turns})} users |",
        *[
            f"| Replies: {name} | "
            f"{rates.share(rows, lambda r, n=name: r['turn'].behavior == n, lambda r: True)} |"
            for name in ("answer", "escalate", "refuse")
        ],
        f"| Flagged for a human (escalation rate) | "
        f"{rates.share(rows, lambda r: r['turn'].escalate, lambda r: True)} |",
        f"| Turns with at least one failure signal | "
        f"{rates.share(rows, lambda r: r['turn'].request_id in flagged, lambda r: True)} |",
        f"| Latency p50 | {rates.percentile(latencies, 50, 'ms')} |",
        f"| Latency p95 | {rates.percentile(latencies, 95, 'ms')} |",
        f"| Tokens per reply, mean | {rates.mean(tokens)} |",
        "",
        "## Failure signals",
        "",
        "One turn can have several.",
        "",
        "| Signal | Turns |",
        "|---|---|",
    ]
    per_signal = Counter(name for name, _ in {(s.signal, s.request_id) for s in signals})
    lines += [f"| {name} | {count} |" for name, count in sorted(per_signal.items())]
    guardrails = Counter(event for t in turns for event in t.guardrail_events)
    lines += ["", "## Guardrail events", "", "| Event | Count |", "|---|---|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(guardrails.items())] or [
        "| none | 0 |"
    ]
    lines += ["", "## LLM judge on a sample of live replies", ""]
    if judgments:
        judged = [{"ok": j.faithful} for j in judgments]
        judges = ", ".join(sorted({j.judge_model for j in judgments}))
        rubrics = ", ".join(sorted({j.rubric_version for j in judgments}))
        lines += [
            f"Sample rate {settings.judge_live_sample_rate:.0%} of replies with model text, "
            f"chosen by request ID. Judge: {judges}, rubric {rubrics}. "
            "**The judge has not yet been validated against a person.**",
            "",
            f"- Judged faithful: {rates.share(judged, lambda r: r['ok'], lambda r: True)}",
            "",
            "Replies judged unfaithful (judge's reason):",
            "",
            *[
                f"- `{j.request_id[:8]}` {j.reason[:300]}"
                for j in sorted(judgments, key=lambda j: j.request_id)
                if not j.faithful
            ],
        ]
    else:
        lines.append("Not run. Use `make judge-live`.")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Write reports/production_signals_<source>.md."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="simulation")
    args = parser.parse_args()
    settings = get_settings()
    repository = Repository(create_database(settings.resolve(settings.database_path)))
    boot = load_benchmark_config()["bootstrap"]
    path: Path = PROJECT_ROOT / "reports" / f"production_signals_{args.source}.md"
    path.write_text(
        build_report(repository, settings, args.source, Rates(boot["resamples"], boot["seed"]))
    )
    print(f"Wrote reports/{path.name}")


if __name__ == "__main__":
    main()
