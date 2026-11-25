# Progress

## Done
- **Phase 1** (2026-11-25): knowledge base, retrieval, model benchmarks, chat API, guardrails.
- **After Phase 1 review:** BM25 dropped from the live path (DESIGN.md 6.3), threshold bug fixed,
  history audited for secrets, pushed to GitHub (public). Online A/B stays on local Ollama.

## In progress: Phase 2
- [ ] SQLite storage of every turn + failure signals
- [ ] POST /feedback, GET /metrics
- [ ] OpenTelemetry traces
- [ ] ab/simulate.py (200 mining-pool messages)
- [ ] Eval set v1 (~150 tasks)
- [ ] Rule graders, LLM judge, live-traffic judge sampling
- [ ] run_eval.py + report; rerun gives same numbers
- [ ] human_review.py (the review itself must be done by Alphin, not by AI)
- [ ] Interview notes phase_2.md + quiz

## Waiting on Alphin
- Phase 1 quiz answers (to be corrected when sent; does not block Phase 2).
- Review AI-drafted labels (`make review-pairs`) and KB articles.

## Carry forward
- `retrieval_v1` test questions have been seen and were used for the BM25 decision.
- Candidate Phase 3 A/B hypothesis: prompt v2 separates "refuse" from "escalate" better.
- `llama3.2:3b` answered when it should not have in the LLM benchmark; `phi4-mini` did not.
