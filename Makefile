.PHONY: setup test lint format check run ingest retrieval-eval benchmark-retrieval benchmark-llm eval samples

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
