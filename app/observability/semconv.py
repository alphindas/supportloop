"""OpenTelemetry attribute names, all in one place.

The GenAI conventions are still marked "Development" and may be renamed.
Source, read 2026-11-25:
https://github.com/open-telemetry/semantic-conventions-genai
(docs/gen-ai/client-inference.md and docs/gen-ai/retrieval.md)
"""

OPERATION_NAME = "gen_ai.operation.name"
PROVIDER_NAME = "gen_ai.provider.name"
CONVERSATION_ID = "gen_ai.conversation.id"
OUTPUT_TYPE = "gen_ai.output.type"
PROMPT_NAME = "gen_ai.prompt.name"
PROMPT_VERSION = "gen_ai.prompt.version"
REQUEST_MODEL = "gen_ai.request.model"
REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
REQUEST_TEMPERATURE = "gen_ai.request.temperature"
RESPONSE_MODEL = "gen_ai.response.model"
USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
RETRIEVAL_TOP_K = "gen_ai.retrieval.top_k"
RETRIEVAL_DOCUMENTS = "gen_ai.retrieval.documents"
ERROR_TYPE = "error.type"

# Our own attributes use our own prefix, so they cannot clash with the standard.
# No message text, query text or answer text is ever put in a span.
REQUEST_ID = "supportloop.request_id"
VARIANT = "supportloop.variant"
BEHAVIOR = "supportloop.behavior"
ESCALATE = "supportloop.escalate"
PII_KINDS = "supportloop.guardrail.pii_kinds"
INJECTION_RULES = "supportloop.guardrail.injection_rules"
GUARDRAIL_EVENTS = "supportloop.guardrail.events"
LLM_CACHED = "supportloop.llm.cached"
LLM_WAIT_MS = "supportloop.llm.wait_ms"
