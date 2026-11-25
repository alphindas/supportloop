"""The LLM judge: faithfulness and correctness, from a versioned rubric."""

from pydantic import BaseModel, ConfigDict, ValidationError

from app.chat.pipeline import neutralise
from app.config import Settings
from app.llm.base import LLMProvider, LLMRequest, LLMResponse, Message
from app.prompts.loader import PromptTemplate, load_template

NO_REFERENCE = "(none)"


class Verdict(BaseModel):
    """The judge's JSON reply. Each reason comes before its verdict, so the model has to
    state its evidence before deciding."""

    model_config = ConfigDict(extra="forbid")

    faithfulness_reason: str
    faithful: bool
    correctness_reason: str
    correct: bool


def load_rubric(settings: Settings) -> PromptTemplate:
    """Read the configured rubric file."""
    path = settings.resolve(settings.rubrics_dir) / f"judge_{settings.judge_rubric_version}.txt"
    return load_template(path, settings.judge_rubric_version)


def build_judge_request(
    settings: Settings,
    rubric: PromptTemplate,
    question: str,
    articles: dict[str, str],
    answer: str,
    reference: str | None,
) -> LLMRequest:
    """Fill the rubric. The judge sees exactly the articles the bot was shown."""
    shown = "\n\n".join(
        f'<article id="{article_id}">\n{text}\n</article>' for article_id, text in articles.items()
    )
    user = rubric.user.substitute(
        articles=shown or "(no articles)",
        question=neutralise(question),
        reference=neutralise(reference) if reference else NO_REFERENCE,
        answer=neutralise(answer),
    )
    return LLMRequest(
        messages=[
            Message(role="system", content=rubric.system),
            Message(role="user", content=user),
        ],
        prompt_version=f"judge_{rubric.version}",
        temperature=settings.judge_temperature,
        max_output_tokens=settings.judge_max_output_tokens,
        schema_name="judge_verdict",
        json_schema=Verdict.model_json_schema(),
    )


async def ask_judge(
    provider: LLMProvider, request: LLMRequest
) -> tuple[Verdict | None, LLMResponse]:
    """Return the verdict (None if the reply is unreadable) and the raw response."""
    response = await provider.complete(request)
    try:
        return Verdict.model_validate_json(response.text.strip()), response
    except ValidationError:
        return None, response
