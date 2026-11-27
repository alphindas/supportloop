"""Eval set v2 is built from the labels, and gap scoring counts honestly."""

import pytest

from app.config import PROJECT_ROOT
from loop.promote import SETS, build_v2, load
from loop.report import planted_gaps
from loop.review import read_lines

FOLDER = PROJECT_ROOT / "loop" / "cycle1"


def inputs() -> list:
    return [
        read_lines(SETS / "v1.jsonl"),
        read_lines(FOLDER / "queue.jsonl"),
        read_lines(FOLDER / "reviews.jsonl"),
        load(FOLDER / "references.yaml"),
        load(FOLDER / "gaps.yaml"),
        1,
    ]


def test_v2_is_reproducible_and_keeps_provenance() -> None:
    tasks = build_v2(*inputs())
    assert tasks == read_lines(SETS / "v2.jsonl")
    mined = [t for t in tasks if t["category"] == "mined"]
    assert len(mined) == 29
    assert all(t["provenance"]["request_id"] for t in mined)
    assert all(t["review_status"].endswith("not_human_reviewed") for t in mined)


def test_an_unreviewed_item_stops_promotion() -> None:
    arguments = inputs()
    arguments[2] = arguments[2][1:]
    with pytest.raises(ValueError, match="no review"):
        build_v2(*arguments)


def test_there_were_ten_planted_gaps() -> None:
    assert len(planted_gaps()) == 10
