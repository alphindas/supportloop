.PHONY: setup test lint format check data ingest run retrieval-eval benchmark-retrieval benchmark-llm eval review-pairs samples guardrail-check

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

benchmark-llm:        ## compare local chat models (needs Ollama; uses some Groq quota)
	uv run python -m evals.benchmark_llm

retrieval-eval:       ## evaluate retrieval on the held-out split and write the report
	uv run python -m evals.retrieval_eval

review-pairs:         ## review AI-drafted retrieval labels by hand
	uv run python -m scripts.review_pairs

eval: retrieval-eval  ## Phase 2 adds the full answer evaluation here

samples:              ## send 10 sample conversations to the running API (make run first)
	uv run python -m scripts.sample_conversations

guardrail-check:      ## false-positive check of guardrail rules on real messages
	uv run python -m evals.guardrail_check
