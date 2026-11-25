"""Groq, through its OpenAI-compatible chat completions API."""

from typing import Any

import httpx

from app.llm.base import LLMError, LLMRequest, LLMResponse
from app.llm.retry import RetryPolicy, post_with_retries


class GroqProvider:
    """Calls a hosted model on Groq."""

    name = "groq"

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        client: httpx.AsyncClient,
        policy: RetryPolicy,
        model_params: dict[str, Any] | None = None,
    ) -> None:
        if not api_key:
            raise LLMError("GROQ_API_KEY is empty. Add it to .env (see .env.example).")
        self.model = model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client
        self._policy = policy
        self._model_params = model_params or {}

    def build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Build the request body."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
            "max_completion_tokens": request.max_output_tokens,
            **self._model_params,
        }
        if request.json_schema is not None:
            # strict=True makes Groq constrain the output to the schema.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name or "response",
                    "strict": True,
                    "schema": request.json_schema,
                },
            }
        return payload

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send the request, retrying when it makes sense."""
        response, latency_ms, wait_ms = await post_with_retries(
            self._client, self._url, self.build_payload(request), self._policy, self._headers
        )
        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"] or ""
            usage = body.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise LLMError(f"Unexpected response shape from Groq: {error!r}") from error
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=latency_ms,
            wait_ms=wait_ms,
        )
