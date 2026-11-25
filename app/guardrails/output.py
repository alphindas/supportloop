"""Check the model's reply in code before a customer sees it."""

import re

from pydantic import BaseModel, ConfigDict, ValidationError

NUMBER = re.compile(r"\d+(?:[.,:]\d+)*")
LIST_MARKER = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
CURRENCY_SIGNS = {"£", "$", "€"}


class BotAnswer(BaseModel):
    """The JSON the model must return. Strict mode needs every field required."""

    model_config = ConfigDict(extra="forbid")

    behavior: str
    answer: str
    cited_article_ids: list[str]


def bot_answer_schema() -> dict:
    """JSON schema sent to the provider, with the allowed behaviours listed."""
    schema = BotAnswer.model_json_schema()
    schema["properties"]["behavior"]["enum"] = ["answer", "escalate", "refuse"]
    return schema


def parse_bot_answer(text: str) -> BotAnswer | None:
    """Parse and validate. Returns None if the reply is unusable."""
    try:
        parsed = BotAnswer.model_validate_json(text.strip())
    except ValidationError:
        return None
    return parsed if parsed.behavior in {"answer", "escalate", "refuse"} else None


def _clean_number(token: str) -> str:
    """'5,000' and '5000' are equal; so are '5' and '5.00'."""
    cleaned = re.sub(r",(?=\d{3}(?!\d))", "", token)
    if re.fullmatch(r"\d+\.\d+", cleaned):
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned


def _numbers(text: str) -> set[tuple[str, str]]:
    """Every number as (kind, value), where kind is a currency sign, '%' or ''."""
    text = LIST_MARKER.sub("", text)
    found = set()
    for match in NUMBER.finditer(text):
        before = text[: match.start()].rstrip()[-1:]
        after = text[match.end() :].lstrip()[:1]
        kind = before if before in CURRENCY_SIGNS else "%" if after == "%" else ""
        found.add((kind, _clean_number(match.group())))
    return found


def ungrounded_numbers(answer: str, articles: list[str], customer_message: str = "") -> set[str]:
    """Numbers in the answer that are not supported by the articles or the customer.

    An amount of money or a percentage must appear as the same kind in an article, so
    "5 to 7 days" does not support an invented "£7" fee. A number the customer typed
    may be repeated in any form. This cannot catch numbers written as words, or a real
    amount attached to the wrong thing.
    """
    from_articles: set[tuple[str, str]] = set()
    for article in articles:
        from_articles |= _numbers(article)
    from_customer = {value for _, value in _numbers(customer_message)}
    article_values = {value for _, value in from_articles}

    problems = set()
    for kind, value in _numbers(answer):
        supported = (kind, value) in from_articles if kind else value in article_values
        if not supported and value not in from_customer:
            problems.add(f"{value}%" if kind == "%" else f"{kind}{value}")
    return problems


def check_answer(
    reply: BotAnswer, article_texts: dict[str, str], customer_message: str
) -> list[str]:
    """Return the names of failed checks. An empty list means the reply passed.

    article_texts maps each retrieved article id to the text the model was shown.
    """
    if reply.behavior == "refuse":
        return []  # the model's text is replaced by a fixed refusal
    problems = []
    unknown = [a for a in reply.cited_article_ids if a not in article_texts]
    if unknown:
        problems.append("citation_not_retrieved")
    if reply.behavior == "answer" and not reply.cited_article_ids:
        problems.append("missing_citation")
    if reply.behavior == "answer" and not reply.answer.strip():
        problems.append("empty_answer")
    cited = [article_texts[a] for a in reply.cited_article_ids if a in article_texts]
    if ungrounded_numbers(reply.answer, cited, customer_message):
        problems.append("ungrounded_number")
    return problems
