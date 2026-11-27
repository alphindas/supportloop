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
