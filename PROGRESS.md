# Progress

## Done
- **Phase 1** (2026-11-25): knowledge base, retrieval, model benchmarks, chat API, guardrails.
- **After Phase 1 review:** BM25 dropped from the live path (DESIGN.md 6.3), threshold rounding
  bug fixed, history audited for secrets, pushed to GitHub (public). Online A/B stays on local
  Ollama.
- **Phase 2** (2026-11-25): SQLite storage, feedback, metrics, traces, simulator (200 messages
  replayed), eval set v1 (150), rule graders + LLM judge, eval report (reruns identical),
  live judging, production signals report, blind human-review tool, interview notes.
- **Human review round 1** (by Alphin): 20/30, kappa -0.01. Published unedited; Alphin reported
  misapplying the rubric on some items. **Never edit verdict files** (a test pins round 1).

## Open
- [ ] Human review round 2: `make human-review ROUND=2` (Alphin only, never AI). It must be
      done without reading the report's "Failed tasks" table. Then commit
      `evals/human_review/*.round2.jsonl` and the rebuilt report, and add the numbers to
      README and docs/interview_notes/phase_2.md.
- [ ] If agreement is still poor: rubric or reference changes go in a NEW version.

## Waiting on Alphin
- Phase 1 and Phase 2 quiz answers (correct them when sent).
- "go" for Phase 3.
- Choose the local model for the online A/B (`llama3.2:3b` won by rule; `phi4-mini` made no
  risky errors in the benchmark).
- Review AI-drafted labels (`make review-pairs`), eval set v1 and KB articles.

## Carry forward to Phase 3
- `retrieval_v1` test questions have been seen and were used for the BM25 decision. The fresh
  check on eval v1 inputs agreed with the decision.
- Eval v1 is frozen. Filling KB gaps needs eval v2, with gap-intent tasks changed to `answer`.
- Main eval weakness: unanswerable near-miss tasks get answered or refused. Prompt v2
  ("refuse vs escalate", "do not answer if the articles only cover a similar topic") is a
  natural A/B hypothesis. Do not tune the prompt by reading eval v1 failures and then report
  the gain on eval v1 as if it were unseen.
- The judge is unvalidated, so do not let a ship decision rest on judge scores alone.
- Local `llama3.2:3b` gave wrong fee claims on simulated traffic that passed the number check.
- Online A/B on local Ollama: about 6 s per request with retrieval on CPU (200 requests took
  about 20 minutes).
- Mining must not read `data/sim/` or `data/kb/COVERAGE.md`.
- The local database holds the simulated turns Phase 3 mines. It is not in git.
