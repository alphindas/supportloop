"""Prometheus metrics. Labels are limited to small, fixed sets: never user or request IDs."""

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 20, 40, 90)
BASE = ("model", "variant")


class Metrics:
    """One set of metrics per app instance, so tests do not share counters.

    Counters live in memory and reset when the process restarts. The database keeps the
    permanent record. Works for a single worker process only.
    """

    def __init__(self) -> None:
        self.registry = CollectorRegistry()

        def counter(name: str, help_text: str, extra: tuple[str, ...] = ()) -> Counter:
            return Counter(name, help_text, (*BASE, *extra), registry=self.registry)

        self.requests = counter("supportloop_requests", "Chat replies", ("behavior",))
        # Escalation rate = rate(escalations_total) / rate(requests_total).
        self.escalations = counter("supportloop_escalations", "Replies flagged for a human")
        self.errors = counter("supportloop_errors", "Failures", ("kind",))
        self.guardrails = counter(
            "supportloop_guardrail_triggers", "Guardrail hits", ("guardrail",)
        )
        self.tokens = counter("supportloop_tokens", "LLM tokens", ("direction",))
        self.feedback = counter("supportloop_feedback", "Feedback submissions", ("rating",))
        self.latency = Histogram(
            "supportloop_request_latency_seconds",
            "Time to produce a chat reply",
            BASE,
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

    def render(self) -> bytes:
        """The text Prometheus scrapes."""
        return generate_latest(self.registry)
