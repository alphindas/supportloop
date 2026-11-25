"""Reciprocal Rank Fusion (RRF): merge ranked lists using only each item's position."""


def reciprocal_rank_fusion(rankings: list[list[str]], k: int) -> list[tuple[str, float]]:
    """Merge several ranked lists of IDs into one.

    Each list gives an item 1 / (k + position) points, with positions starting at 1.
    Using positions avoids comparing BM25 scores with similarity scores, which are on
    different scales. A larger k makes the top few positions count less sharply.
    Ties are broken by ID so results are repeatable.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + position)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
