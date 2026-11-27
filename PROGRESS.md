# Progress

## Done
- **Phase 1** (2026-11-25): knowledge base, retrieval, model benchmarks, chat API, guardrails.
- **After Phase 1 review:** BM25 dropped from the live path (DESIGN.md 6.3), threshold rounding
  bug fixed, history audited for secrets, pushed to GitHub (public). Online A/B stays on local
  Ollama.
- **Phase 2** (2026-11-25): SQLite storage, feedback, metrics, traces, simulator (200 messages
  replayed), eval set v1 (150), rule graders + LLM judge, eval report (reruns identical),
  live judging, production signals report, judge review tool, interview notes.
- **Judge review, two rounds, by a second-AI reviewer (ChatGPT), NOT by a person.** Round 1:
  20/30, kappa -0.01. Round 2 (30 other tasks): 25/30, chance 69%, kappa 0.47. First
  recorded and published as human review; corrected 2026-11-25. ChatGPT version, prompt and
  inputs are not recorded.
- **Judge review round 3, the first human check** (2026-11-26): Alphin, who states no AI help.
  Agreement 20/30 (67%), 69% expected by chance, Cohen's kappa -0.06. Person passed 29/30, judge 21/30.
  Verdicts committed unedited. Whether any task looked familiar from the report: **not
  recorded** (the placeholder in Alphin's message was not filled in).
  **The judge is not validated.**
- **Never edit verdict files** (a test pins all three by hash). In rounds 1 and 2 the `human`
  field holds ChatGPT's verdict (evals/human_review/README.md).
- **Local model for the online A/B: `phi4-mini`**, a safety override of the pre-set rule,
  which picked `llama3.2:3b` (DESIGN.md 6.2). On two wrong-fee cases (`make fee-cases`) it
  **still gave a wrong fee on one**, so the override rests only on benchmark hand-off and
  refusal behaviour. Alphin agreed to keep it on that narrow basis. Pushed.

## Round 3 follow-up (2026-11-27)
- Round 3 commits are pushed.
- **Follow-up analysis of the 10 disagreements: not done** (skipped by Alphin). Item 1 was
  shown and no decision was recorded. Who was right is unchecked.
- Familiar tasks in round 3: **not recorded** (the placeholder was left unfilled twice).
- Alphin states they checked the Phase 2 Q1 interview answer and it is true.

## Phase 3: started 2026-11-27 (Alphin's "go")
Run Steps 3.0 to 3.6 in order. Stop only at two checkpoints: **fee test cases (3.0)**, where
Alphin marks each case and approves before the freeze, and **data loop review (3.2)**, where
only Alphin labels, with `loop/review.py`. Commit locally after each working step; push only
when Alphin says "push". Label drafts "drafted by Claude Code, reviewed by me" or "not
reviewed". Keep Groq caching on and long runs resumable.

- 3.0 fee accuracy test set: about 40 claims, half wrong, with the hard cases (real number on
  the wrong thing, wrong card type, combined rules, correct reuse of the same numbers). Freeze
  with a hash test after approval. The 2 known fee cases are development cases only.
- 3.1 claim-level fee check; old vs new on the frozen set, saved eval v1 replies and fresh
  phi4-mini replies, with 95% intervals. No tuning on eval v1 failures. List what it misses.
  `reports/fee_check_v1.md`.
- 3.2 `loop/mine.py` (escalations, low scores, wrong refusals, judge-flagged, blocked fee
  claims; embedding dedupe, cluster, rank; no PII-only items), `loop/review.py`,
  `loop/promote.py` to eval set v2 with provenance; draft articles Alphin asks for; before and
  after with intervals on mined and never-mined messages. `reports/data_loop_cycle_1.md`.
- 3.3 prompt_v1 vs prompt_v2 (hand off instead of refusing; clearer fee rules). Pre-register
  in `experiments/prompt_v2.yaml`. Offline paired on eval v2 (Groq: McNemar, bootstrap);
  online on `phi4-mini`, one message per user, hash assignment, fixed sample, no peeking.
  `reports/ab_prompt_v2.md`.
- 3.4 optional intent routing with Alphin's LoRA (`banking77_lora_artifacts.zip`; skip and say
  so if missing). Eval on a separate Banking77 test slice; A/B on vs off.
- 3.5 Dockerfile, compose (api, prometheus; ollama optional) with health check; CI (ruff,
  pytest with fakes, eval smoke test); final README with tables from the reports.
- 3.6 `docs/interview_notes/phase_3.md`, 3-4 resume bullets, final summary with unpushed
  commits, 3 quiz questions.

**Checkpoint 1 done (2026-11-27):** Alphin said "approve freeze". `evals/sets/fee_claims_v1.yaml`
is frozen (42 claims; hash test). First marks on the 10 hard claims: 3 matched Claude Code's
labels, 3 differed, 4 unsure. The 7 later matches came after seeing the labels, so are not
independent. The other 32 are labelled by Claude Code, not human-reviewed.

**New instruction (2026-11-27):** Alphin will answer no more checkpoints. Claude Code labels the
data loop queue and makes the remaining decisions. Record everywhere that these are by Claude
Code, **not reviewed by a human**. Write nothing in first person that Alphin did not do. Stop
only on Groq quota or usage limit (update this file first) or at the end. **Do not push.**

## Phase 3 status (2026-11-27). All labels and decisions below: Claude Code, not human-reviewed
- Done and committed: 3.0 freeze; 3.1 claim check + `reports/fee_check_v1.md`; 3.2 mining,
  labels, 8 articles, eval set v2, `reports/data_loop_cycle_1.md`; 3.3 pre-registration,
  routing and analysis code; 3.5 Docker, compose (checked locally), CI file (steps rehearsed
  in a clean container; **never run on GitHub**).
- A/B done: **don't ship** prompt v2 (`reports/ab_prompt_v2.md`). Offline pass rate unclear;
  online behaviour accuracy 0.642 to 0.460; guardrails broken. Prompt v1 stays the default.
- README, DESIGN section 12.1 and `docs/interview_notes/phase_3.md` written and committed.
- **Phase 3 is complete apart from push**, and from 3.4.
- 3.4 intent routing: skipped (optional). The adapter was not opened.
- Nothing pushed since the round 3 commits. **Push only when Alphin says "push".**

## Still open for Alphin
- Check Claude's reading of the replies in `reports/local_model_fee_cases.md`.
- Phase 1 and Phase 2 quiz answers (correct them when sent).
- Review AI-drafted labels (`make review-pairs`), eval set v1 and KB articles.

ChatGPT details for rounds 1 and 2 stay "not recorded" unless Alphin supplies them.

## Phase 3 main goal: fee accuracy (set by Alphin, 2026-11-25)
- Improve the number check so each number must match what it describes in the article: fee,
  minimum or limit, and which card type.
- Test it on the two wrong-fee cases.
- Show before and after on the eval set.

## Carry forward to Phase 3
- `retrieval_v1` test questions have been seen and were used for the BM25 decision. The fresh
  check on eval v1 inputs agreed with the decision.
- Eval v1 is frozen. Filling KB gaps needs eval v2, with gap-intent tasks changed to `answer`.
- Main eval weakness: unanswerable near-miss tasks get answered or refused. Prompt v2
  ("refuse vs escalate", "do not answer if the articles only cover a similar topic") is a
  natural A/B hypothesis. Do not tune the prompt by reading eval v1 failures and then report
  the gain on eval v1 as if it were unseen.
- Do not let a ship decision rest on judge scores alone: the judge is not validated.
  Any rubric or reference change goes in a NEW version; existing results stay. Another human
  check needs people who have not seen judge output.
- Both local models gave wrong fee claims that passed the number check (it cannot catch a
  real number attached to the wrong thing). A fee-claim check is a candidate improvement.
- Production signals (200 replayed messages) were measured on `llama3.2:3b`. They do not
  describe `phi4-mini`; both A/B arms need fresh runs on `phi4-mini`.
- Local replies can differ in wording between reruns even at temperature 0.
- Mining must not read `data/sim/` or `data/kb/COVERAGE.md`.
- The local database holds the simulated turns Phase 3 mines. It is not in git.
- Online A/B on local Ollama: about 6 s per request was measured with `llama3.2:3b` and
  retrieval on CPU (200 requests took about 20 minutes). Not yet measured end to end with
  `phi4-mini`.
