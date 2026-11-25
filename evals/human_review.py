"""Check the LLM judge against a person: how often do they agree?

You see the task and give YOUR pass/fail first. Only then is the judge's verdict shown.
Seeing it first would pull your answer towards it and inflate agreement.

Keys: y = pass, n = fail, s = skip for now, q = quit. Progress is saved after each one.

Usage: uv run python -m evals.human_review
Only a person should run this. Its whole point is to be independent of any model.
"""

import argparse
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from random import Random

from app.config import PROJECT_ROOT, get_settings
from evals.benchmark_retrieval import load_benchmark_config
from evals.eval_report import HUMAN_DIR, Rates, load_human_review, write_report
from evals.run_eval import HUMAN_SAMPLE_SIZE

SEED = 20261125

QUESTIONS = {
    "faithful": "Is EVERY factual statement in the bot's answer supported by the articles?",
    "correct": "Does the answer give the key information in the reference, with nothing wrong?",
}


def decisions(rows: list[dict]) -> list[tuple[str, str]]:
    """Every judge decision as (task id, dimension).

    'correct' only exists for tasks that have a reference answer to compare with.
    """
    found = []
    for row in rows:
        if row["verdict"] is None:
            continue
        found.append((row["id"], "faithful"))
        if row["expected_behavior"] == "answer":
            found.append((row["id"], "correct"))
    return found


def sample_decisions(rows: list[dict], size: int, seed: int) -> list[tuple[str, str]]:
    """A fixed random sample, so quitting and restarting keeps the same 30."""
    everything = sorted(decisions(rows))
    return Random(seed).sample(everything, min(size, len(everything)))


def show(row: dict, dimension: str, say: Callable[[str], None]) -> None:
    """Print what the reviewer needs, without the judge's verdict."""
    say("=" * 78)
    say(f"Task {row['id']}  |  checking: {dimension}")
    if dimension == "faithful":
        say("\nHELP ARTICLES THE BOT WAS SHOWN:")
        for article_id, text in row["context"].items():
            say(f"\n--- {article_id} ---\n{text}")
    say(f"\nCUSTOMER: {row['input']}")
    if dimension == "correct":
        say(f"\nREFERENCE ANSWER: {row['reference_answer']}")
    say(f"\nBOT ANSWER: {row['shown_text']}")
    say(f"\n{QUESTIONS[dimension]}")


def review(
    rows: list[dict],
    output: Path,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    size: int = HUMAN_SAMPLE_SIZE,
) -> None:
    """Walk through the unreviewed part of the sample."""
    by_id = {row["id"]: row for row in rows}
    done = (
        {(r["id"], r["dimension"]) for r in map(json.loads, output.read_text().splitlines())}
        if output.exists()
        else set()
    )
    todo = [d for d in sample_decisions(rows, size, SEED) if d not in done]
    say(f"{len(done)} done, {len(todo)} to go.")
    output.parent.mkdir(parents=True, exist_ok=True)
    for task_id, dimension in todo:
        row = by_id[task_id]
        show(row, dimension, say)
        choice = ""
        while choice not in ("y", "n", "s", "q"):
            choice = (
                ask("your verdict [y = pass / n = fail / s = skip / q = quit] ").strip().lower()
            )
        if choice == "q":
            return
        if choice == "s":
            continue
        human = choice == "y"
        judge = row["verdict"][dimension]
        reason = row["verdict"][
            "faithfulness_reason" if dimension == "faithful" else "correctness_reason"
        ]
        say(f"\nJudge said {'PASS' if judge else 'FAIL'}: {reason}")
        say("AGREE" if human == judge else "DISAGREE")
        record = {
            "id": task_id,
            "dimension": dimension,
            "human": human,
            "judge": judge,
            "reviewed_on": date.today().isoformat(),
        }
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


def main() -> None:
    """Review the latest run, then rebuild its report with the agreement rate."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="a reports/raw/eval_*.json file (default: the only one)")
    args = parser.parse_args()
    raw_dir = PROJECT_ROOT / "reports" / "raw"
    candidates = [Path(args.run)] if args.run else sorted(raw_dir.glob("eval_*.json"))
    if len(candidates) != 1:
        raise SystemExit(f"Choose one with --run. Found: {[p.name for p in candidates]}")
    saved = json.loads(candidates[0].read_text())
    name = saved["meta"]["config_name"]
    review(saved["rows"], HUMAN_DIR / f"{name}.jsonl")

    boot = load_benchmark_config()["bootstrap"]
    report = PROJECT_ROOT / "reports" / f"{candidates[0].stem}.md"
    write_report(
        report,
        get_settings(),
        saved,
        Rates(boot["resamples"], boot["seed"]),
        HUMAN_SAMPLE_SIZE,
    )
    print(f"\n{len(load_human_review(name))} decisions recorded. Rebuilt {report.name}.")


if __name__ == "__main__":
    main()
