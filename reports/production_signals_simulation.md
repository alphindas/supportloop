# Production signals: 'simulation' traffic

| Field | Value |
|---|---|
| Generated | 2026-11-25 |
| Git commit | ad0ab6c |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | none (stored traffic; no labels are used) |
| Generator LLM | ollama:llama3.2:3b |
| Variant | baseline |
| Knowledge base fingerprint | 78fdf89e95037eec |
| Traffic recorded | 2026-11-25 15:05 to 2026-11-25 15:24 UTC |
| Judge model | qwen/qwen3.8-27b (used in this report) |

These are signals, not accuracy: nothing here says whether a reply was right.

| Metric | Value |
|---|---|
| Turns | 200 from 200 users |
| Replies: answer | 0.800 [0.745, 0.855] (n=200) |
| Replies: escalate | 0.195 [0.140, 0.250] (n=200) |
| Replies: refuse | 0.005 [0.000, 0.015] (n=200) |
| Flagged for a human (escalation rate) | 0.195 [0.140, 0.250] (n=200) |
| Turns with at least one failure signal | 0.235 [0.175, 0.295] (n=200) |
| Latency p50 | 6000 ms [5860, 6130] |
| Latency p95 | 7652 ms [7167, 7787] |
| Tokens per reply, mean | 666 [660, 672] (n=200) |

## Failure signals

One turn can have several.

| Signal | Turns |
|---|---|
| escalation | 39 |
| guardrail | 7 |
| low_faithfulness | 8 |
| weak_retrieval | 9 |

## Guardrail events

| Event | Count |
|---|---|
| out_of_scope | 1 |
| output_check:citation_not_retrieved | 2 |
| output_check:ungrounded_number | 4 |

## LLM judge on a sample of live replies

Sample rate 20% of replies with model text, chosen by request ID. Judge: qwen/qwen3.8-27b, rubric v1. **The judge has not yet been validated against a person.**

- Judged faithful: 0.778 [0.639, 0.917] (n=36)

Replies judged unfaithful (judge's reason):

- `353daeb3` The bot claims the customer can transfer money to their credit card, but the articles only state that Visa and Mastercard debit and credit cards can be used to top up the account, not that money can be transferred to a credit card.
- `4c7f4236` The bot asserts a specific cause (reaching the daily limit) that is not supported by the customer's message or the articles, which only list it as one of several common reasons.
- `503217db` The statement that the customer cannot choose the exact delivery date is not supported by the provided help articles, which only list delivery timeframes and do not mention scheduling options.
- `a3510989` The bot claims the card arrives about 30 days before the old one expires, but the article states the renewal card is sent about 30 days before expiry, not that it arrives then. The article does not specify the arrival time relative to the expiry date, only that a new card is sent 30 days prior.
- `a8db2bee` The bot incorrectly states that the fee is '1.5% of the amount, or £10 minimum, whichever is higher.' The help articles state that the minimum per top-up is £10, but this is a limit on the transaction amount, not a minimum fee. The articles do not support the claim that the fee has a £10 minimum.
- `aa7037e2` The bot conflates the reasons for a top-up being reversed (from the 'topup-reverted' article) with the reasons for a card being cancelled. The articles do not state that a card is cancelled for these reasons; they explain why a payment or top-up was reversed or declined. Therefore, the factual claim
- `c3dad486` The bot invents specific app navigation steps ('Exchange' section, selecting card) that are not present in the provided articles. While the articles confirm that GBP and AUD are supported currencies for exchange, they do not describe the UI steps to perform the exchange.
- `f3d6916d` The bot incorrectly states that UK and EEA debit cards have a 1.5% fee, whereas the article explicitly states they are free. It also omits the fee for credit cards (1.5%).
