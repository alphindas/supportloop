"""A SQLite cache of LLM responses, so eval reruns are cheap and give the same text."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.llm.base import LLMProvider, LLMRequest, LLMResponse, request_fingerprint


class ResponseCache:
    """Stores one response per request fingerprint."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache ("
                "key TEXT PRIMARY KEY, created_at TEXT, provider TEXT, model TEXT, "
                "prompt_version TEXT, response_json TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path, timeout=30)

    def get(self, key: str) -> LLMResponse | None:
        """Look up a stored response."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT response_json FROM llm_cache WHERE key = ?", (key,)
            ).fetchone()
        return LLMResponse.model_validate_json(row[0]) if row else None

    def put(self, key: str, prompt_version: str, response: LLMResponse) -> None:
        """Store a response. The first one stored wins."""
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO llm_cache VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    datetime.now(UTC).isoformat(),
                    response.provider,
                    response.model,
                    prompt_version,
                    response.model_dump_json(),
                ),
            )


class CachedProvider:
    """Wraps a provider. A cached reply keeps the ORIGINAL latency and token counts,
    so reports never show the time of a cache lookup as model latency."""

    def __init__(self, inner: LLMProvider, cache: ResponseCache) -> None:
        self._inner = inner
        self._cache = cache
        self.name = inner.name
        self.model = inner.model

    def build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Same body as the wrapped provider."""
        return self._inner.build_payload(request)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a cached reply if there is one, otherwise call the provider."""
        key = request_fingerprint(self._inner, request)
        stored = self._cache.get(key)
        if stored is not None:
            return stored.model_copy(update={"cached": True})
        response = await self._inner.complete(request)
        # Failed calls raise before this line, so errors are never cached.
        self._cache.put(key, request.prompt_version, response)
        return response
