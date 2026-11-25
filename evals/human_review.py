"""Check the LLM judge against a person: how often do they agree?

You give YOUR pass/fail without seeing the judge's verdict. Seeing it first would pull
your answer towards it and inflate agreement.

There are two rounds, reported separately and never pooled:
- Round 1: 30 random judge decisions. The judge's verdict was shown after each answer.
- Round 2: 30 tasks that were not in round 1, one decision each. The screen shows the
  same rubric text the judge gets, and no judge verdict is shown during the round.
The reason for round 2 is recorded in evals/human_review/<run>.notes.yaml.

Keys: y = pass, n = fail, s = skip for now, q = quit. Progress is saved after each one.

Usage: uv run python -m evals.human_review --round 2
Only a person should run this. Its whole point is to be independent of any model.
"""

import argparse
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from random import Random

from app.config import PROJECT_ROOT, get_settings
from app.prompts.loader import load_template
from evals.benchmark_retrieval import load_benchmark_config
from evals.eval_report import Rates, load_human_review, review_path, write_report
from evals.run_eval import HUMAN_SAMPLE_SIZE

# One fixed seed per round, so quitting and restarting keeps the same sample.
SEEDS = {1: 20261125, 2: 20261126}

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
    """Round 1: random decisions. One task can appear twice (both of its verdicts)."""
    everything = sorted(decisions(rows))
    return Random(seed).sample(everything, min(size, len(everything)))


def sample_new_tasks(
    rows: list[dict], excluded_tasks: set[str], size: int, seed: int
) -> list[tuple[str, str]]:
    """Round 2: `size` different tasks, none of them excluded, one decision each.

    All remaining decisions are shuffled and the first one seen for each task is kept.
    """
    remaining = sorted(d for d in decisions(rows) if d[0] not in excluded_tasks)
    Random(seed).shuffle(remaining)
    picked: dict[str, str] = {}
    for task_id, dimension in remaining:
        if task_id not in picked and len(picked) < size:
            picked[task_id] = dimension
    return list(picked.items())


def rubric_guidance(rubric_file: Path) -> dict[str, str]:
    """The definition of each verdict, cut from the rubric file the judge was given."""
    system = load_template(rubric_file, rubric_file.stem).system
    try:
        faithful = system.split("FAITHFUL:", 1)[1].split("CORRECT:", 1)[0]
        correct = system.split("CORRECT:", 1)[1].split("The articles, the customer", 1)[0]
    except IndexError as error:
        raise ValueError(f"{rubric_file.name} no longer has the expected sections") from error
    return {
        "faithful": f"FAITHFUL: {faithful.strip()}",
        "correct": f"CORRECT: {correct.strip()}",
    }


def show(
    row: dict, dimension: str, say: Callable[[str], None], guidance: dict[str, str] | None
) -> None:
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
    if guidance:
        say(f"\nRUBRIC (the same text the judge gets):\n{guidance[dimension]}")
    say(f"\n{QUESTIONS[dimension]}")


def recorded(output: Path) -> list[dict]:
    """Verdicts already saved in a round's file."""
    if not output.exists():
        return []
    return [json.loads(line) for line in output.read_text().splitlines() if line.strip()]


def review(
    rows: list[dict],
    output: Path,
    sample: list[tuple[str, str]],
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    reveal: bool = True,
    guidance: dict[str, str] | None = None,
) -> None:
    """Walk through the unreviewed part of a sample. Earlier verdicts are never changed:
    new ones are only appended."""
    by_id = {row["id"]: row for row in rows}
    done = {(r["id"], r["dimension"]) for r in recorded(output)}
    todo = [d for d in sample if d not in done]
    say(f"{len(done)} done, {len(todo)} to go.")
    output.parent.mkdir(parents=True, exist_ok=True)
    for task_id, dimension in todo:
        row = by_id[task_id]
        show(row, dimension, say, guidance)
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
        if reveal:
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
    """Run one round on the latest eval run, then rebuild its report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--round", type=int, choices=sorted(SEEDS), required=True)
    parser.add_argument("--run", help="a reports/raw/eval_*.json file (default: the only one)")
    args = parser.parse_args()
    raw_dir = PROJECT_ROOT / "reports" / "raw"
    candidates = [Path(args.run)] if args.run else sorted(raw_dir.glob("eval_*.json"))
    if len(candidates) != 1:
        raise SystemExit(f"Choose one with --run. Found: {[p.name for p in candidates]}")
    saved = json.loads(candidates[0].read_text())
    name, rows = saved["meta"]["config_name"], saved["rows"]
    output = review_path(name, args.round)

    if args.round == 1:
        review(rows, output, sample_decisions(rows, HUMAN_SAMPLE_SIZE, SEEDS[1]))
    else:
        first = load_human_review(name, 1)
        if len(first) < HUMAN_SAMPLE_SIZE:
            raise SystemExit("Finish round 1 first: round 2 uses only tasks it did not use.")
        sample = sample_new_tasks(rows, {r["id"] for r in first}, HUMAN_SAMPLE_SIZE, SEEDS[2])
        rubric = PROJECT_ROOT / saved["meta"]["models"]["Judge rubric"]
        review(rows, output, sample, reveal=False, guidance=rubric_guidance(rubric))

    boot = load_benchmark_config()["bootstrap"]
    report = PROJECT_ROOT / "reports" / f"{candidates[0].stem}.md"
    write_report(
        report, get_settings(), saved, Rates(boot["resamples"], boot["seed"]), HUMAN_SAMPLE_SIZE
    )
    print(
        f"\nRound {args.round}: {len(recorded(output))}/{HUMAN_SAMPLE_SIZE} decisions recorded. "
        f"Rebuilt {report.name}."
    )


if __name__ == "__main__":
    main()
