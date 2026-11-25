# Local models on two wrong-fee cases

| Field | Value |
|---|---|
| Generated | 2026-11-25 |
| Git commit | 82680a4 |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | none (two messages from the simulated traffic) |
| Generator LLM | ollama:llama3.2:3b, ollama:phi4-mini |
| Judge model | qwen/qwen3.8-27b (configured; not used in this report) |

Replies only; nothing here is graded automatically. Two questions are far too few to compare models.

## `llama3.2:3b`

### `a8db2bee`: What fee is included if I top up by card?

1 of 3 runs (answer; guardrail events: none):

> The fee for topping up by card is 1.5% of the amount, or £10 minimum, whichever is higher. If you top up by credit card, the fee is 1.5% of the amount. If you top up by debit card, the fee is free. If you top up by card issued outside the UK and EEA, the fee is 2.0% of the amount.

2 of 3 runs (answer; guardrail events: none):

> The fee for topping up by card is 1.5% of the amount, or £10 minimum, whichever is higher. If you top up by card issued outside the UK and EEA, the fee is 2.0% of the amount.

### `f3d6916d`: What are the top-up fees?

3 of 3 runs (answer; guardrail events: none):

> For card top-ups, the fee is 1.5% of the amount if the card is a UK debit card or an EEA debit card. If the card is issued outside the UK and EEA, the fee is 2.0% of the amount. Cash deposits have a fee of 1.5%.

## `phi4-mini`

### `a8db2bee`: What fee is included if I top up by card?

3 of 3 runs (answer; guardrail events: none):

> The fee for topping up by card is 1.5% of the amount. This applies to credit cards issued outside the UK and EEA, as well as cash deposits. The fee is shown before you confirm the top-up.

### `f3d6916d`: What are the top-up fees?

1 of 3 runs (answer; guardrail events: none):

> Top-up fees for NovaPay cards are as follows: UK and EEA debit cards have no fee, credit cards incur a 1.5% fee of the amount, and cards issued outside the UK and EEA have a 2.0% fee. Cash deposits also have a 1.5% fee. For bank transfers, NovaPay does not charge for UK or SEPA transfers, but international transfers may have additional bank charges. Top-up limits are £10 minimum, £5,000 maximum per top-up, £10,000 maximum per day, and £30,000 maximum in any 30 days.

2 of 3 runs (answer; guardrail events: none):

> Top-up fees for NovaPay cards are as follows: UK and EEA debit cards have no fee, credit cards incur a 1.5% fee of the top-up amount, and cards issued outside the UK and EEA have a 2.0% fee. Cash deposits also have a 1.5% fee. For bank transfers, NovaPay does not charge for UK or SEPA transfers, but international transfers may have additional bank charges. Top-up limits are £10 minimum, £5,000 maximum per top-up, £10,000 maximum per day, and £30,000 maximum in any 30 days.

## Fee article shown to the models

`a8db2bee`, `topup-fees`:

```
Top-up fees
Card top-ups
- UK debit card: free.
- EEA debit card: free.
- Credit card: 1.5% of the amount.
- Card issued outside the UK and EEA: 2.0% of the amount.

If both card rules apply, only the higher fee is charged. The fee is shown before you confirm.

Top-up fees
Cash
Cash deposits have a fee of 1.5%.
```

`f3d6916d`, `topup-fees`:

```
Top-up fees
Card top-ups
- UK debit card: free.
- EEA debit card: free.
- Credit card: 1.5% of the amount.
- Card issued outside the UK and EEA: 2.0% of the amount.

If both card rules apply, only the higher fee is charged. The fee is shown before you confirm.

Top-up fees
Cash
Cash deposits have a fee of 1.5%.

Top-up fees
Bank transfers
NovaPay does not charge for UK or SEPA bank transfer top-ups. For international (SWIFT) transfers, banks along the way may deduct their own charges.
```
