# Progress

## Done
- **Phase 1** (2026-11-25): knowledge base, retrieval, model benchmarks, chat API, guardrails.
- **After Phase 1 review:** BM25 dropped from the live path (DESIGN.md 6.3), threshold rounding
  bug fixed, history audited for secrets, pushed to GitHub (public). Online A/B stays on local
  Ollama.
- **Phase 2** (2026-11-25): SQLite storage, feedback, metrics, traces, simulator (200 messages
  replayed), eval set v1 (150), rule graders + LLM judge, eval report (reruns identical),
  live judging, production signals report, blind human-review tool, interview notes.

## Open: needed to close Phase 2
- [ ] Human review: `make human-review` (30 decisions; must be done by Alphin, never by AI).
      Then commit `evals/human_review/*.jsonl` and the rebuilt report.

## Waiting on Alphin
- Phase 1 and Phase 2 quiz answers (correct them when sent).
- "go" for Phase 3.
- Review AI-drafted labels (`make review-pairs`), eval set v1 and KB articles.
- Phase 2 commits are NOT pushed (the push request covered the state before Phase 2).

## Carry forward to Phase 3
- `retrieval_v1` test questions have been seen and were used for the BM25 decision. The fresh
  check on eval v1 inputs agreed with the decision.
- Eval v1 is frozen. Filling KB gaps needs eval v2, with gap-intent tasks changed to `answer`.
- Main eval weakness: unanswerable near-miss tasks get answered or refused. Prompt v2
  ("refuse vs escalate", "do not answer if the articles only cover a similar topic") is a
  natural A/B hypothesis. Do not tune the prompt by reading eval v1 failures and then report
  the gain on eval v1 as if it were unseen.
- Local `llama3.2:3b` gave wrong fee claims on simulated traffic that passed the number check.
  `phi4-mini` made no risky errors in the LLM benchmark. Relevant to the local online A/B.
- Online A/B on local Ollama: about 6 s per request with retrieval on CPU (200 requests took
  about 20 minutes).
- Mining must not read `data/sim/` or `data/kb/COVERAGE.md`.
- The local database holds the simulated turns Phase 3 mines. It is not in git.
