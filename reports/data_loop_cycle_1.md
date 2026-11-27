# Data loop, cycle 1: from logged failures to new articles

| Field | Value |
|---|---|
| Generated | 2026-11-27 |
| Git commit | b188058 |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | evals/sets/v2.jsonl and the Banking77 loop holdout pool |
| Generator LLM | openai/gpt-oss-20b |
| Judge model | qwen/qwen3.8-27b (used in this report) |


**All 49 queue labels, the 8 new articles and every reference answer are by Claude Code. No person has reviewed them.** The judge is not validated.

## Result in plain words

Notes by Claude Code, **not reviewed by a human**.

- **On messages that were never mined, on the filled topics, "resolved" rose from 5/54 to
  43/54.** On 30 messages from other topics it went from 25/30 to 26/30. This is the better
  evidence, with three cautions: the topics were picked by their intent label, "resolved"
  relies on an unvalidated judge, and faithful does not mean useful.
- **The gain on the mined questions is expected** (9/29 to 17/29 passed): the articles were
  written for them. 12 of the 29 still fail.
- **Other eval v1 tasks got slightly worse:** 4 of 133 stopped passing and none started.
  By the paired bootstrap interval the drop is clear (-0.060 to -0.008); the exact McNemar
  test, with only 4 changed tasks, gives p = 0.125. From reading the four: two answers now
  leave out a step that the judge wants, one cites differently, and one student-account
  question is now refused instead of handed off. Whether the new articles caused each of
  these has not been established.
- **Circularity beyond the mined set:** Claude Code wrote the labels, the articles and the
  reference answers, and the 17 changed eval v1 tasks have references written to match the
  new articles. The articles are invented policy for a fictional company.
- **Mining missed some gaps.** All 10 planted gaps appeared in the traffic, but only 7 had a
  message flagged. A gap answered confidently from a similar article raises no signal.
  `automatic_top_up` was not found and is still open. The disposable-card article came from
  one flagged message whose intent was not a planted gap.
- The mined turns were answered by `llama3.2:3b`; before/after uses `gpt-oss-20b`. Most
  confirmed failures (18 of 29) were model errors or needless hand-offs, which new articles
  do not target. No prompt or retrieval change was made for them in this cycle.

## Mining

200 stored turns (simulated traffic answered by llama3.2:3b in Phase 2) gave 49 candidates, 49 queue items after merging duplicates, in 39 groups. Signals (a turn can have several): {'blocked_output': 6, 'escalation': 39, 'fee_claim': 4, 'low_faithfulness': 8, 'out_of_scope_refusal': 1, 'weak_retrieval': 9}.

Labels: {'not_failure': 16, 'failure': 29, 'unclear': 4}. Causes of the confirmed failures: {'needs_new_article': 11, 'model_error': 16, 'over_escalation': 2}.

## Planted gaps (scored afterwards)

- Planted gaps present in the mined traffic: 10 of 10.
- With at least one message in the queue: 7.
- Labelled 'needs new article': 7 (age_limit, apple_pay_or_google_pay, atm_support, card_swallowed, edit_personal_details, lost_or_stolen_phone, terminate_account).
- 'Needs new article' items that were not a planted gap: 1 of 11.
- **Not an independent test of labelling:** the labeller had read the list of planted gaps in the project files before labelling. The mining code reads only the database.

## Before and after on eval set v2

Same code, prompt v1 and models; only the knowledge base differs. 'Before' is scored against the v2 labels, so tasks that now expect an answer are bound to look bad before. The mined rows show whether the fix works on the questions it was made for, **not** how well it generalises.

| Tasks | Measure | Before | After | Change [95% paired bootstrap] | Gained / lost | McNemar p |
|---|---|---|---|---|---|---|
| Mined failures (29) | pass | 9/29 = 0.310 | 17/29 = 0.586 | +0.276 [+0.138, +0.448] | 8 / 0 | 0.008 |
| Mined failures (29) | right behaviour | 17/29 = 0.586 | 26/29 = 0.897 | +0.310 [+0.138, +0.483] | 9 / 0 | 0.004 |
| Eval v1 tasks whose gap was filled (17) | pass | 0/17 = 0.000 | 15/17 = 0.882 | +0.882 [+0.706, +1.000] | 15 / 0 | <0.001 |
| Eval v1 tasks whose gap was filled (17) | right behaviour | 3/17 = 0.176 | 17/17 = 1.000 | +0.824 [+0.647, +1.000] | 14 / 0 | <0.001 |
| All other eval v1 tasks (harm check) (133) | pass | 89/133 = 0.669 | 85/133 = 0.639 | -0.030 [-0.060, -0.008] | 0 / 4 | 0.125 |
| All other eval v1 tasks (harm check) (133) | right behaviour | 120/133 = 0.902 | 120/133 = 0.902 | +0.000 [-0.023, +0.023] | 1 / 1 | 1.000 |
| All of eval v2 (179) | pass | 98/179 = 0.547 | 117/179 = 0.654 | +0.106 [+0.050, +0.162] | 23 / 4 | <0.001 |
| All of eval v2 (179) | right behaviour | 140/179 = 0.782 | 163/179 = 0.911 | +0.128 [+0.078, +0.179] | 24 / 1 | <0.001 |

Other eval v1 tasks that passed before and fail after: 4 (`v1-001`, `v1-083`, `v1-129`, `v1-133`).

## Never-mined messages

54 holdout messages on the filled topics and 30 random ones from other topics. 'Resolved' means answered without hand-off and judged faithful. It does not show that the answer solves the problem.

| Tasks | Measure | Before | After | Change [95% paired bootstrap] | Gained / lost | McNemar p |
|---|---|---|---|---|---|---|
| Never mined, filled topics (54) | resolved | 5/54 = 0.093 | 43/54 = 0.796 | +0.704 [+0.574, +0.815] | 38 / 0 | <0.001 |
| Never mined, filled topics (54) | answered, no hand-off | 12/54 = 0.222 | 45/54 = 0.833 | +0.611 [+0.481, +0.741] | 33 / 0 | <0.001 |
| Never mined, filled topics (54) | shown text judged unfaithful | 8/54 = 0.148 | 2/54 = 0.037 | -0.111 [-0.222, -0.019] | 1 / 7 | 0.070 |
| Never mined, other topics (30) | resolved | 25/30 = 0.833 | 26/30 = 0.867 | +0.033 [+0.000, +0.100] | 1 / 0 | 1.000 |
| Never mined, other topics (30) | answered, no hand-off | 26/30 = 0.867 | 27/30 = 0.900 | +0.033 [+0.000, +0.100] | 1 / 0 | 1.000 |
| Never mined, other topics (30) | shown text judged unfaithful | 1/30 = 0.033 | 1/30 = 0.033 | +0.000 [+0.000, +0.000] | 0 / 0 | 1.000 |

After the fix, 46/54 filled-topic replies cite one of the new articles.
