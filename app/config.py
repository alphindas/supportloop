"""All application settings, loaded from config/settings.yaml, .env and the environment."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Typed settings. A wrong type or a missing value fails at start-up, not mid-request.

    Priority, highest first: arguments in code, environment variables, .env,
    config/settings.yaml.
    """

    model_config = SettingsConfigDict(
        env_prefix="SUPPORTLOOP_",
        env_file=PROJECT_ROOT / ".env",
        yaml_file=PROJECT_ROOT / "config" / "settings.yaml",
        extra="ignore",
    )

    # SecretStr prints as '**********', so the key cannot leak through a log line.
    groq_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GROQ_API_KEY")

    llm_provider: Literal["groq", "ollama", "fake"]
    groq_base_url: str
    groq_generator_model: str
    groq_judge_model: str
    groq_reasoning_effort: Literal["low", "medium", "high"]
    ollama_base_url: str
    ollama_model: str
    ollama_num_ctx: int = Field(gt=0)
    llm_temperature: float = Field(ge=0, le=2)
    llm_max_output_tokens: int = Field(gt=0)
    llm_timeout_seconds: float = Field(gt=0)
    llm_max_retries: int = Field(ge=0)
    llm_backoff_base_seconds: float = Field(ge=0)
    llm_backoff_max_seconds: float = Field(ge=0)
    llm_max_retry_after_seconds: float = Field(ge=0)
    llm_cache_enabled: bool
    llm_cache_path: Path
    prompt_version: str

    embedding_model: str
    reranker_model: str
    retrieval_device: Literal["cuda", "cpu"]
    kb_dir: Path
    index_dir: Path
    chunk_max_words: int = Field(gt=0)
    bm25_top_k: int = Field(gt=0)
    dense_top_k: int = Field(gt=0)
    rrf_k: int = Field(gt=0)
    rerank_candidates: int = Field(gt=0)
    context_top_k: int = Field(gt=0)

    escalation_score_threshold: float = Field(ge=0, le=1)
    max_message_chars: int = Field(gt=0)
    history_turns: int = Field(ge=0)
    guardrails_path: Path

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Add the YAML file as the lowest-priority source."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    def resolve(self, path: Path) -> Path:
        """Turn a project-relative path into an absolute one."""
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them."""
    return Settings()
