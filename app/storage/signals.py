"""Which turns are failure candidates, and why (DESIGN.md section 7)."""

# Guardrail events that mean "worth a look". Redacting personal data is the system
# working as intended, so it is counted in metrics but is not a failure signal.
SYSTEM_ERRORS = ("llm_error", "retrieval_error")


def signals_for_turn(
    *, escalate: bool, top_score: float | None, threshold: float, guardrail_events: list[str]
) -> list[tuple[str, str]]:
    """Return (signal, detail) pairs that can be known as soon as the reply is made.

    'negative_feedback' and 'low_faithfulness' arrive later.
    """
    signals: list[tuple[str, str]] = []
    if escalate:
        signals.append(("escalation", ""))
    if top_score is not None and top_score < threshold:
        signals.append(("weak_retrieval", f"{top_score:.4f}"))
    for event in guardrail_events:
        if event in SYSTEM_ERRORS:
            signals.append(("system_error", event))
        elif event.startswith(("prompt_injection:", "output_check:")) or event == "out_of_scope":
            # 'out_of_scope' is included because wrong refusals of real banking
            # questions would otherwise never reach a reviewer.
            signals.append(("guardrail", event))
    return signals
