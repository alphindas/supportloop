"""The small interface every LLM provider follows."""

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel


class Message(BaseModel):
    """One chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMRequest(BaseModel):
    """A provider-independent request."""

    messages: list[Message]
    prompt_version: str
    temperature: float
    max_output_tokens: int
    schema_name: str | None = None
    json_schema: dict[str, Any] | None = None


class LLMResponse(BaseModel):
    """What came back, with the numbers we report."""

    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float  # the successful attempt only
    wait_ms: float = 0.0  # time spent backing off before it, e.g. after a rate limit
    cached: bool = False


class LLMError(Exception):
    """The provider could not give us a usable response."""


class LLMQuotaExceededError(LLMError):
    """The provider asks us to wait so long that retrying now is pointless."""

    def __init__(self, message: str, retry_after_seconds: float) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LLMProvider(Protocol):
    """Anything that can answer an LLMRequest."""

    name: str
    model: str

    def build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """The exact body that will be sent. It is also what the cache key is made from."""
        ...

    async def complete(self, request: LLMRequest) -> LLMResponse: ...


def request_fingerprint(provider: LLMProvider, request: LLMRequest) -> str:
    """Hash of the whole request: provider, prompt version and every field we send.

    Retrieved article text is part of the messages, so changing an article changes
    the key and an out-of-date answer can never be returned.
    """
    material = {
        "provider": provider.name,
        "prompt_version": request.prompt_version,
        "payload": provider.build_payload(request),
    }
    encoded = json.dumps(material, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()
