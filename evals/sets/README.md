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

## v1.jsonl
150 end-to-end tasks: answerable (real messages), unanswerable (planted-gap messages and
AI-written), off-topic, multi-part, PII (all personal data is fake) and prompt injection.

- Fields: `id`, `category`, `input`, `expected_behavior` (answer / escalate / refuse),
  `expected_article_ids`, `also_acceptable_article_ids`, `reference_answer`, `intent`,
  `source`, `source_message_id`, `pii_values`, `labelled_by`, `review_status`,
  `added_in_version`.
- Real messages were drawn at random (seed 20261126) from the eval pool, excluding all
  used in `retrieval_v1`. Dropped as unlabelable: see `v1.excluded.json`.
- All labels and reference answers are AI-drafted. A test checks that every number in a
  reference appears in its labelled article; that does not prove a label is right.
- Building this set exposed a redaction bug (`cvv 913` was not removed). It was fixed
  before the first eval run, so the PII results do not show the system as it was.
- **When KB gaps are filled (Phase 3)**, tasks with a planted-gap `intent` change from
  `escalate` to `answer`. That must happen in a new version, never by editing v1.
