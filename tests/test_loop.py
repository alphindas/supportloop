"""Mining and review bookkeeping for the data loop."""

import numpy as np
import pytest

from loop.mine import build_queue, cluster, merge_duplicates
from loop.review import PERSON, import_labels, read_lines, record, review

QUEUE = [{"item_id": "c1-001"}, {"item_id": "c1-002"}]


def test_duplicates_merge_and_similar_questions_cluster() -> None:
    similarity = np.array(
        [
            [1.0, 0.99, 0.85, 0.1],
            [0.99, 1.0, 0.84, 0.1],
            [0.85, 0.84, 1.0, 0.1],
            [0.1, 0.1, 0.1, 1.0],
        ]
    )
    groups = merge_duplicates(similarity, 0.97)
    assert groups == [[0, 1], [2], [3]]
    assert cluster(similarity, groups, 0.80) == [[[0, 1], [2]], [[3]]]


def test_queue_is_ranked_by_turns_covered() -> None:
    candidates = [{"request_id": r, "signals": ["escalation"]} for r in "abc"]
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]])
    queue = build_queue(
        candidates, vectors, {"cycle": 1, "duplicate_similarity": 0.97, "cluster_similarity": 0.8}
    )
    assert [(q["item_id"], q["cluster_turns"]) for q in queue] == [("c1-001", 2), ("c1-002", 1)]
    assert queue[0]["duplicate_request_ids"] == ["c"]


@pytest.mark.parametrize(
    "label",
    [
        {"verdict": "maybe"},
        {"verdict": "failure", "expected_behavior": "answer"},
        {"verdict": "failure", "cause": "needs_new_article", "expected_behavior": "answer"},
    ],
)
def test_incomplete_labels_are_rejected(tmp_path, label: dict) -> None:
    with pytest.raises(ValueError):
        record(tmp_path / "r.jsonl", "c1-001", label, "someone")


def test_imported_labels_cannot_claim_to_be_a_persons_review(tmp_path) -> None:
    with pytest.raises(ValueError):
        import_labels(QUEUE, {"c1-001": {"verdict": "unclear"}}, tmp_path / "r.jsonl", PERSON)


def test_labels_are_appended_once_and_name_the_reviewer(tmp_path) -> None:
    output = tmp_path / "r.jsonl"
    labels = {"c1-001": {"verdict": "unclear"}}
    assert import_labels(QUEUE, labels, output, "Claude Code") == 1
    assert import_labels(QUEUE, labels, output, "Claude Code") == 0
    assert read_lines(output)[0]["reviewer"] == "Claude Code"


def test_a_persons_review_is_marked_self_declared(tmp_path) -> None:
    item = {
        "item_id": "c1-001", "cluster": 1, "cluster_turns": 1, "signals": [], "behavior": "answer",
        "message": "m", "answer": "a", "model_reply": "a", "retrieved_articles": [],
    }  # fmt: skip
    replies = iter(["", "2", "fine"])
    review([item], tmp_path / "r.jsonl", ask=lambda _: next(replies), say=lambda _: None)
    assert read_lines(tmp_path / "r.jsonl")[0]["reviewer"] == PERSON
