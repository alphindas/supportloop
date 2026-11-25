"""Shared fixtures: the real knowledge base with fake models and a fake LLM."""

from pathlib import Path

import pytest

from app.config import Settings
from app.rag.chunking import chunk_articles
from app.rag.kb import load_articles
from app.rag.models import FakeEmbedder
from app.rag.retriever import build_index


@pytest.fixture(scope="session")
def fake_index(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("index")
    settings = Settings(_env_file=None)
    articles = load_articles(settings.resolve(settings.kb_dir))
    build_index(chunk_articles(articles, settings.chunk_max_words), FakeEmbedder(), directory)
    return directory


@pytest.fixture
def test_settings(fake_index: Path) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="fake",
        llm_cache_enabled=False,
        embedding_model="fake-embedder",
        reranker_model="fake-reranker",
        retrieval_device="cpu",
        index_dir=fake_index,
        escalation_score_threshold=0.3,
        prompt_version="v1",
    )
