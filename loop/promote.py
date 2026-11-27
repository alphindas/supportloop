"""Turn reviewed failures into eval set v2, keeping where every task came from.

v2 = every eval v1 task (those whose topic now has an article change from hand-off to
answer) plus one task per queue item labelled 'failure'. v1 itself is never edited.

Usage: uv run python -m loop.promote
"""

import json
from collections import Counter
from pathlib import Path

import yaml

from app.config import PROJECT_ROOT
from loop.mine import load_loop_config
from loop.review import read_lines

SETS = PROJECT_ROOT / "evals" / "sets"


def mined_task(item: dict, label: dict, extra: dict, new_articles: dict, cycle: int) -> dict:
    """One eval task from a confirmed failure."""
    behaviour = extra.get("expected_behavior", label["expected_behavior"])
    articles = list(label.get("expected_article_ids") or [])
    if label["cause"] == "needs_new_article":
        articles = [new_articles[label["topic"]]]
    if behaviour != "answer":
        articles = []
    elif not articles or not extra.get("reference"):
        raise ValueError(f"{item['item_id']}: an answer task needs an article and a reference")
    return {
        "id": f"v2-{item['item_id']}",
        "category": "mined",
        "input": item["message"],
        "expected_behavior": behaviour,
        "expected_article_ids": articles,
        "also_acceptable_article_ids": [],
        "reference_answer": extra.get("reference") if behaviour == "answer" else None,
        "intent": None,
        "source": "mined_simulation_turn",
        "source_message_id": None,
        "pii_values": [],
        "labelled_by": label["reviewer"],
        "review_status": "labelled_by_claude_code_not_human_reviewed"
        if label["reviewer"].startswith("Claude")
        else "labelled_by_reviewer",
        "added_in_version": "v2",
        "provenance": {
            "cycle": cycle,
            "queue_item": item["item_id"],
            "request_id": item["request_id"],
            "signals": item["signals"],
            "cause": label["cause"],
            "label_note": label.get("note", ""),
            **({"override_reason": extra["why"]} if "why" in extra else {}),
        },
    }


def build_v2(
    v1: list[dict], queue: list[dict], reviews: list[dict], refs: dict, gaps: dict, cycle: int
) -> list[dict]:
    """All v2 tasks. Items labelled 'not_failure' or 'unclear' are not promoted."""
    tasks = []
    for task in v1:
        change = refs["eval_v1_changes"].get(task["id"])
        if change:
            if task["intent"] not in gaps["filled_gaps"]:
                raise ValueError(f"{task['id']} is not about a filled gap")
            task = {
                **task,
                "expected_behavior": "answer",
                "expected_article_ids": [change["article"]],
                "reference_answer": change["reference"],
                "review_status": "labelled_by_claude_code_not_human_reviewed",
                "provenance": {"cycle": cycle, "changed_from_v1": "escalate to answer"},
            }
        tasks.append(task)
    labels = {r["item_id"]: r for r in reviews}
    for item in queue:
        label = labels.get(item["item_id"])
        if label is None:
            raise ValueError(f"{item['item_id']} has no review")
        if label["verdict"] == "failure":
            extra = refs["mined"].get(item["item_id"], {})
            tasks.append(mined_task(item, label, extra, gaps["new_articles"], cycle))
    return tasks


def load(path: Path) -> dict:
    """A YAML file."""
    return yaml.safe_load(path.read_text())


def main() -> None:
    """Write evals/sets/v2.jsonl."""
    cycle = load_loop_config()["cycle"]
    folder = PROJECT_ROOT / "loop" / f"cycle{cycle}"
    output = SETS / "v2.jsonl"
    if output.exists():
        raise SystemExit("v2.jsonl exists. Changes belong in a new version.")
    tasks = build_v2(
        read_lines(SETS / "v1.jsonl"),
        read_lines(folder / "queue.jsonl"),
        read_lines(folder / "reviews.jsonl"),
        load(folder / "references.yaml"),
        load(folder / "gaps.yaml"),
        cycle,
    )
    output.write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in tasks))
    mined = [t for t in tasks if t["category"] == "mined"]
    print(
        f"{len(tasks)} tasks: {len(mined)} mined "
        f"{dict(Counter(t['expected_behavior'] for t in mined))}"
    )


if __name__ == "__main__":
    main()
