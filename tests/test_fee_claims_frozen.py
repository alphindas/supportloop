"""The fee claim test set was frozen on 2026-11-27. Editing any of its files fails here."""

import hashlib
from collections import Counter

import pytest
import yaml

from app.config import PROJECT_ROOT

SETS = PROJECT_ROOT / "evals" / "sets"


@pytest.mark.parametrize(
    ("name", "digest"),
    [
        ("fee_claims_v1.yaml", "3eb9d9ff06e7719eb888a6e7afeaf09cb6a63d17fd25776776a8eb7989aba5a2"),
        (
            "fee_claims_v1.first_marks.yaml",
            "a67443f17064ac4b33228e0436b3bb7f7a75e0929f760803ac9d9ebfc770576c",
        ),
        (
            "fee_claims_v1.final_marks.yaml",
            "ad646ebf2fa62ef55213771e6ea5a58b4a3162e92db4b1f940bcf82aedb141f1",
        ),
    ],
)
def test_frozen_files_are_unchanged(name: str, digest: str) -> None:
    assert hashlib.sha256((SETS / name).read_bytes()).hexdigest() == digest


def test_shape_and_review_status() -> None:
    cases = yaml.safe_load((SETS / "fee_claims_v1.yaml").read_text())["cases"]
    assert len({c["id"] for c in cases}) == 42
    assert Counter(c["expected"] for c in cases) == {"correct": 21, "wrong": 21}
    assert Counter(c["review_status"] for c in cases) == {
        "labelled by Claude Code, not human-reviewed": 32,
        "human-marked after seeing Claude Code's label and reason": 7,
        "human-marked without seeing Claude Code's label": 3,
    }
