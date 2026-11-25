"""After a reply is made, record it: metrics first, then the database."""

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.chat.pipeline import ChatResult, TurnTrace
from app.guardrails.pii import redact
from app.observability.metrics import Metrics
from app.storage.db import Turn
from app.storage.repository import Repository
from app.storage.signals import SYSTEM_ERRORS, signals_for_turn

logger = logging.getLogger("supportloop.recorder")


class TurnRecorder:
    """Used by the API only. Eval runs call the pipeline directly, so they never mix
    test traffic into the live database or metrics."""

    def __init__(self, repository: Repository, metrics: Metrics, threshold: float) -> None:
        self.repository = repository
        self.metrics = metrics
        self._threshold = threshold

    def record(
        self,
        user_id: str,
        source: str,
        kb_fingerprint: str,
        result: ChatResult,
        trace: TurnTrace,
    ) -> None:
        """Never raises for database problems: the customer must still get the reply."""
        provider, model = result.model.split(":", 1)
        llm = trace.llm or {}
        self._count(result, trace)
        top_score = trace.top_score
        turn = Turn(
            request_id=result.request_id,
            user_id=user_id,
            conversation_id=result.conversation_id,
            source=source,
            redacted_message=trace.redacted_message,
            retrieval_query=trace.retrieval_query,
            retrieved=trace.retrieved,
            context=trace.context,
            top_score=top_score,
            answer=redact(result.answer).text,
            model_reply=None if trace.model_reply is None else redact(trace.model_reply).text,
            behavior=result.behavior,
            cited_article_ids=[c.article_id for c in result.citations],
            confidence=result.confidence,
            escalate=result.escalate,
            escalation_reasons=result.escalation_reasons,
            guardrail_events=result.guardrail_events,
            prompt_version=result.prompt_version,
            provider=provider,
            model=model,
            variant=result.variant,
            kb_fingerprint=kb_fingerprint,
            latency_ms=trace.latency_ms,
            llm_latency_ms=llm.get("latency_ms"),
            llm_wait_ms=llm.get("wait_ms"),
            input_tokens=llm.get("input_tokens"),
            output_tokens=llm.get("output_tokens"),
            llm_cached=llm.get("cached"),
        )
        signals = signals_for_turn(
            escalate=result.escalate,
            top_score=top_score,
            threshold=self._threshold,
            guardrail_events=result.guardrail_events,
        )
        try:
            self.repository.save_turn(turn, signals)
        except SQLAlchemyError as error:
            # Only the error type: the message can contain the row's values.
            self.metrics.errors.labels(result.model, result.variant, "storage").inc()
            logger.error("storage_error", extra={"fields": {"error": type(error).__name__}})

    def _count(self, result: ChatResult, trace: TurnTrace) -> None:
        labels = (result.model, result.variant)
        self.metrics.requests.labels(*labels, result.behavior).inc()
        self.metrics.latency.labels(*labels).observe(trace.latency_ms / 1000)
        if result.escalate:
            self.metrics.escalations.labels(*labels).inc()
        for event in result.guardrail_events:
            if event in SYSTEM_ERRORS:
                self.metrics.errors.labels(*labels, event).inc()
            else:
                self.metrics.guardrails.labels(*labels, event).inc()
        llm = trace.llm or {}
        if not llm.get("cached"):  # a cached reply used no tokens now
            for direction in ("input", "output"):
                tokens = llm.get(f"{direction}_tokens")
                if tokens:
                    self.metrics.tokens.labels(*labels, direction).inc(tokens)
