"""Review AI-drafted retrieval labels by hand. Progress is saved after every answer.

Keys: y = label is right, e = fix the expected articles, s = skip, q = quit.

Usage: uv run python -m scripts.review_pairs
"""

import json

from app.config import PROJECT_ROOT, get_settings
from app.rag.kb import load_articles

PAIRS = PROJECT_ROOT / "evals" / "sets" / "retrieval_v1.jsonl"


def save(rows: list[dict]) -> None:
    """Rewrite the file."""
    PAIRS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def ask_for_articles(titles: dict[str, str]) -> list[str]:
    """Read article ids until all of them exist. An empty line means 'no article'."""
    while True:
        typed = input("  correct article ids, comma separated (empty = none): ")
        ids = [part.strip() for part in typed.split(",") if part.strip()]
        unknown = [i for i in ids if i not in titles]
        if not unknown:
            return ids
        print(f"  unknown ids: {unknown}. Look in data/kb/.")


def main() -> None:
    """Walk through every unreviewed row."""
    settings = get_settings()
    titles = {a.id: a.title for a in load_articles(settings.resolve(settings.kb_dir))}
    rows = [json.loads(line) for line in PAIRS.read_text().splitlines() if line.strip()]
    todo = [r for r in rows if r["review_status"] != "human_reviewed"]
    print(f"{len(todo)} of {len(rows)} rows still to review.")
    for number, row in enumerate(todo, start=1):
        print(f"\n[{number}/{len(todo)}] {row['id']} ({row['source']}, {row['split']})")
        print(f"  Q: {row['question']}")
        for article_id in row["expected_article_ids"] or []:
            print(f"  -> {article_id}: {titles.get(article_id, '(missing!)')}")
        if not row["expected_article_ids"]:
            print("  -> no article should answer this")
        choice = input("  [y/e/s/q] ").strip().lower()
        if choice == "q":
            break
        if choice == "e":
            row["expected_article_ids"] = ask_for_articles(titles)
            row["labelled_by"] = "ai_then_human_edit"
        if choice in ("y", "e"):
            row["review_status"] = "human_reviewed"
            save(rows)


if __name__ == "__main__":
    main()
