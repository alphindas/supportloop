"""Load knowledge-base articles (markdown files with a front-matter header)."""

from dataclasses import dataclass
from pathlib import Path

import yaml

# COVERAGE.md describes the planted gaps, so it must never become searchable content.
NOT_ARTICLES = {"COVERAGE.md"}
REQUIRED_FIELDS = ("id", "title", "category", "last_updated")


@dataclass(frozen=True)
class Article:
    """One help article."""

    id: str
    title: str
    category: str
    last_updated: str
    review_status: str
    body: str


def parse_article(path: Path) -> Article:
    """Read one article file and check its header is complete."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError(f"{path.name}: expected a front-matter block between '---' lines")
    meta = yaml.safe_load(parts[1])
    missing = [field for field in REQUIRED_FIELDS if not meta.get(field)]
    if missing:
        raise ValueError(f"{path.name}: missing front-matter fields {missing}")
    if meta["id"] != path.stem:
        raise ValueError(f"{path.name}: id '{meta['id']}' must match the file name")
    return Article(
        id=meta["id"],
        title=meta["title"],
        category=meta["category"],
        last_updated=str(meta["last_updated"]),
        review_status=meta.get("review_status", "unknown"),
        body=parts[2].strip(),
    )


def load_articles(kb_dir: Path) -> list[Article]:
    """Load every article in the folder, sorted by file name so runs are repeatable."""
    paths = sorted(p for p in kb_dir.glob("*.md") if p.name not in NOT_ARTICLES)
    if not paths:
        raise ValueError(f"No articles found in {kb_dir}")
    return [parse_article(path) for path in paths]
