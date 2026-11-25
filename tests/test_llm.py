"""Retries, timeouts, caching and request building. No real network calls."""

import json

import httpx
import pytest

from app.llm.base import (
    LLMError,
    LLMQuotaExceededError,
    LLMRequest,
    Message,
    request_fingerprint,
)
from app.llm.cache import CachedProvider, ResponseCache
from app.llm.fake import FakeProvider
from app.llm.groq import GroqProvider
from app.llm.ollama import OllamaProvider
from app.llm.retry import RetryPolicy, backoff_delay, post_with_retries

POLICY = RetryPolicy(
    max_retries=3, backoff_base_seconds=1, backoff_max_seconds=5, max_retry_after_seconds=90
)
GROQ_OK = {
    "choices": [{"message": {"content": '{"ok": true}'}}],
    "usage": {"prompt_tokens": 11, "completion_tokens": 3},
}


def request(content: str = "hello", prompt_version: str = "v1") -> LLMRequest:
    return LLMRequest(
        messages=[Message(role="user", content=content)],
        prompt_version=prompt_version,
        temperature=0,
        max_output_tokens=50,
        schema_name="s",
        json_schema={"type": "object"},
    )


def client_returning(*outcomes: httpx.Response | Exception) -> tuple[httpx.AsyncClient, list]:
    queue, seen = list(outcomes), []

    def handler(incoming: httpx.Request) -> httpx.Response:
        seen.append(incoming)
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


async def run_post(client: httpx.AsyncClient) -> tuple[httpx.Response, list[float], float]:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    response, _, wait_ms = await post_with_retries(
        client, "https://example.test/x", {}, POLICY, sleep=fake_sleep, jitter=lambda: 1.0
    )
    return response, sleeps, wait_ms


async def test_retries_429_using_retry_after() -> None:
    client, seen = client_returning(
        httpx.Response(429, headers={"retry-after": "7"}), httpx.Response(200)
    )
    response, sleeps, wait_ms = await run_post(client)
    assert response.status_code == 200 and len(seen) == 2
    assert sleeps == [7.0] and wait_ms == 7000


async def test_server_errors_and_timeouts_back_off_exponentially() -> None:
    client, _ = client_returning(
        httpx.Response(503), httpx.ReadTimeout("slow"), httpx.Response(500), httpx.Response(200)
    )
    _, sleeps, _ = await run_post(client)
    assert sleeps == [1, 2, 4]


def test_backoff_is_capped_and_jittered() -> None:
    assert backoff_delay(10, POLICY, jitter=lambda: 1.0) == 5
    assert backoff_delay(10, POLICY, jitter=lambda: 0.0) == 2.5


async def test_gives_up_after_max_retries() -> None:
    client, seen = client_returning(*[httpx.Response(500)] * 4)
    with pytest.raises(LLMError, match="Gave up after 4 attempts"):
        await run_post(client)
    assert len(seen) == 4


async def test_client_errors_are_not_retried() -> None:
    client, seen = client_returning(httpx.Response(401, text="bad key"))
    with pytest.raises(LLMError, match="401"):
        await run_post(client)
    assert len(seen) == 1


async def test_long_retry_after_means_quota_is_used_up() -> None:
    client, _ = client_returning(httpx.Response(429, headers={"retry-after": "3600"}))
    with pytest.raises(LLMQuotaExceededError) as caught:
        await run_post(client)
    assert caught.value.retry_after_seconds == 3600


async def test_groq_payload_and_parsing() -> None:
    client, seen = client_returning(httpx.Response(200, json=GROQ_OK))
    provider = GroqProvider(
        "m", "secret-key", "https://g.test/v1", client, POLICY, {"reasoning_effort": "low"}
    )
    response = await provider.complete(request())
    sent = json.loads(seen[0].content)
    assert sent["reasoning_effort"] == "low"
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert seen[0].headers["authorization"] == "Bearer secret-key"
    assert (response.input_tokens, response.output_tokens) == (11, 3)


async def test_error_messages_never_contain_the_key() -> None:
    client, _ = client_returning(httpx.Response(400, text="bad request"))
    provider = GroqProvider("m", "secret-key", "https://g.test/v1", client, POLICY)
    with pytest.raises(LLMError) as caught:
        await provider.complete(request())
    assert "secret-key" not in str(caught.value)


def test_groq_needs_a_key() -> None:
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqProvider("m", "", "https://g.test", httpx.AsyncClient(), POLICY)


async def test_ollama_payload_sets_context_size_and_schema() -> None:
    client, seen = client_returning(
        httpx.Response(
            200, json={"message": {"content": "hi"}, "prompt_eval_count": 5, "eval_count": 1}
        )
    )
    provider = OllamaProvider("m", "http://o.test", client, POLICY, 4096, {"think": False})
    response = await provider.complete(request())
    sent = json.loads(seen[0].content)
    assert sent["options"]["num_ctx"] == 4096 and sent["think"] is False
    assert sent["format"] == {"type": "object"}
    assert response.text == "hi" and response.input_tokens == 5


async def test_cache_returns_same_text_and_original_latency(tmp_path) -> None:
    inner = FakeProvider(script=["first", "second"])
    provider = CachedProvider(inner, ResponseCache(tmp_path / "c.sqlite3"))
    first = await provider.complete(request())
    second = await provider.complete(request())
    assert (first.cached, second.cached) == (False, True)
    assert second.text == "first" and second.latency_ms == first.latency_ms
    assert len(inner.requests) == 1


async def test_failures_are_not_cached(tmp_path) -> None:
    inner = FakeProvider(script=[LLMError("boom"), "fine"])
    provider = CachedProvider(inner, ResponseCache(tmp_path / "c.sqlite3"))
    with pytest.raises(LLMError):
        await provider.complete(request())
    assert (await provider.complete(request())).text == "fine"


def test_cache_key_changes_with_context_and_prompt_version() -> None:
    provider = FakeProvider()
    base = request_fingerprint(provider, request("question + article: fee is 5"))
    assert base != request_fingerprint(provider, request("question + article: fee is 6"))
    assert base != request_fingerprint(
        provider, request("question + article: fee is 5", prompt_version="v2")
    )
