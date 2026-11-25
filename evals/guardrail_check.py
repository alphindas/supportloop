"""How often do the guardrail rules fire on real, harmless customer messages?

Banking77 test messages are ordinary customer questions, so any injection hit there is
a false positive. This does NOT measure how many real attacks are caught.

Usage: uv run python -m evals.guardrail_check
"""

from app.banking77 import read_messages
from app.config import PROJECT_ROOT, get_settings
from app.guardrails.pii import redact
from app.guardrails.rules import load_guardrails
from evals.report_header import report_header

REPORT = PROJECT_ROOT / "reports" / "guardrails_v1.md"


def main() -> None:
    """Run every rule over every message and write the counts."""
    settings = get_settings()
    messages = read_messages(PROJECT_ROOT / "data" / "banking77" / "test.csv")
    injection, escalation = load_guardrails(settings.resolve(settings.guardrails_path))

    injection_hits, redacted, escalated = [], [], {}
    for message in messages:
        result = redact(message.text)
        if result.counts:
            redacted.append((message, result))
        if injection.matches(result.text):
            injection_hits.append(message)
        for rule in escalation.matches(result.text):
            escalated.setdefault(rule, []).append(message)
    any_escalation = {m.message_id for group in escalated.values() for m in group}
    total = len(messages)

    lines = [
        report_header(
            "Guardrail rules on real customer messages",
            settings,
            eval_set=f"Banking77 test.csv, all {total} messages (CC BY 4.0, PolyAI)",
            models={"Models": "none (pattern rules only)"},
            judge_used=False,
        ),
        "## Prompt-injection rules",
        "",
        f"Wrongly flagged: **{len(injection_hits)}/{total}** harmless messages.",
        *[f"- `{m.message_id}` ({m.intent}): {m.text}" for m in injection_hits],
        "",
        "This says nothing about recall. The only attacks tested are the examples in "
        "`tests/test_guardrails_rules.py`, written by the same author as the rules. A "
        "rephrased or non-English attack can get through.",
        "",
        "## PII redaction",
        "",
        f"Messages changed: **{len(redacted)}/{total}**.",
        *[f"- `{m.message_id}` {r.counts}: {r.text}" for m, r in redacted],
        "",
        "PII detection is only tested on made-up examples in `tests/test_guardrails_pii.py`. "
        "Names and addresses are not detected at all.",
        "",
        "## Escalation rules",
        "",
        f"At least one rule fired on **{len(any_escalation)}/{total}** "
        f"({len(any_escalation) / total:.1%}) messages. There are no labels saying which of "
        "these really need a person, so this is a rate, not an accuracy.",
        "",
        "| Rule | Messages | Most common intents |",
        "|---|---|---|",
    ]
    for rule, group in sorted(escalated.items()):
        intents: dict[str, int] = {}
        for message in group:
            intents[message.intent] = intents.get(message.intent, 0) + 1
        common = sorted(intents.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
        top = ", ".join(f"{name} ({count})" for name, count in common)
        lines.append(f"| {rule} | {len(group)} | {top} |")
    REPORT.write_text("\n".join(lines) + "\n")
    print(
        f"injection false positives {len(injection_hits)}/{total}; "
        f"redacted {len(redacted)}; escalation rules fired on {len(any_escalation)}"
    )


if __name__ == "__main__":
    main()
