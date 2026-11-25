"""Hand-checked values for the metric and statistics helpers."""

import pytest

from evals.benchmark_retrieval import select
from evals.retrieval_metrics import (
    choose_threshold,
    distinct_articles,
    recall_at_k,
    reciprocal_rank,
)
from evals.stats import bootstrap_ci


def test_chunks_of_one_article_count_once() -> None:
    assert distinct_articles(["a", "a", "b", "a", "c"]) == ["a", "b", "c"]


def test_recall_counts_each_expected_article() -> None:
    assert recall_at_k(["a", "b", "c"], ["a", "z"], k=5) == 0.5
    assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["x", "a"], ["a"]) == 0.5
    assert reciprocal_rank(["x"], ["a"]) == 0.0


def test_threshold_respects_the_false_escalation_budget() -> None:
    scores = [i / 100 for i in range(1, 41)]  # 40 answerable questions
    threshold = choose_threshold(scores, max_false_rate=0.05)
    assert sum(s < threshold for s in scores) == 2


def test_bootstrap_is_repeatable_and_brackets_the_mean() -> None:
    values = [1.0] * 8 + [0.0] * 2
    first = bootstrap_ci(values, resamples=2000, seed=7)
    assert first == bootstrap_ci(values, resamples=2000, seed=7)
    assert first[0] <= 0.8 <= first[1]


def test_bootstrap_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([], resamples=10, seed=1)


def test_selection_prefers_the_faster_of_tied_candidates() -> None:
    runs = [
        {"name": "slow-best", "recall_at_k": 0.97, "mrr": 0.90, "latency_p50_ms": 300},
        {"name": "fast-tied", "recall_at_k": 0.95, "mrr": 0.88, "latency_p50_ms": 40},
        {"name": "fast-worse", "recall_at_k": 0.80, "mrr": 0.60, "latency_p50_ms": 5},
    ]
    assert select(runs, 0.034, "latency_p50_ms")["name"] == "fast-tied"
