"""The FastAPI application."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST
from pydantic import BaseModel, ConfigDict, Field

from app.chat.factory import build_chat_service
from app.chat.pipeline import ChatResult, ChatService
from app.chat.recorder import TurnRecorder
from app.config import Settings, get_settings
from app.guardrails.pii import redact
from app.observability.logging import configure_logging
from app.observability.metrics import Metrics
from app.observability.tracing import build_tracer_provider
from app.storage.db import create_database
from app.storage.repository import Repository

# IDs are limited to safe characters, so an email or free text cannot be used as an ID
# and end up in the logs.
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    """Body of POST /chat."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(pattern=ID_PATTERN)
    user_id: str = Field(pattern=ID_PATTERN)
    message: str = Field(min_length=1)


class FeedbackRequest(BaseModel):
    """Body of POST /feedback."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    user_id: str = Field(pattern=ID_PATTERN)
    rating: Literal["up", "down"]
    comment: str | None = None


def create_app(settings: Settings | None = None, service: ChatService | None = None) -> FastAPI:
    """Build the app. Tests pass in their own settings or service."""
    settings = settings or get_settings()
    configure_logging()

    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Models load once at start-up, not on the first customer's request.
        engine = create_database(settings.resolve(settings.database_path))
        tracing = build_tracer_provider(settings)
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            app.state.service = service or build_chat_service(
                settings, client, tracer=tracing.get_tracer("supportloop")
            )
            app.state.recorder = TurnRecorder(
                Repository(engine), metrics, settings.escalation_score_threshold
            )
            yield
        tracing.shutdown()  # send any spans still waiting
        engine.dispose()

    app = FastAPI(title="SupportLoop: NovaPay support assistant", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # FastAPI's default reply repeats the input, which may contain personal data.
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]}
            for e in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": details})

    @app.post("/chat", response_model=ChatResult)
    async def chat(
        body: ChatRequest,
        request: Request,
        source: Literal["live", "simulation", "sample"] = Header(
            "live", alias="X-SupportLoop-Source"
        ),
    ) -> ChatResult:
        """Answer one customer message. The header only labels where traffic came from."""
        if len(body.message) > settings.max_message_chars:
            raise HTTPException(
                422, f"message is longer than {settings.max_message_chars} characters"
            )
        if not body.message.strip():
            raise HTTPException(422, "message is blank")
        chat_service: ChatService = request.app.state.service
        try:
            result, trace = await chat_service.handle(
                body.user_id, body.conversation_id, body.message
            )
        except Exception:
            model = f"{chat_service.provider.name}:{chat_service.provider.model}"
            metrics.errors.labels(model, settings.variant_name, "unhandled").inc()
            raise
        await asyncio.to_thread(
            request.app.state.recorder.record,
            body.user_id,
            source,
            chat_service.retriever.corpus_fingerprint,
            result,
            trace,
        )
        return result

    @app.post("/feedback")
    async def feedback(body: FeedbackRequest, request: Request) -> dict:
        """Thumbs up or down for one reply."""
        if body.comment and len(body.comment) > settings.max_message_chars:
            raise HTTPException(
                422, f"comment is longer than {settings.max_message_chars} characters"
            )
        recorder: TurnRecorder = request.app.state.recorder
        comment = redact(body.comment).text if body.comment else None
        turn = await asyncio.to_thread(
            recorder.repository.save_feedback,
            body.request_id,
            body.user_id,
            body.rating,
            comment,
        )
        if turn is None:
            # Same answer for "no such reply" and "not your reply".
            raise HTTPException(404, "no reply with that request_id for this user")
        metrics.feedback.labels(f"{turn.provider}:{turn.model}", turn.variant, body.rating).inc()
        return {"status": "recorded"}

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        """Metrics for Prometheus to scrape."""
        return Response(metrics.render(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health")
    async def health(request: Request) -> dict:
        """Is the app up, and with which setup? It does not call the LLM (saves quota)."""
        chat_service: ChatService = request.app.state.service
        return {
            "status": "ok",
            "articles": len(chat_service.titles),
            "kb_fingerprint": chat_service.retriever.corpus_fingerprint,
            "llm": f"{chat_service.provider.name}:{chat_service.provider.model}",
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
            "prompt_version": chat_service.prompt.version,
        }

    return app
