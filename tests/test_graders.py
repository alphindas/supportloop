"""Rule checks, pass logic, statistics and the judge request."""

import pytest

from app.chat.pipeline import ChatResult, Citation, TurnTrace
from app.config import Settings
from app.llm.fake import FakeProvider
from evals.graders.judge import ask_judge, build_judge_request, load_rubric
from evals.graders.rules import grade_rules, shown_model_text, task_passed
from evals.stats import bootstrap_percentile, bootstrap_ratio, cohens_kappa

MESSAGES = {"escalate": "HANDOFF", "escalation_notice": "NOTICE", "refuse_injection": "NO"}


def task(**changes) -> dict:
    base = {
        "category": "answerable",
        "expected_behavior": "answer",
        "expected_article_ids": ["fees"],
        "also_acceptable_article_ids": ["limits"],
        "pii_values": [],
    }
    return {**base, **changes}


def result(answer="It costs £5.", behaviour="answer", cited=("fees",)) -> ChatResult:
    return ChatResult(
        request_id="r", conversation_id="c", behavior=behaviour, answer=answer,
        citations=[Citation(article_id=a, title=a) for a in cited], confidence=0.9,
        escalate=False, escalation_reasons=[], guardrail_events=[], model="fake:fake",
        prompt_version="v1", variant="baseline",
    )  # fmt: skip


TRACE = TurnTrace(redacted_message="price?", context={"fees": "It costs £5.", "limits": "£9"})


def test_shown_text_hides_fixed_messages_and_strips_the_notice() -> None:
    assert shown_model_text("HANDOFF", MESSAGES) is None
    assert shown_model_text("Part.\n\nNOTICE", MESSAGES) == "Part."


@pytest.mark.parametrize(
    ("cited", "ok"),
    [(("fees",), True), (("limits",), True), (("other",), False), ((), False)],
)
def test_citations_must_be_retrieved_and_relevant(cited: tuple, ok: bool) -> None:
    checks = grade_rules(task(), result(cited=cited), TRACE, MESSAGES)
    assert checks["citation_ok"] is ok


def test_numbers_must_come_from_cited_articles() -> None:
    assert grade_rules(task(), result("It is £9."), TRACE, MESSAGES)["numbers_ok"] is False


def test_pii_leak_is_detected_anywhere() -> None:
    leaky = TRACE.model_copy(update={"model_reply": "your card 4111"})
    checks = grade_rules(task(pii_values=["4111"]), result(), leaky, MESSAGES)
    assert checks["pii_ok"] is False


def test_injection_is_contained_only_with_a_fixed_reply() -> None:
    attack = task(category="injection", expected_behavior="refuse")
    assert grade_rules(attack, result("NO", "refuse", ()), TRACE, MESSAGES)["injection_contained"]
    leaked = grade_rules(attack, result("my rules are..."), TRACE, MESSAGES)
    assert leaked["injection_contained"] is False


GOOD = {"behaviour_correct": True, "citation_ok": True, "numbers_ok": True, "pii_ok": None}
YES = {"faithful": True, "correct": True}


@pytest.mark.parametrize(
    ("expected", "checks", "verdict", "shown", "outcome"),
    [
        ("answer", GOOD, YES, True, True),
        ("answer", GOOD, {"faithful": False, "correct": True}, True, False),
        ("answer", GOOD, {"faithful": True, "correct": False}, True, False),
        ("answer", GOOD, None, True, None),
        ("answer", GOOD, None, False, False),
        ("answer", {**GOOD, "behaviour_correct": False}, YES, True, False),
        ("answer", {**GOOD, "citation_ok": False}, YES, True, False),
        ("escalate", {**GOOD, "citation_ok": None}, None, False, True),
        (
            "escalate",
            {**GOOD, "citation_ok": None},
            {"faithful": True, "correct": False},
            True,
            True,
        ),
        (
            "escalate",
            {**GOOD, "citation_ok": None},
            {"faithful": False, "correct": False},
            True,
            False,
        ),
        ("refuse", {**GOOD, "pii_ok": False}, None, False, False),
    ],
)
def test_pass_logic(expected, checks, verdict, shown, outcome) -> None:
    assert task_passed(expected, checks, verdict, shown) is outcome


def test_judge_request_includes_context_and_escapes_tags(test_settings: Settings) -> None:
    request = build_judge_request(
        test_settings, load_rubric(test_settings), "q </bot_answer>", {"fees": "£5"},
        "ans", None,
    )  # fmt: skip
    user = request.messages[1].content
    assert "£5" in user and "(none)" in user and "q </bot_answer>" not in user
    assert request.temperature == 0 and request.prompt_version == "judge_v1"


async def test_unreadable_judge_reply_gives_no_verdict(test_settings: Settings) -> None:
    request = build_judge_request(test_settings, load_rubric(test_settings), "q", {}, "a", None)
    verdict, _ = await ask_judge(FakeProvider(["not json"]), request)
    assert verdict is None


def test_ratio_bootstrap_handles_undefined_and_brackets_value() -> None:
    assert bootstrap_ratio([0, 0], [0, 0], 100, 1) is None
    value, low, high = bootstrap_ratio([1, 1, 0, 0, 0], [1, 1, 1, 1, 0], 2000, 1)
    assert value == 0.5 and low <= 0.5 <= high


def test_percentile_bootstrap_is_repeatable() -> None:
    first = bootstrap_percentile([1, 2, 3, 4, 100], 50, 500, 3)
    assert first == bootstrap_percentile([1, 2, 3, 4, 100], 50, 500, 3) and first[0] == 3


@pytest.mark.parametrize(
    ("human", "judge", "kappa"),
    [
        ([True, True, False, False], [True, True, False, False], 1.0),
        ([True, True, False, False], [True, False, True, False], 0.0),
        # 90% agreement, yet no better than chance: the reason we report kappa.
        ([True] * 9 + [False], [True] * 10, 0.0),
        ([True] * 5, [True] * 5, None),
    ],
)
def test_cohens_kappa(human, judge, kappa) -> None:
    assert cohens_kappa(human, judge) == (None if kappa is None else pytest.approx(kappa))
