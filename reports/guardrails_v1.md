# Guardrail rules on real customer messages

| Field | Value |
|---|---|
| Generated | 2026-11-25 |
| Git commit | 450e704 |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | Banking77 test.csv, all 3080 messages (CC BY 4.0, PolyAI) |
| Models | none (pattern rules only) |
| Judge model | qwen/qwen3.8-27b (configured; not used in this report) |

## Prompt-injection rules

Wrongly flagged: **0/3080** harmless messages.

This says nothing about recall. The only attacks tested are the examples in `tests/test_guardrails_rules.py`, written by the same author as the rules. A rephrased or non-English attack can get through.

## PII redaction

Messages changed: **0/3080**.

PII detection is only tested on made-up examples in `tests/test_guardrails_pii.py`. Names and addresses are not detected at all.

## Escalation rules

At least one rule fired on **90/3080** (2.9%) messages. There are no labels saying which of these really need a person, so this is a rate, not an accuracy.

| Rule | Messages | Most common intents |
|---|---|---|
| lost_or_stolen | 65 | lost_or_stolen_card (33), lost_or_stolen_phone (13), cash_withdrawal_not_recognised (6) |
| possible_fraud | 36 | compromised_card (15), card_payment_not_recognised (6), lost_or_stolen_phone (5) |
