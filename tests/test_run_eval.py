"""The eval runner end to end, with fake providers."""

import json

import pytest

from app.config import PROJECT_ROOT, Settings
from app.llm.base import LLMError, LLMQuotaExceededError
from app.llm.cache import CachedProvider, ResponseCache
from app.llm.fake import FakeProvider
from evals.eval_report import Rates, write_report
from evals.run_eval import is_temporary, run

ROWS = (PROJECT_ROOT / "evals" / "sets" / "v1.jsonl").read_text().splitlines()


@pytest.fixture
def paths(tmp_path):
    # A small mix: answerable, unanswerable, off-topic, PII and injection tasks.
    picked = [ROWS[i] for i in (0, 10, 62, 92, 120, 135, 136)]
    eval_set = tmp_path / "mini.jsonl"
    eval_set.write_text("\n".join(picked) + "\n")
    return {
        "name": "fake",
        "eval_set": eval_set,
        "raw": tmp_path / "raw.json",
        "report": tmp_path / "report.md",
    }


def judge_script() -> FakeProvider:
    verdict = {
        "faithfulness_reason": "ok", "faithful": True,
        "correctness_reason": "ok", "correct": True,
    }  # fmt: skip
    return FakeProvider([json.dumps(verdict)] * 20)


def providers(tmp_path):
    generator = CachedProvider(FakeProvider(), ResponseCache(tmp_path / "gen.db"))
    judge = CachedProvider(judge_script(), ResponseCache(tmp_path / "judge.db"))
    return generator, judge


def report_text(settings: Settings, result: dict, path) -> str:
    write_report(path, settings, result, Rates(200, 1), 30)
    return path.read_text()


async def test_rerun_gives_identical_results_and_report(
    test_settings: Settings, paths, tmp_path
) -> None:
    generator, judge = providers(tmp_path)
    first = await run(None, test_settings, paths, generator, judge)
    paths["raw"].write_text(json.dumps(first))
    second = await run(None, test_settings, paths, generator, judge)
    assert first["rows"] == second["rows"]
    assert all(r["passed"] is not None for r in first["rows"])
    a = report_text(test_settings, first, paths["report"])
    assert a == report_text(test_settings, second, paths["report"])
    assert "Pass rate (all tasks)" in a and "Not done yet" in a and "INCOMPLETE" not in a
    assert "Judge model" in a and "Prompt version" in a


async def test_batch_limit_stops_and_a_later_run_finishes(
    test_settings: Settings, paths, tmp_path
) -> None:
    generator, judge = providers(tmp_path)
    partial = await run(2, test_settings, paths, generator, judge)
    assert 0 < len(partial["rows"]) < 7
    assert "INCOMPLETE RUN" in report_text(test_settings, partial, paths["report"])
    paths["raw"].write_text(json.dumps(partial))
    complete = await run(None, test_settings, paths, generator, judge)
    assert len(complete["rows"]) == 7 and all(r["passed"] is not None for r in complete["rows"])
    for before in partial["rows"]:
        after = next(r for r in complete["rows"] if r["id"] == before["id"])
        assert after["latency_ms"] == before["latency_ms"]


async def test_quota_error_stops_instead_of_grading_the_handoff(
    test_settings: Settings, paths, tmp_path
) -> None:
    generator = FakeProvider([LLMQuotaExceededError("daily limit", 3600)])
    result = await run(None, test_settings, paths, generator, judge_script())
    assert result["rows"] == []


def test_only_rejected_requests_are_graded() -> None:
    assert not is_temporary(LLMError("HTTP 400: json_validate_failed"))
    assert is_temporary(LLMError("Gave up after 6 attempts; last problem: HTTP 429"))
    assert is_temporary(LLMQuotaExceededError("HTTP 429", 3600))
