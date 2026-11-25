"""A local model served by Ollama."""

from typing import Any

import httpx

from app.llm.base import LLMError, LLMRequest, LLMResponse
from app.llm.retry import RetryPolicy, post_with_retries


class OllamaProvider:
    """Calls a model running on this machine."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str,
        client: httpx.AsyncClient,
        policy: RetryPolicy,
        num_ctx: int,
        model_params: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._policy = policy
        self._num_ctx = num_ctx
        self._model_params = model_params or {}

    def build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Build the request body."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_output_tokens,
                # Set explicitly: a small default would silently cut off the articles.
                "num_ctx": self._num_ctx,
                "seed": 0,
            },
            **self._model_params,
        }
        if request.json_schema is not None:
            payload["format"] = request.json_schema
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send the request to the local server."""
        response, latency_ms, wait_ms = await post_with_retries(
            self._client, f"{self._base_url}/api/chat", self.build_payload(request), self._policy
        )
        try:
            body = response.json()
            text = body["message"]["content"]
        except (ValueError, KeyError, TypeError) as error:
            raise LLMError(f"Unexpected response shape from Ollama: {error!r}") from error
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=body.get("prompt_eval_count"),
            output_tokens=body.get("eval_count"),
            latency_ms=latency_ms,
            wait_ms=wait_ms,
        )
