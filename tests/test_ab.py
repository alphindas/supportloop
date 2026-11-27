"""Assignment, statistics and the pre-registered decision rule."""

import pytest

from ab.analyze import decide, guardrail_breaches, sample_ratio_chi_square
from ab.assign import assign, load_experiment
from app.config import PROJECT_ROOT
from evals.stats import mcnemar_exact, two_proportion_p, wilson_interval

EXPERIMENT = load_experiment(PROJECT_ROOT / "experiments" / "prompt_v2.yaml")


def test_assignment_is_stable_and_close_to_the_planned_split() -> None:
    users = [f"user-{i}" for i in range(4000)]
    arms = [assign(EXPERIMENT, u) for u in users]
    assert arms == [assign(EXPERIMENT, u) for u in users]
    counts = {name: arms.count(name) for name in EXPERIMENT["variants"]}
    assert sample_ratio_chi_square(counts, EXPERIMENT["allocation"]) < 10.83


def test_a_lopsided_split_fails_the_sample_ratio_check() -> None:
    chi = sample_ratio_chi_square({"control": 380, "treatment": 220}, EXPERIMENT["allocation"])
    assert chi > 10.83


def test_mcnemar_uses_only_disagreements() -> None:
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(0, 10) == pytest.approx(2 / 1024)


def test_two_proportion_and_wilson_basics() -> None:
    assert two_proportion_p(50, 100, 50, 100) == pytest.approx(1.0)
    assert two_proportion_p(50, 100, 70, 100) < 0.01
    low, high = wilson_interval(0, 10)
    assert low == 0.0 and 0.2 < high < 0.35


def test_guardrails() -> None:
    control = {"escalation_rate": 0.2, "latency_p95": 100.0, "mean_tokens": 1000.0}
    worse = {"escalation_rate": 0.35, "latency_p95": 121.0, "mean_tokens": 1201.0}
    limits = EXPERIMENT["guardrails"]
    assert guardrail_breaches(control, control, limits, with_latency=True) == []
    assert len(guardrail_breaches(control, worse, limits, with_latency=True)) == 3


@pytest.mark.parametrize(
    ("offline", "online", "breaches", "behaviour", "decision"),
    [
        ("better", "unclear", [], 0.0, "ship"),
        ("better", "worse", [], 0.0, "don't ship"),
        ("better", "better", ["latency_p95"], 0.0, "don't ship"),
        ("better", "unclear", [], -0.01, "inconclusive"),
        ("unclear", "unclear", [], 0.1, "inconclusive"),
    ],
)
def test_decision_rule(offline, online, breaches, behaviour, decision) -> None:
    first = {"effect": offline, "breaches": [], "behaviour_difference": behaviour}
    assert decide(first, {"effect": online, "breaches": breaches})[0] == decision


def test_no_decision_until_both_parts_are_complete() -> None:
    assert decide(None, {"effect": "better", "breaches": []})[0] == "no decision yet"
