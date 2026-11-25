# Eval sets

## Attribution
Rows with `source: banking77_eval_pool` contain real customer messages from **Banking77**
by PolyAI, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/):
<https://github.com/PolyAI-LDN/task-specific-datasets>. Text is unchanged apart from
trimming surrounding spaces. The article labels are ours.

## retrieval_v1.jsonl
90 questions with expected articles (30 `dev` for choosing, 60 `test` held out) and
35 negative questions that no article answers.

- `source`: `banking77_eval_pool` (real message) or `ai_written`.
- `labelled_by` / `review_status`: all labels were drafted by AI. A row is only
  human-reviewed if `review_status` says so. Run `make review-pairs` to review.
- Real messages were drawn at random with a fixed seed, one per covered intent. Three
  were dropped as too vague to have one right article; see `retrieval_v1.excluded.json`.
