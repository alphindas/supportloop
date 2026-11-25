"""Settings load from YAML, accept overrides and hide the API key."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_yaml_defaults_load() -> None:
    settings = Settings(_env_file=None)
    assert settings.rrf_k > 0
    assert settings.context_top_k <= settings.rerank_candidates


def test_environment_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPPORTLOOP_CONTEXT_TOP_K", "7")
    assert Settings(_env_file=None).context_top_k == 7


def test_invalid_value_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPPORTLOOP_LLM_PROVIDER", "somethingelse")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_api_key_is_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "not-a-real-key-123")
    settings = Settings(_env_file=None)
    assert "not-a-real-key-123" not in repr(settings)
    assert settings.groq_api_key.get_secret_value() == "not-a-real-key-123"
