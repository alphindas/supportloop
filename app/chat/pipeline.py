"""One chat turn: redact, check, retrieve, generate, verify, decide."""

import asyncio
import json
import logging
import time
import uuid

from opentelemetry import trace as otel
from opentelemetry.trace import SpanKind, Status, StatusCode
from pydantic import BaseModel

from app.chat.history import ConversationStore, Turn
from app.config import Settings
from app.guardrails.claims import Fact
from app.guardrails.output import BotAnswer, bot_answer_schema, check_answer, parse_bot_answer
from app.guardrails.pii import redact
from app.guardrails.rules import RuleSet
from app.llm.base import LLMError, LLMProvider, LLMRequest, LLMResponse, Message
from app.observability import semconv
from app.prompts.loader import PromptTemplate
from app.rag.retriever import HybridRetriever, RetrievedChunk

logger = logging.getLogger("supportloop.chat")


class Citation(BaseModel):
    """An article the answer relies on."""

    article_id: str
    title: str


class ChatResult(BaseModel):
    """What the API returns."""

    request_id: str
    conversation_id: str
    behavior: str  # answer | escalate | refuse
    answer: str
    citations: list[Citation]
    confidence: float  # top reranker score; NOT a probability that the answer is right
    escalate: bool
    escalation_reasons: list[str]
    guardrail_events: list[str]
    model: str
    prompt_version: str
    variant: str


class TurnTrace(BaseModel):
    """Everything about a turn that is useful for debugging. Contains no raw PII."""

    redacted_message: str
    retrieval_query: str = ""
    retrieved: list[dict] = []
    context: dict[str, str] = {}  # article id -> text shown to the model
    top_score: float | None = None
    llm: dict | None = None
    model_reply: str | None = None
    latency_ms: float = 0.0


def neutralise(text: str) -> str:
    """Stop user text from opening or closing the tags that structure the prompt."""
    return text.replace("<", "‹").replace(">", "›")


def format_articles(chunks: list[RetrievedChunk]) -> dict[str, str]:
    """Group retrieved chunks by article, keeping rank order. Returns id -> shown text."""
    grouped: dict[str, list[str]] = {}
    for item in chunks:
        grouped.setdefault(item.chunk.article_id, []).append(item.chunk.text)
    return {article_id: "\n\n".join(texts) for article_id, texts in grouped.items()}


def build_llm_request(
    settings: Settings,
    prompt: PromptTemplate,
    question: str,
    history: list[Turn],
    article_texts: dict[str, str],
) -> LLMRequest:
    """Fill the prompt template. Used by the app and by the model benchmark."""
    articles = "\n\n".join(
        f'<article id="{article_id}">\n{text}\n</article>'
        for article_id, text in article_texts.items()
    )
    past = "\n".join(
        f"Customer: {neutralise(t.question)}\nAssistant: {neutralise(t.answer)}" for t in history
    )
    user = prompt.user.substitute(
        articles=articles or "(no articles found)",
        history=past or "(none)",
        question=neutralise(question),
    )
    return LLMRequest(
        messages=[
            Message(role="system", content=prompt.system),
            Message(role="user", content=user),
        ],
        prompt_version=prompt.version,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        schema_name="bot_answer",
        json_schema=bot_answer_schema(),
    )


def _mark_failed(span: otel.Span, error: Exception) -> None:
    """Record only the error type. Error messages could contain request text."""
    span.set_attribute(semconv.ERROR_TYPE, type(error).__name__)
    span.set_status(Status(StatusCode.ERROR))


class ChatService:
    """Runs the pipeline. All dependencies are passed in, so tests can swap them."""

    def __init__(
        self,
        settings: Settings,
        retriever: HybridRetriever,
        provider: LLMProvider,
        prompt: PromptTemplate,
        messages: dict[str, str],
        injection_rules: RuleSet,
        escalation_rules: RuleSet,
        titles: dict[str, str],
        tracer: otel.Tracer | None = None,
        money_facts: dict[str, list[Fact]] | None = None,
    ) -> None:
        self.money_facts = money_facts  # None switches the claim check off
        self.tracer = tracer or otel.NoOpTracer()
        self.settings = settings
        self.retriever = retriever
        self.provider = provider
        self.prompt = prompt
        self.messages = messages
        self.injection_rules = injection_rules
        self.escalation_rules = escalation_rules
        self.titles = titles
        self.history = ConversationStore(settings.history_turns, settings.max_conversations)
        # There is one GPU, so only one retrieval runs at a time.
        self._retrieval_lock = asyncio.Lock()

    async def handle(
        self, user_id: str, conversation_id: str, message: str
    ) -> tuple[ChatResult, TurnTrace]:
        """Answer one customer message. The whole turn is one trace."""
        with self.tracer.start_as_current_span("chat_request", kind=SpanKind.SERVER) as span:
            span.set_attribute(semconv.CONVERSATION_ID, conversation_id)
            span.set_attribute(semconv.VARIANT, self.settings.variant_name)
            span.set_attribute(semconv.PROMPT_VERSION, self.prompt.version)
            result, trace = await self._run(user_id, conversation_id, message)
            span.set_attribute(semconv.REQUEST_ID, result.request_id)
            span.set_attribute(semconv.BEHAVIOR, result.behavior)
            span.set_attribute(semconv.ESCALATE, result.escalate)
            return result, trace

    async def _run(
        self, user_id: str, conversation_id: str, message: str
    ) -> tuple[ChatResult, TurnTrace]:
        started = time.perf_counter()
        with self.tracer.start_as_current_span("guardrail input") as span:
            # Redaction comes first. The raw message is not used again after this line.
            redaction = redact(message)
            question = redaction.text
            events = [f"pii_redacted:{kind}" for kind in sorted(redaction.counts)]
            injections = self.injection_rules.matches(question)
            span.set_attribute(semconv.PII_KINDS, sorted(redaction.counts))
            span.set_attribute(semconv.INJECTION_RULES, injections)
        trace = TurnTrace(redacted_message=question)

        if injections:
            events += [f"prompt_injection:{name}" for name in injections]
            # Not added to history, so the attack text never reaches a later prompt.
            result = self._result(
                conversation_id, "refuse", self.messages["refuse_injection"], events=events
            )
            return self._finish(user_id, result, trace, started)

        history = self.history.get(user_id, conversation_id)
        # Follow-ups such as "what does it cost?" need the previous question to search.
        query = f"{history[-1].question}\n{question}" if history else question
        trace.retrieval_query = query
        rule_hits = self.escalation_rules.matches(question)
        try:
            chunks = await self._retrieve(query)
        except RuntimeError as error:  # e.g. the GPU ran out of memory
            return self._system_failure(
                user_id, conversation_id, "retrieval_error", error, rule_hits, events,
                trace, started,
            )  # fmt: skip
        trace.retrieved = [
            {
                "chunk_id": c.chunk.chunk_id,
                "bm25_rank": c.bm25_rank,
                "dense_rank": c.dense_rank,
                "rrf_score": round(c.rrf_score, 5),
                "rerank_score": None if c.rerank_score is None else round(c.rerank_score, 4),
            }
            for c in chunks
        ]
        article_texts = format_articles(chunks)
        trace.context = article_texts
        trace.top_score = chunks[0].rerank_score if chunks else None

        request = build_llm_request(self.settings, self.prompt, question, history, article_texts)
        try:
            response = await self._generate(conversation_id, request)
        except LLMError as error:
            return self._system_failure(
                user_id, conversation_id, "llm_error", error, rule_hits, events, trace, started
            )

        trace.llm = response.model_dump(exclude={"text"})
        trace.model_reply = redact(response.text).text
        with self.tracer.start_as_current_span("guardrail output") as span:
            result = self._decide(
                conversation_id,
                question,
                response,
                article_texts,
                trace.top_score,
                rule_hits,
                events,
            )
            span.set_attribute(semconv.GUARDRAIL_EVENTS, result.guardrail_events)
            span.set_attribute(semconv.BEHAVIOR, result.behavior)
        self.history.add(user_id, conversation_id, Turn(question, redact(result.answer).text))
        return self._finish(user_id, result, trace, started)

    async def _retrieve(self, query: str) -> list[RetrievedChunk]:
        with self.tracer.start_as_current_span(
            "retrieval", record_exception=False, set_status_on_exception=False
        ) as span:
            span.set_attribute(semconv.OPERATION_NAME, "retrieval")
            span.set_attribute(semconv.RETRIEVAL_TOP_K, self.settings.context_top_k)
            try:
                async with self._retrieval_lock:
                    chunks = await asyncio.to_thread(
                        self.retriever.retrieve, query, self.settings.context_top_k
                    )
            except RuntimeError as error:
                _mark_failed(span, error)
                raise
            # Chunk IDs and scores only. The query text is left out on purpose.
            documents = [
                {"id": c.chunk.chunk_id, "score": c.rerank_score or c.rrf_score} for c in chunks
            ]
            span.set_attribute(semconv.RETRIEVAL_DOCUMENTS, json.dumps(documents))
            return chunks

    async def _generate(self, conversation_id: str, request: LLMRequest) -> LLMResponse:
        with self.tracer.start_as_current_span(
            f"chat {self.provider.model}",
            kind=SpanKind.CLIENT,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            span.set_attributes(
                {
                    semconv.OPERATION_NAME: "chat",
                    semconv.PROVIDER_NAME: self.provider.name,
                    semconv.REQUEST_MODEL: self.provider.model,
                    semconv.REQUEST_TEMPERATURE: request.temperature,
                    semconv.REQUEST_MAX_TOKENS: request.max_output_tokens,
                    semconv.OUTPUT_TYPE: "json",
                    semconv.PROMPT_NAME: "supportloop_chat",
                    semconv.PROMPT_VERSION: request.prompt_version,
                    semconv.CONVERSATION_ID: conversation_id,
                }
            )
            try:
                response = await self.provider.complete(request)
            except LLMError as error:
                _mark_failed(span, error)
                raise
            span.set_attribute(semconv.RESPONSE_MODEL, response.model)
            span.set_attribute(semconv.LLM_CACHED, response.cached)
            span.set_attribute(semconv.LLM_WAIT_MS, response.wait_ms)
            if response.input_tokens is not None:
                span.set_attribute(semconv.USAGE_INPUT_TOKENS, response.input_tokens)
            if response.output_tokens is not None:
                span.set_attribute(semconv.USAGE_OUTPUT_TOKENS, response.output_tokens)
            return response

    def _system_failure(
        self,
        user_id: str,
        conversation_id: str,
        kind: str,
        error: Exception,
        rule_hits: list[str],
        events: list[str],
        trace: TurnTrace,
        started: float,
    ) -> tuple[ChatResult, TurnTrace]:
        """Something broke. The customer is handed to a person instead of seeing an error."""
        logger.warning(kind, extra={"fields": {"error": str(error)[:300]}})
        result = self._result(
            conversation_id,
            "escalate",
            self.messages["escalate"],
            reasons=[kind, *[f"rule:{r}" for r in rule_hits]],
            events=[*events, kind],
        )
        return self._finish(user_id, result, trace, started)

    def _decide(
        self,
        conversation_id: str,
        question: str,
        response: LLMResponse,
        article_texts: dict[str, str],
        top_score: float | None,
        rule_hits: list[str],
        events: list[str],
    ) -> ChatResult:
        """Turn the model's reply into the final result. When in doubt, hand off."""
        confidence = top_score or 0.0
        rule_reasons = [f"rule:{name}" for name in rule_hits]
        reply: BotAnswer | None = parse_bot_answer(response.text)
        problems = (
            ["invalid_json"]
            if reply is None
            else check_answer(reply, article_texts, question, self.money_facts)
        )
        if reply is None or problems:
            events += [f"output_check:{p}" for p in problems]
            return self._result(
                conversation_id,
                "escalate",
                self.messages["escalate"],
                reasons=[*[f"output_check:{p}" for p in problems], *rule_reasons],
                events=events,
            )

        if reply.behavior == "refuse" and not rule_hits:
            return self._result(
                conversation_id,
                "refuse",
                self.messages["refuse_out_of_scope"],
                confidence=confidence,
                events=[*events, "out_of_scope"],
            )

        reasons = list(rule_reasons)
        if reply.behavior == "escalate":
            reasons.insert(0, "model_chose_escalate")
        if reply.behavior == "refuse":
            reasons.insert(0, "model_refused_but_rule_matched")
        weak = top_score is not None and top_score < self.settings.escalation_score_threshold
        if weak:
            reasons.insert(0, "low_retrieval_score")

        behavior = "escalate" if weak or reply.behavior != "answer" else "answer"
        # Show the model's text only if it is backed by a citation and search was not weak.
        show_text = bool(
            not weak
            and reply.behavior != "refuse"
            and reply.answer.strip()
            and reply.cited_article_ids
        )
        if not show_text:
            text, cited = self.messages["escalate"], []
        else:
            text = reply.answer.strip()
            cited = list(dict.fromkeys(reply.cited_article_ids))
            if reasons:
                text = f"{text}\n\n{self.messages['escalation_notice']}"
        return self._result(
            conversation_id,
            behavior,
            text,
            citations=[Citation(article_id=a, title=self.titles[a]) for a in cited],
            confidence=confidence,
            reasons=reasons,
            events=events,
        )

    def _result(
        self,
        conversation_id: str,
        behavior: str,
        answer: str,
        *,
        citations: list[Citation] | None = None,
        confidence: float = 0.0,
        reasons: list[str] | None = None,
        events: list[str],
    ) -> ChatResult:
        reasons = reasons or []
        return ChatResult(
            request_id=uuid.uuid4().hex,
            conversation_id=conversation_id,
            behavior=behavior,
            answer=answer,
            citations=citations or [],
            confidence=round(confidence, 4),
            escalate=behavior == "escalate" or bool(reasons),
            escalation_reasons=reasons,
            guardrail_events=events,
            model=f"{self.provider.name}:{self.provider.model}",
            prompt_version=self.prompt.version,
            variant=self.settings.variant_name,
        )

    def _finish(
        self, user_id: str, result: ChatResult, trace: TurnTrace, started: float
    ) -> tuple[ChatResult, TurnTrace]:
        trace.latency_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "chat_turn",
            extra={
                "fields": {
                    "user_id": user_id,
                    **result.model_dump(exclude={"citations", "answer"}),
                    "cited": [c.article_id for c in result.citations],
                    # Article text and the raw reply go to the database, not the log.
                    **trace.model_dump(exclude={"context", "model_reply"}),
                }
            },
        )
        return result, trace
