"""A scripted provider for tests and CI. No network, no API key."""

import json
import re
from typing import Any

from app.llm.base import LLMRequest, LLMResponse


class FakeProvider:
    """Returns scripted replies, or a simple valid answer built from the prompt.

    Scripted items are used in order. An exception in the list is raised instead of
    returned, which lets tests simulate provider failures.
    """

    name = "fake"
    model = "fake-llm"

    def __init__(self, script: list[str | Exception] | None = None) -> None:
        self._script = list(script or [])
        self.requests: list[LLMRequest] = []

    def build_payload(self, request: LLMRequest) -> dict[str, Any]:
        """Build a stand-in request body."""
        return {"model": self.model, **request.model_dump(exclude={"prompt_version"})}

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Return the next scripted reply."""
        self.requests.append(request)
        if self._script:
            item = self._script.pop(0)
            if isinstance(item, Exception):
                raise item
            text = item
        else:
            text = self._default_reply(request)
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            input_tokens=sum(len(m.content.split()) for m in request.messages),
            output_tokens=len(text.split()),
            latency_ms=1.0,
        )

    @staticmethod
    def _default_reply(request: LLMRequest) -> str:
        article_ids = re.findall(r'<article id="([^"]+)"', request.messages[-1].content)
        if not article_ids:
            return json.dumps({"behavior": "escalate", "answer": "", "cited_article_ids": []})
        return json.dumps(
            {
                "behavior": "answer",
                "answer": "Please see the cited help article.",
                "cited_article_ids": article_ids[:1],
            }
        )
