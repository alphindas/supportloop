"""Build the provider named in settings."""

from typing import Any

import httpx

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.cache import CachedProvider, ResponseCache
from app.llm.fake import FakeProvider
from app.llm.groq import GroqProvider
from app.llm.ollama import OllamaProvider
from app.llm.retry import RetryPolicy
from app.rag.models import load_model_config


def llm_params(provider: str, model: str) -> dict[str, Any]:
    """Model-specific request fields from config/models.yaml."""
    return dict(load_model_config().get("llm", {}).get(provider, {}).get(model, {}))


def build_provider(
    settings: Settings,
    client: httpx.AsyncClient,
    provider: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    """Create a provider, wrapped in the cache if caching is switched on."""
    provider = provider or settings.llm_provider
    if provider == "fake":
        return FakeProvider()
    policy = RetryPolicy(
        settings.llm_max_retries,
        settings.llm_backoff_base_seconds,
        settings.llm_backoff_max_seconds,
        settings.llm_max_retry_after_seconds,
    )
    built: LLMProvider
    if provider == "groq":
        model = model or settings.groq_generator_model
        built = GroqProvider(
            model,
            settings.groq_api_key.get_secret_value(),
            settings.groq_base_url,
            client,
            policy,
            llm_params("groq", model),
        )
    else:
        model = model or settings.ollama_model
        built = OllamaProvider(
            model,
            settings.ollama_base_url,
            client,
            policy,
            settings.ollama_num_ctx,
            llm_params("ollama", model),
        )
    if settings.llm_cache_enabled:
        return CachedProvider(built, ResponseCache(settings.resolve(settings.llm_cache_path)))
    return built
