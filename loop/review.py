"""Label the mined queue: which candidates are real failures, and what should happen?

Every saved label records who gave it. Labels are only appended, never changed.

Usage:
    uv run python -m loop.review                       # a person, one item at a time
    uv run python -m loop.review --import file.yaml --reviewer "Claude Code"
"""

import argparse
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import yaml

from app.config import PROJECT_ROOT
from loop.mine import load_loop_config

VERDICTS = ("failure", "not_failure", "unclear")
CAUSES = ("needs_new_article", "model_error", "over_escalation", "retrieval_miss")
BEHAVIOURS = ("answer", "escalate", "refuse")
PERSON = "a person (self-declared)"


def read_lines(path: Path) -> list[dict]:
    """A JSON-lines file, or nothing if it does not exist yet."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate(label: dict) -> None:
    """A failure needs a cause and what should have happened. Others need neither."""
    if label.get("verdict") not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    if label["verdict"] != "failure":
        return
    if label.get("cause") not in CAUSES:
        raise ValueError(f"a failure needs a cause from {CAUSES}")
    if label.get("expected_behavior") not in BEHAVIOURS:
        raise ValueError(f"a failure needs expected_behavior from {BEHAVIOURS}")
    if label["cause"] == "needs_new_article" and not label.get("topic"):
        raise ValueError("needs_new_article needs a topic")


def record(output: Path, item_id: str, label: dict, reviewer: str) -> None:
    """Append one label."""
    validate(label)
    row = {"item_id": item_id, **label, "reviewer": reviewer, "reviewed_on": str(date.today())}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def import_labels(queue: list[dict], labels: dict, output: Path, reviewer: str) -> int:
    """Save labels prepared in a file: {item_id: {verdict, ...}}."""
    if reviewer.strip().lower().startswith("a person"):
        raise ValueError("Imported labels cannot claim to be a person's live review")
    known = {item["item_id"] for item in queue}
    done = {row["item_id"] for row in read_lines(output)}
    if unknown := set(labels) - known:
        raise ValueError(f"Unknown items: {sorted(unknown)}")
    for label in labels.values():
        validate(label)
    fresh = [item_id for item_id in labels if item_id not in done]
    for item_id in fresh:
        record(output, item_id, labels[item_id], reviewer)
    return len(fresh)


def choose(ask: Callable[[str], str], prompt: str, options: tuple[str, ...]) -> str:
    """Ask until the reply is one of the numbered options."""
    menu = ", ".join(f"{i}={name}" for i, name in enumerate(options, start=1))
    while True:
        reply = ask(f"{prompt} [{menu}] ").strip()
        if reply.isdigit() and 1 <= int(reply) <= len(options):
            return options[int(reply) - 1]


def review(
    queue: list[dict],
    output: Path,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
) -> None:
    """Walk a person through the items not yet labelled."""
    done = {row["item_id"] for row in read_lines(output)}
    todo = [item for item in queue if item["item_id"] not in done]
    say(f"{len(done)} labelled, {len(todo)} to go.")
    for item in todo:
        say("=" * 78)
        say(f"{item['item_id']}  group {item['cluster']} ({item['cluster_turns']} turns)")
        say(f"Signals: {', '.join(item['signals'])}   Bot did: {item['behavior']}")
        say(f"\nCUSTOMER: {item['message']}\n\nSHOWN: {item['answer']}")
        say(f"\nMODEL TEXT: {item['model_reply']}")
        say(f"\nArticles retrieved: {', '.join(item['retrieved_articles'])}")
        if ask("Enter to label, s to skip, q to quit: ").strip().lower() in ("s", "q"):
            continue
        label: dict = {"verdict": choose(ask, "Verdict", VERDICTS)}
        if label["verdict"] == "failure":
            label["cause"] = choose(ask, "Cause", CAUSES)
            label["expected_behavior"] = choose(ask, "Right behaviour", BEHAVIOURS)
            articles = ask("Right article ids, space separated (may be empty): ").split()
            label["expected_article_ids"] = articles
            if label["cause"] == "needs_new_article":
                label["topic"] = ""
                while not label["topic"]:
                    label["topic"] = ask("Short topic for the new article: ").strip()
        label["note"] = ask("Note (optional): ").strip()
        record(output, item["item_id"], label, PERSON)


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--import", dest="source", type=Path)
    parser.add_argument("--reviewer", help="required with --import")
    args = parser.parse_args()
    folder = PROJECT_ROOT / "loop" / f"cycle{load_loop_config()['cycle']}"
    queue = read_lines(folder / "queue.jsonl")
    if not queue:
        raise SystemExit("No queue. Run `uv run python -m loop.mine` first.")
    output = folder / "reviews.jsonl"
    if args.source:
        if not args.reviewer:
            raise SystemExit("--import needs --reviewer: every label records who gave it.")
        labels = yaml.safe_load(args.source.read_text())
        print(f"Saved {import_labels(queue, labels, output, args.reviewer)} labels")
    else:
        review(queue, output)


if __name__ == "__main__":
    main()
