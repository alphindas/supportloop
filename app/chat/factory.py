"""Assemble a ChatService from settings."""

import logging
from pathlib import Path

import httpx
from opentelemetry import trace as otel

from ab.assign import load_experiment
from app.chat.pipeline import ChatService
from app.config import Settings
from app.guardrails.claims import load_facts
from app.guardrails.rules import load_guardrails
from app.llm.base import LLMProvider
from app.llm.factory import build_provider
from app.prompts.loader import load_messages, load_prompt
from app.rag.chunking import chunk_articles
from app.rag.kb import load_articles
from app.rag.models import build_embedder, build_reranker
from app.rag.retriever import HybridRetriever, RetrievalConfig

logger = logging.getLogger("supportloop.startup")


def build_retriever(settings: Settings) -> tuple[HybridRetriever, dict[str, str]]:
    """Load the knowledge base and models. Returns (retriever, article titles by id)."""
    articles = load_articles(settings.resolve(settings.kb_dir))
    retriever = HybridRetriever(
        chunk_articles(articles, settings.chunk_max_words),
        build_embedder(settings.embedding_model, settings.retrieval_device),
        build_reranker(settings.reranker_model, settings.retrieval_device),
        settings.resolve(settings.index_dir),
        RetrievalConfig(
            settings.bm25_top_k,
            settings.dense_top_k,
            settings.rrf_k,
            settings.rerank_candidates,
            settings.retrieval_mode,
        ),
    )
    return retriever, {article.id: article.title for article in articles}


def build_chat_service(
    settings: Settings,
    client: httpx.AsyncClient,
    provider: LLMProvider | None = None,
    tracer: otel.Tracer | None = None,
) -> ChatService:
    """Create the service. A provider can be passed in by tests."""
    if settings.llm_provider == "ollama" and settings.retrieval_device == "cuda":
        logger.warning(
            "gpu_memory_conflict",
            extra={"fields": {"advice": "set SUPPORTLOOP_RETRIEVAL_DEVICE=cpu with Ollama"}},
        )
    retriever, titles = build_retriever(settings)
    prompts_dir = settings.resolve(settings.prompts_dir)
    injection, escalation = load_guardrails(settings.resolve(settings.guardrails_path))
    return ChatService(
        settings,
        retriever,
        provider or build_provider(settings, client),
        load_prompt(prompts_dir, settings.prompt_version),
        load_messages(prompts_dir, settings.messages_version),
        injection,
        escalation,
        titles,
        tracer,
        load_facts(settings.resolve(settings.money_facts_path))
        if settings.fee_check_enabled
        else None,
    )


def build_variant_services(settings: Settings, base: ChatService) -> tuple[dict, dict | None]:
    """(variant name -> service, experiment). Without an experiment, both are empty.

    Variants share the search models and their lock. Only the settings an experiment
    file names for a variant differ (today: the prompt version).
    """
    if not settings.experiment_path:
        return {}, None
    experiment = load_experiment(settings.resolve(Path(settings.experiment_path)))
    services = {}
    for name, changes in experiment["variants"].items():
        if unknown := set(changes) - {"prompt_version"}:
            raise ValueError(f"A variant cannot change {sorted(unknown)}")
        variant = settings.model_copy(update={**changes, "variant_name": name})
        service = ChatService(
            variant,
            base.retriever,
            base.provider,
            load_prompt(variant.resolve(variant.prompts_dir), variant.prompt_version),
            base.messages,
            base.injection_rules,
            base.escalation_rules,
            base.titles,
            base.tracer,
            base.money_facts,
        )
        service._retrieval_lock = base._retrieval_lock
        services[name] = service
    return services, experiment
