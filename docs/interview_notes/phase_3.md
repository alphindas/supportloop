# Interview notes: Phase 3 (improve and ship)

Numbers come from `reports/fee_check_v1.md`, `reports/data_loop_cycle_1.md`, `reports/ab_prompt_v2.md` and the eval v2 reports. Written 2026-11-27.

**Be honest about authorship.** Phase 3 was built with Claude Code. After approving the freeze of the fee test set, the project owner stopped answering checkpoints. **The data loop labels, the 8 new articles, the reference answers, most fee-test labels, the reply labels, the experiment design and the ship or don't-ship style decisions were made by Claude Code and not reviewed by a human.** The one human input to the Phase 3 data: the owner marked 10 hard fee claims (7 of the final marks came after seeing Claude Code's label and reason).

The answers below are written without "I did". Before saying one in your own voice, read the code and report behind it, and keep saying who made each decision.

**The judge is still not validated** (one human round, kappa -0.06).

## 1. What was built and why

- **Fee claim check.** The old number check only asked whether an amount appeared in a cited article. The new one also reads the words around it: fee, minimum or limit, which product, which period, which card.
- **Data loop.** Code picks suspicious turns from the database, removes near-duplicates and groups them. A reviewer labels each one. Confirmed failures become eval tasks; missing topics become articles.
- **Eval set v2.** 179 tasks: the 150 from v1 plus 29 mined ones. v1 was not edited.
- **A/B testing.** Users are assigned to a prompt by a hash. The rule for deciding was written before results. One offline test (same tasks, both prompts) and one online test (600 simulated users).
- **Shipping basics.** A CPU-only Docker image, Compose with Prometheus, a CI workflow, and a README with the results.
- Why: Phase 2 could measure problems. Phase 3 tries to fix some and to check, with numbers, whether each fix worked.

## 2. Design decisions and rejected alternatives

All decisions in this table are Claude Code's, not reviewed by a human.

| Decision | Why | Rejected, and why |
|---|---|---|
| Rule-based claim check over a facts file | Free, instant, testable, and it can say why it blocked. | A second model call per reply: more latency and quota, and another unvalidated judge. The cost of rules: they only know the words written into them. |
| Freeze the fee test set, then commit the check, then run once | A check changed after seeing its test score is tuned on the test. | Fixing the misses and re-running: the score would stop meaning anything. |
| Also test on real saved and fresh replies | Short written claims are easier than real replies. This showed most of the gain did not carry over. | Reporting the test-set score only. |
| Keep the check on despite weak results | A wrong fee is treated as worse than a needless hand-off. | Turning it off: defensible too. On real replies it caught 1 more wrong reply and blocked 3 more correct ones than the old check. |
| Mining reads only the database | It must not see the list of planted gaps. | Using intent labels or the coverage file: that is reading the answer key. |
| Embeddings to merge duplicates and group | One topic should not fill the whole review queue. | Reviewing every turn: does not scale. |
| New articles contain no money amounts | The company is fictional; inventing fees would add facts the claim check does not know. | Writing detailed fee policy. |
| New eval version, never edit v1 | Old results stay reproducible. | Editing v1 in place: scores would change meaning silently. |
| Measure on never-mined messages too | Articles written for mined questions will help those questions. | Reporting only the mined tasks. |
| Report the harm check | New text in the knowledge base can change retrieval for other questions. 4 of 133 other tasks stopped passing. | Reporting only the gains. |
| Experiment file with metric, guardrails, sample size and rule, committed first | It stops choosing the metric after seeing results. | Deciding after looking. |
| One message per simulated user | The tests assume independent samples. | Many per user: intervals look tighter than they are. |
| McNemar offline, two-proportion online | Offline is paired (same tasks); online is two separate groups. | One test for both: throws away the pairing or assumes one that is not there. |
| Hash assignment | Same user, same variant, with nothing to store. | Random per request: a user would see both. |
| A ship decision may not rest on the judge alone | The judge is not validated. | Shipping on pass rate only. |
| CPU-only Docker image | Runs without a GPU; avoids the large GPU libraries. | GPU image: much larger and needs GPU setup on the host. |
| Skip intent routing | It was optional. | Building it late with no time to test it properly. |

## 3. Trade-offs, weaknesses, and what to do with more time

**The most important weakness: almost nothing in Phase 3 was checked by a person**, and one author (Claude Code) wrote the labels, the articles, the reference answers, the fee check and most of its test. Treat the results as a working method with early numbers, not as proof of quality.

**Fee claim check.**

- 42 frozen claims: wrong ones caught 3/21 → 17/21 [0.60, 0.92]; correct ones blocked 0/21 → 1/21.
- Real replies: eval v1 0/1 → 0/1 caught, 0/25 → 1/25 blocked. Fresh `phi4-mini` 0/4 → 1/4 caught, 1/30 → 3/30 blocked.
- Only 5 wrong real replies in total, so none of these shares is precise.
- It cannot catch missing conditions, wrong scope without a new amount, or products named in words it does not know.
- Likely reason for the gap (not tested): the test claims were short sentences by the same author as the check.

**Data loop.**

- Never mined, filled topics: answered and faithful 5/54 → 43/54. Other topics: 25/30 → 26/30.
- Eval v2 pass rate: 0.547 → 0.654. Part of this is expected: 17 references were rewritten to expect answers, and the articles were written for the mined questions.
- 4 of 133 other eval v1 tasks stopped passing, none started (McNemar p = 0.125; bootstrap interval excludes zero).
- Mining flagged 7 of 10 planted gaps, although all 10 were in the traffic. A confident answer from a similar article raises no signal. The labeller had read the gap list.
- 18 of 29 confirmed failures were model errors or needless hand-offs, which new articles do not fix.
- The mined turns came from `llama3.2:3b`; before and after used `gpt-oss-20b`.

**A/B test.** See `reports/ab_prompt_v2.md`.

<!-- AB-WEAK -->
- Online (600 users, `phi4-mini`): behaviour accuracy 0.642 → 0.460 with prompt v2; hand-offs 0.358 → 0.552; two guardrails broken.
- Offline: not finished.
<!-- /AB-WEAK -->
- Two changes were made in one prompt, so the test cannot say which caused the drop.
- The online label is crude: intent-based "answer" or "hand off". It does not check answer quality.
- The traffic is simulated.

**Shipping.** CI has not run on GitHub. The Compose Ollama profile was not tested. No authentication, one process, no alerts.

With more time: validate the judge with two people who have not seen its output; have a person review the Phase 3 labels and articles; test the fee check on replies and claims written by someone else; run the next prompt experiment with one change and fresh messages; run a second data loop cycle aimed at model errors.

## 4. Eight likely questions, with short answers

**Q1. Did your fee check work?**
Only partly. On 42 frozen claims it caught 17 of 21 wrong ones, up from 3. On real model replies it caught 0 of 1 and 1 of 4, and it blocked more correct replies than before. The test claims were written by the same author as the check, which is the likely reason, though that was not tested. So fee accuracy is not solved. Claude Code decided to keep the check on, because a wrong fee was treated as worse than an extra hand-off; that is a weak case and no person reviewed it.

**Q2. Why not fix the cases it missed and re-run?**
Then the test set would become training data for the rules, and the new score would say nothing about new replies. The check was committed before the run and not changed after it. A fix needs a new measurement on replies the fix has not seen.

**Q3. How does the data loop find failures without labels?**
From signals the running app has: hand-offs, weak search scores, out-of-scope refusals, blocked outputs, fee-claim flags, replies the live judge called unfaithful, errors and thumbs down. Near-identical messages are merged and the rest grouped by meaning. These are only suspicions: of 49 items, 29 were labelled real failures, 16 not failures and 4 unclear. It also misses things: 3 planted gaps in the traffic raised no signal. The labels were made by Claude Code, not a person.

**Q4. Pass rate rose from 0.547 to 0.654. How much of that is real?**
Less than it looks. The "before" run is scored against new labels that expect answers where articles did not exist, and the mined questions are the ones the articles were written for. The better evidence is the never-mined messages: 5/54 → 43/54 answered and faithful on the filled topics. Even that has limits: topics were chosen by intent label, the judge is not validated, faithful is not the same as helpful, and one author wrote articles and labels. And 4 other tasks got worse.

**Q5. What does pre-registration protect you from?**
From picking the metric, the cut-off or the stopping point after seeing results. The experiment file fixes the primary metric, guardrails, sample size and decision rule, and the report records the file's hash. The analysis code gives no result before the sample is complete. It does not protect against a bad metric: the online label here is crude.

**Q6. Prompt v2 was meant to help. What happened online?**
It did much worse on the online metric: 0.642 → 0.460, a difference of -0.182 [-0.260, -0.103]. Hand-offs rose from 0.358 to 0.552, mostly chosen by the model itself, and tokens rose past the limit. A likely cause is the line telling the model to hand off when unsure, but that is a guess: the prompt changed two things at once. The lesson is to change one thing per experiment.

**Q7. Why one message per user?**
Both tests used here treat each result as independent. Several messages from one user tend to succeed or fail together, which makes the intervals too narrow and the p-value too small. With real conversations one would randomise by user and analyse by user, or use a method that allows for the grouping.

**Q8. What does your CI prove?**
That the code passes lint, the tests pass with a fake model, embedder and reranker, and the eval runner works end to end on a few tasks, with no API keys. It says nothing about answer quality: that needs the real models and the eval reports. Its steps passed in a clean local container, but it has not run on GitHub yet.

## 5. Three files to read

1. **`app/guardrails/claims.py`** (with `config/money_facts.yaml`): follow `extract_claims` and `claim_problems`. Be able to explain one claim it catches and one it cannot (`fee-01` in the report).
2. **`ab/analyze.py`** (with `experiments/prompt_v2.yaml`): look at `decide` and `online_section`. Be able to say what blocks a result from being shown early and what makes the decision "don't ship".
3. **`loop/mine.py`**: look at `signal_names`, `merge_duplicates` and `cluster`. Be able to say what mining can see, what it must not read, and which failures raise no signal.
