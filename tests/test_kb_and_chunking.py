"""The knowledge base is well formed and chunk IDs stay stable."""

import re

from app.config import PROJECT_ROOT
from app.rag.chunking import chunk_article, chunk_articles, corpus_fingerprint
from app.rag.kb import Article, load_articles

KB_DIR = PROJECT_ROOT / "data" / "kb"
CATEGORIES = {
    "cards",
    "top_ups",
    "transfers",
    "fees",
    "exchange_rates",
    "identity_verification",
    "account_security",
    "refunds_disputes",
}


def make_article(body: str) -> Article:
    return Article("a", "Title", "cards", "2026-11-25", "ai_drafted", body)


def test_articles_load_and_cover_every_category() -> None:
    articles = load_articles(KB_DIR)
    assert len(articles) >= 45
    assert {a.category for a in articles} == CATEGORIES
    assert "COVERAGE" not in {a.id for a in articles}


def test_coverage_file_matches_the_articles() -> None:
    article_ids = {a.id for a in load_articles(KB_DIR)}
    table = (KB_DIR / "COVERAGE.md").read_text(encoding="utf-8").split("## All intents")[1]
    rows = re.findall(r"^\| `([^`]+)` \| (\*\*GAP\*\*|`[^`]+`) \|$", table, re.MULTILINE)
    assert len(rows) == 77
    assert len({intent for intent, _ in rows}) == 77
    assert {target.strip("`") for _, target in rows if target != "**GAP**"} <= article_ids


def test_planted_gap_topics_do_not_appear_in_articles() -> None:
    """A rough keyword net. It cannot prove that a gap is not answered some other way."""
    leaks = re.compile(
        r"apple ?pay|google ?pay|mobile wallet|disposable|swallow|auto(matic)?[- ]?top|"
        r"(lost|stolen) phone|clos(e|ing) (your )?account|age limit|years old|under 18",
        re.IGNORECASE,
    )
    for article in load_articles(KB_DIR):
        assert not leaks.search(article.title + "\n" + article.body), article.id


def test_chunk_ids_are_unique_across_the_knowledge_base() -> None:
    chunks = chunk_articles(load_articles(KB_DIR), max_words=220)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_chunk_ids_follow_headings_not_positions() -> None:
    before = chunk_article(make_article("## Fees\nText one.\n\n## Limits\nText two."), 220)
    after = chunk_article(
        make_article("## New part\nAdded.\n\n## Fees\nText one.\n\n## Limits\nText two."), 220
    )
    assert {c.chunk_id for c in before} <= {c.chunk_id for c in after}


def test_long_sections_split_on_paragraphs_with_numbered_ids() -> None:
    body = "## Long\n" + "\n\n".join(["one two three four five"] * 3)
    chunks = chunk_article(make_article(body), max_words=6)
    assert [c.chunk_id for c in chunks] == ["a#long", "a#long-2", "a#long-3"]
    assert all(c.text.startswith("Title\nLong\n") for c in chunks)


def test_fingerprint_changes_when_text_changes() -> None:
    one = chunk_article(make_article("## Fees\nIt costs 5."), 220)
    two = chunk_article(make_article("## Fees\nIt costs 6."), 220)
    assert corpus_fingerprint(one) != corpus_fingerprint(two)
