"""The eval set is well formed and its AI-written references agree with the articles."""

import json
from collections import Counter

import pytest

from app.config import PROJECT_ROOT
from app.guardrails.output import ungrounded_numbers
from app.guardrails.pii import redact
from app.rag.kb import load_articles

SETS = PROJECT_ROOT / "evals" / "sets"
ROWS = [json.loads(line) for line in (SETS / "v1.jsonl").read_text().splitlines()]
ARTICLES = {a.id: f"{a.title}\n{a.body}" for a in load_articles(PROJECT_ROOT / "data" / "kb")}
REQUIRED = {
    "id", "input", "expected_behavior", "expected_article_ids", "reference_answer",
    "intent", "source", "added_in_version",
}  # fmt: skip


def test_shape_and_mix() -> None:
    assert len(ROWS) == 150 and len({r["id"] for r in ROWS}) == 150
    assert all(set(r) >= REQUIRED for r in ROWS)
    assert {r["expected_behavior"] for r in ROWS} == {"answer", "escalate", "refuse"}
    categories = Counter(r["category"] for r in ROWS)
    assert {"answerable", "unanswerable", "multi_part", "pii", "injection"} <= set(categories)


def test_answer_tasks_have_known_articles_and_references() -> None:
    for row in ROWS:
        ids = row["expected_article_ids"] + row["also_acceptable_article_ids"]
        assert set(ids) <= set(ARTICLES), row["id"]
        if row["expected_behavior"] == "answer":
            assert row["expected_article_ids"] and row["reference_answer"], row["id"]
        else:
            assert not ids and row["reference_answer"] is None, row["id"]


@pytest.mark.parametrize("row", [r for r in ROWS if r["reference_answer"]], ids=lambda r: r["id"])
def test_reference_numbers_come_from_the_labelled_articles(row: dict) -> None:
    ids = row["expected_article_ids"] + row["also_acceptable_article_ids"]
    texts = [ARTICLES[i] for i in ids]
    assert ungrounded_numbers(row["reference_answer"], texts, row["input"]) == set()


def test_every_planted_pii_value_is_redacted() -> None:
    rows = [r for r in ROWS if r["category"] == "pii"]
    assert rows
    for row in rows:
        cleaned = redact(row["input"]).text
        assert not [v for v in row["pii_values"] if v in cleaned], row["id"]


def test_real_messages_are_not_reused_from_the_retrieval_set() -> None:
    retrieval = (SETS / "retrieval_v1.jsonl").read_text().splitlines()
    used = {json.loads(line)["source_message_id"] for line in retrieval} - {None}
    mine = [r["source_message_id"] for r in ROWS if r["source_message_id"]]
    assert len(mine) == len(set(mine))
    assert not used & set(mine)
