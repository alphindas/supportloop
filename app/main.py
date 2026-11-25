"""The FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.chat.factory import build_chat_service
from app.chat.pipeline import ChatResult, ChatService
from app.config import Settings, get_settings
from app.observability.logging import configure_logging

# IDs are limited to safe characters, so an email or free text cannot be used as an ID
# and end up in the logs.
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    """Body of POST /chat."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(pattern=ID_PATTERN)
    user_id: str = Field(pattern=ID_PATTERN)
    message: str = Field(min_length=1)


def create_app(settings: Settings | None = None, service: ChatService | None = None) -> FastAPI:
    """Build the app. Tests pass in their own settings or service."""
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Models load once at start-up, not on the first customer's request.
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            app.state.service = service or build_chat_service(settings, client)
            yield

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
    async def chat(body: ChatRequest, request: Request) -> ChatResult:
        """Answer one customer message."""
        if len(body.message) > settings.max_message_chars:
            raise HTTPException(
                422, f"message is longer than {settings.max_message_chars} characters"
            )
        if not body.message.strip():
            raise HTTPException(422, "message is blank")
        result, _ = await request.app.state.service.handle(
            body.user_id, body.conversation_id, body.message
        )
        return result

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
