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

## What's next
1. Alphin: say whether any round 3 task looked familiar from the report (IDs, or none).
2. Push the round 3 commits, only after Alphin agrees.
3. Alphin: check Claude's reading of the replies in `reports/local_model_fee_cases.md`.
4. Alphin: Phase 1 and Phase 2 quiz answers (correct them when sent).
5. Alphin: review AI-drafted labels (`make review-pairs`), eval set v1 and KB articles.
6. Alphin: "go" for Phase 3 (data loop, A/B testing, Docker, CI). **Not started. Wait for "go".**

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
