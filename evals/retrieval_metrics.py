"""Retrieval metrics, measured on articles (several chunks of one article count once)."""

from collections.abc import Sequence


def distinct_articles(article_ids: Sequence[str]) -> list[str]:
    """Keep the first appearance of each article, preserving rank order."""
    return list(dict.fromkeys(article_ids))


def recall_at_k(ranked: Sequence[str], expected: Sequence[str], k: int) -> float:
    """Share of the expected articles that appear in the top k."""
    if not expected:
        raise ValueError("Recall is undefined without an expected article")
    return len(set(expected) & set(ranked[:k])) / len(set(expected))


def reciprocal_rank(ranked: Sequence[str], expected: Sequence[str]) -> float:
    """1 / position of the first expected article, or 0 if none was returned."""
    for position, article_id in enumerate(ranked, start=1):
        if article_id in expected:
            return 1.0 / position
    return 0.0


def choose_threshold(answerable_scores: Sequence[float], max_false_rate: float) -> float:
    """Highest threshold that wrongly escalates at most max_false_rate of answerable cases.

    A question is escalated when its top score is below the threshold.
    """
    ordered = sorted(answerable_scores)
    allowed = int(len(ordered) * max_false_rate)
    return ordered[allowed]
