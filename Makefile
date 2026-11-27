.PHONY: loop-holdout loop-report loop-mine loop-review loop-promote loop-before ab-analyze setup test lint format check data ingest run retrieval-eval benchmark-retrieval benchmark-llm eval review-pairs samples guardrail-check simulate eval-answers human-review judge-live traffic-report fee-cases fee-check

setup:                ## install everything from uv.lock and enable git hooks
	uv sync
	uv run pre-commit install

test:                 ## unit and integration tests (no API key, no model downloads)
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

check: lint test

ingest:               ## chunk, embed and index the knowledge base
	uv run python -m scripts.ingest

data:                 ## download Banking77 and build the message pools
	uv run python -m scripts.prepare_data

benchmark-retrieval:  ## compare embedders and rerankers (needs GPU, downloads models)
	uv run python -m evals.benchmark_retrieval

run:                  ## start the API on http://127.0.0.1:8000
	uv run uvicorn --factory app.main:create_app --host 127.0.0.1 --port 8000

fee-cases:            ## replay two wrong-fee questions on local models (needs Ollama)
	uv run python -m evals.fee_cases

benchmark-llm:        ## compare local chat models (needs Ollama; uses some Groq quota)
	uv run python -m evals.benchmark_llm

retrieval-eval:       ## evaluate retrieval on the held-out split and write the report
	uv run python -m evals.retrieval_eval

review-pairs:         ## review AI-drafted retrieval labels by hand
	uv run python -m scripts.review_pairs

eval: eval-answers    ## the full answer evaluation

samples:              ## send 10 sample conversations to the running API (make run first)
	uv run python -m scripts.sample_conversations

fee-check:            ## old number check against the claim check (no LLM calls)
	uv run python -m evals.fee_check

guardrail-check:      ## false-positive check of guardrail rules on real messages
	uv run python -m evals.guardrail_check

simulate:             ## replay 200 mining-pool messages through the running API
	uv run python -m ab.simulate --limit 200 --run sim1

eval-answers:         ## run eval set v1 through the app and write the report (uses Groq quota)
	uv run python -m evals.run_eval

human-review:         ## review tool for a PERSON: round 3 (rounds 1 and 2 were done by a second AI)
	uv run python -m evals.human_review --round $(or $(ROUND),3)

judge-live:           ## judge faithfulness on a sample of stored replies (uses Groq quota)
	uv run python -m evals.judge_live --limit 40

traffic-report:       ## summarise the production signals stored in the database
	uv run python -m evals.traffic_report --source simulation

loop-mine:            ## data loop: write the review queue from stored turns
	uv run python -m loop.mine

loop-review:          ## data loop: label the queue (for a person)
	uv run python -m loop.review

loop-promote:         ## data loop: build the next eval set from the labels
	uv run python -m loop.promote

loop-holdout:         ## never-mined messages, before and after cycle 1 (uses Groq quota)
	uv run python -m loop.holdout --kb before
	uv run python -m loop.holdout --kb after

loop-report:          ## data loop report (no LLM calls)
	uv run python -m loop.report

KB_BEFORE = SUPPORTLOOP_KB_DIR=data/cache/kb_before SUPPORTLOOP_INDEX_DIR=data/cache/index_before

loop-before:          ## eval v2 on the knowledge base as it was before cycle 1 (uses Groq quota)
	uv run python -m loop.kb_before
	$(KB_BEFORE) uv run python -m scripts.ingest
	$(KB_BEFORE) uv run python -m evals.run_eval --eval-set evals/sets/v2.jsonl --tag kb-before

ab-analyze:           ## A/B report and decision for prompt v2 (no LLM calls)
	uv run python -m ab.analyze
