"""Which turns count as failure candidates."""

import pytest

from app.storage.signals import signals_for_turn


def signals(escalate=False, top=0.9, events=()) -> list[str]:
    found = signals_for_turn(
        escalate=escalate, top_score=top, threshold=0.5, guardrail_events=list(events)
    )
    return [name for name, _ in found]


def test_a_good_answer_has_no_signals() -> None:
    assert signals() == []


def test_escalation_and_weak_retrieval() -> None:
    assert signals(escalate=True, top=0.1) == ["escalation", "weak_retrieval"]


@pytest.mark.parametrize(
    "event",
    ["prompt_injection:reveal_prompt", "output_check:ungrounded_number", "out_of_scope"],
)
def test_guardrail_events_are_signals(event: str) -> None:
    assert signals(events=[event]) == ["guardrail"]


def test_redacting_personal_data_is_not_a_failure() -> None:
    assert signals(events=["pii_redacted:EMAIL"]) == []


def test_system_errors_have_their_own_signal() -> None:
    assert signals(events=["llm_error"]) == ["system_error"]


def test_no_retrieval_means_no_weak_retrieval_signal() -> None:
    assert signals(top=None) == []
