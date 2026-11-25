# Progress

## Done: Phase 1 (2026-11-25)
Repo setup, 60 KB articles, hybrid retrieval, model benchmarks, retrieval report, chat API with
guardrails, tests, sample conversations, interview notes.

## Waiting on Alphin
1. Quiz answers for `docs/interview_notes/phase_1.md`, then "go" for Phase 2.
2. Restart WSL (`wsl --shutdown` from Windows) so the new 10 GB limit applies.
3. Review AI-drafted labels: `make review-pairs`. KB articles also need review.
4. Nothing has been pushed to GitHub.

## Next: Phase 2
SQLite storage, `POST /feedback`, Prometheus `/metrics`, OpenTelemetry traces (not built in
Phase 1), `ab/simulate.py` (mining pool), eval set v1, graders and judge, human review.

## Carry forward
- Do not tune retrieval on `retrieval_v1` test questions: their results have been seen.
  Changes need new dev data and fresh test questions.
- Candidate Phase 3 A/B hypothesis: prompt v2 separates "refuse" from "escalate" better
  (v1 refused a savings-interest question in the samples and the LLM benchmark shows the
  same error type).
- Online A/B: the agreed plan is local Ollama. Measured Groq use (about 830 tokens a call)
  is lower than first assumed, so re-check that choice before Phase 3.
- Local-model benchmark did not include the score threshold; `llama3.2:3b` answered twice
  when it should not have. Re-check in the Phase 2 eval.
