"""POST with retries: exponential backoff on rate limits, server errors and timeouts."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.llm.base import LLMError, LLMQuotaExceededError

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try. All values come from settings."""

    max_retries: int
    backoff_base_seconds: float
    backoff_max_seconds: float
    max_retry_after_seconds: float


def backoff_delay(attempt: int, policy: RetryPolicy, jitter: Callable[[], float]) -> float:
    """Double the wait each time, up to a cap.

    The random part ("jitter") stops many clients from retrying at the same instant.
    """
    ceiling = min(policy.backoff_max_seconds, policy.backoff_base_seconds * 2**attempt)
    return ceiling * (0.5 + 0.5 * jitter())


def retry_after_seconds(response: httpx.Response) -> float | None:
    """Read the server's 'retry-after' header, if it is a number of seconds."""
    try:
        return float(response.headers["retry-after"])
    except (KeyError, ValueError):
        return None


async def post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    policy: RetryPolicy,
    headers: dict[str, str] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    jitter: Callable[[], float] = random.random,
) -> tuple[httpx.Response, float, float]:
    """Return (successful response, latency_ms of that attempt, total wait_ms).

    Raises LLMQuotaExceededError if the server asks for a very long wait (a daily
    quota), and LLMError for other failures. Error messages never include headers,
    so the API key cannot end up in a log.
    """
    waited = 0.0
    for attempt in range(policy.max_retries + 1):
        server_delay: float | None = None
        started = time.perf_counter()
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.TransportError as error:  # includes timeouts and refused connections
            problem = type(error).__name__
        else:
            latency_ms = (time.perf_counter() - started) * 1000
            if response.is_success:
                return response, latency_ms, waited * 1000
            if response.status_code not in RETRYABLE_STATUS:
                # A 400 or 401 will fail the same way again, so do not retry it.
                raise LLMError(f"HTTP {response.status_code}: {response.text[:300]}")
            problem = f"HTTP {response.status_code}"
            server_delay = retry_after_seconds(response)
            if server_delay is not None and server_delay > policy.max_retry_after_seconds:
                raise LLMQuotaExceededError(
                    f"{problem}: server asks to wait {server_delay:.0f}s", server_delay
                )

        if attempt == policy.max_retries:
            raise LLMError(f"Gave up after {attempt + 1} attempts; last problem: {problem}")
        delay = server_delay if server_delay is not None else backoff_delay(attempt, policy, jitter)
        await sleep(delay)
        waited += delay
    raise AssertionError("unreachable")
