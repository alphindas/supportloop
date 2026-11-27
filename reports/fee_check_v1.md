# Fee claim check v1: old number check against the new claim check

| Field | Value |
|---|---|
| Generated | 2026-11-27 |
| Git commit | b5a6665+uncommitted |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | evals/sets/fee_claims_v1.yaml, saved eval v1 replies, fresh replies |
| Fresh replies | ollama:phi4-mini |
| Judge model | qwen/qwen3.8-27b (configured; not used in this report) |


## Result in plain words

**The large gain on the test claims mostly did not carry over to real replies.** On the 42
frozen claims the new check caught 17 of 21 wrong ones (old check: 3). On real model replies
it caught 0 of 1 (eval v1) and 1 of 4 (fresh phi4-mini); the old check caught none of these
5. It wrongly blocked 1 of 25 and 3 of 30 correct replies (old check: 0 and 1). The groups of
wrong replies are tiny, so none of these shares is precise.

The likely main reason for the gap: the test claims were short single sentences, written by
the same author as the check. This has not been tested.

**Decision (by Claude Code, not reviewed by a human): keep the claim check on.** A block
turns into a hand-off, and for a payments product a wrong fee is treated as worse than a
needless hand-off. This is a weak case: on real replies it caught 1 more wrong reply and
wrongly blocked 3 more correct ones than the old check. It does not solve fee accuracy.

**Next step:** judge it on new replies after any fix. Fixing the false blocks below and
re-measuring on the same replies would be tuning on the test data.

## What was compared

- **Old check:** every amount in the reply must appear in a cited article.
- **New check:** the old check, plus a claim check (`app/guardrails/claims.py`) that reads the
  words around each amount and compares fee, minimum or limit, product, period and card type
  with `config/money_facts.yaml`. A blocked reply is replaced by a hand-off.

The facts file, the check, these notes and the labels were written by Claude Code. **No
person has reviewed them.** The one exception is the owner's marks on 10 frozen claims.
The check was written from the articles and the two development cases and committed before
the runs below. Nothing in it was changed after seeing these results, and no eval v1
failure was used to write it. Shares are shown with 95% Wilson intervals.

## What the check still cannot catch

- **A missing condition.** Leaving out "only the higher fee is charged", or saying a fee
  starts after *both* limits when either one is enough.
- **A wrong scope without a new amount**, such as applying a 0.5% fee to the whole monthly
  total instead of the part above £1,000.
- **A claim whose product is not named in words it knows.** A clause such as "charged 1.5%
  to top up" names no card top-up phrase, so the cash fee of 1.5% appears to support it.
- **Rules with no amount**, such as "only the higher charge applies at weekends".
- Amounts written as words, and anything that is not about an amount or a "free" card.

It can also **block correct replies**: it picks up a period or product from a neighbouring
part of the sentence. In data loop mining it flagged a correct withdrawal reply this way
(item `c1-006`): a "per day" limit later in the sentence was read as the period of the £200
monthly allowance.

## (a) Frozen test set, 42 claims

**Not unseen by the builder:** Claude Code wrote these claims before writing the check. Read this as a development score. It was run after the check was committed, and the check was not changed afterwards.

| | Old number check | New check (number + claim) |
|---|---|---|
| Wrong claims caught | 3/21 = 0.14 [0.05, 0.35] | 17/21 = 0.81 [0.60, 0.92] |
| Wrong claims missed | 18/21 = 0.86 [0.65, 0.95] | 4/21 = 0.19 [0.08, 0.40] |
| Correct ones wrongly blocked | 0/21 = 0.00 [0.00, 0.15] | 1/21 = 0.05 [0.01, 0.23] |

**Missed by the new check: 4**
- `fee-01`: A credit card issued outside the UK and EEA is charged 1.5% to top up.
- `fee-21`: The 2% fee starts only after you have passed both the £200 limit and the 5-withdrawal limit.
- `fee-33`: If you exchange more than £1,000 in a month, the 0.5% fee applies to everything you exchanged that month.
- `fee-36`: At the weekend, if you are above your monthly allowance, only the higher charge, the 1% markup, applies.

**Wrongly blocked by the new check: 1**
- `fee-35`: At the weekend, if you are above your monthly allowance, you pay both the 0.5% fee and the 1% weekend markup. (0.5% does not match the article (topic))

### By who checked the label

10 hard claims with a mark by the project owner (7 settled after seeing Claude Code's label and reason). Picked by Claude Code, not at random.

| | Old number check | New check (number + claim) |
|---|---|---|
| Wrong claims caught | 0/6 = 0.00 [0.00, 0.39] | 4/6 = 0.67 [0.30, 0.90] |
| Wrong claims missed | 6/6 = 1.00 [0.61, 1.00] | 2/6 = 0.33 [0.10, 0.70] |
| Correct ones wrongly blocked | 0/4 = 0.00 [0.00, 0.49] | 1/4 = 0.25 [0.05, 0.70] |

32 claims labelled by Claude Code, not human-reviewed.

| | Old number check | New check (number + claim) |
|---|---|---|
| Wrong claims caught | 3/15 = 0.20 [0.07, 0.45] | 13/15 = 0.87 [0.62, 0.96] |
| Wrong claims missed | 12/15 = 0.80 [0.55, 0.93] | 2/15 = 0.13 [0.04, 0.38] |
| Correct ones wrongly blocked | 0/17 = 0.00 [0.00, 0.18] | 0/17 = 0.00 [0.00, 0.18] |

## (b) Saved eval v1 replies (gpt-oss-20b)

26 shown replies with a money statement. Labelled by Claude Code, not human-reviewed, before the new check was run on them.

| | Old number check | New check (number + claim) |
|---|---|---|
| Wrong claims caught | 0/1 = 0.00 [0.00, 0.79] | 0/1 = 0.00 [0.00, 0.79] |
| Wrong claims missed | 1/1 = 1.00 [0.21, 1.00] | 1/1 = 1.00 [0.21, 1.00] |
| Correct ones wrongly blocked | 0/25 = 0.00 [0.00, 0.13] | 1/25 = 0.04 [0.01, 0.20] |

**Missed by the new check: 1**
- `v1-109`: Yes, you can hold Swiss francs (CHF). On a Saturday, exchanging into CHF incurs the normal currency exchange fee plus a 1% weekend markup, as the weekend period runs from Friday 22:00 to Sunday 22:00 UK time.

**Wrongly blocked by the new check: 1**
- `v1-074`: Yes. You can top up as long as you stay within the limits: a minimum of £10, a maximum of £5,000 per top‑up, £10,000 per day, and £30,000 in any 30‑day period. For bank transfer top‑ups there is no upper limit, though transfers over £10,000 may require a source‑of‑funds check. (£10 does not match the article (period); £5000 does not match the article (period); £30000 does not match the article (period))

## (c) Fresh phi4-mini replies

34 replies with a money statement, from 36 questions written by Claude Code. Raw model replies, claim check off. Labelled by Claude Code, not human-reviewed, before the new check was run on them.

| | Old number check | New check (number + claim) |
|---|---|---|
| Wrong claims caught | 0/4 = 0.00 [0.00, 0.49] | 1/4 = 0.25 [0.05, 0.70] |
| Wrong claims missed | 4/4 = 1.00 [0.51, 1.00] | 3/4 = 0.75 [0.30, 0.95] |
| Correct ones wrongly blocked | 1/30 = 0.03 [0.01, 0.17] | 3/30 = 0.10 [0.03, 0.26] |

**Missed by the new check: 3**
- `phi-01`: To add money with your debit card from France, the top-up fee is 1.5% of the amount. Each deposit must be between £5 and £500. The fee is shown before you confirm the top-up.
- `phi-11`: The smallest cash deposit must be between £5 and £500. The largest cash deposit must be £500.
- `phi-31`: To add money to your NovaPay account, you can use cash, cheques, or card top-ups. Cash deposits have a fee of 1.5% of the amount. For amounts above £1,000 in a month, there's an additional 0.5% fee. Card top-ups are usually the fastest, but they may have different fees and limits. Bank transfers are recommended for larger amounts. Each method has its own fees and limits.

**Wrongly blocked by the new check: 3**
- `phi-07`: Yes, there is a daily cap on card top-ups. The maximum amount you can top up in a single day is £10,000. (£10000 does not match the article (period))
- `phi-08`: The maximum amount you can add by card over a month is £30,000. For more details on the top-up process, please contact NovaPay support. (£30000 does not match the article (period, role))
- `phi-19`: Amounts above £1,000 in a month have a 0.5% fee. For exchanging £2,000, the fee would be 0.5% of £1,000, which is £5. Support will help with the exact amount.
