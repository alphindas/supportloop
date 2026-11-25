"""Judge the faithfulness of a sample of stored replies (a production signal).

Which turns are sampled depends only on their request ID, so reruns pick the same ones.
A reply judged unfaithful gets a 'low_faithfulness' failure signal.

Usage: uv run python -m evals.judge_live --limit 40
"""

import argparse
import asyncio
import hashlib

import httpx

from app.config import Settings, get_settings
from app.llm.base import LLMError, LLMProvider
from app.prompts.loader import load_messages
from app.storage.db import LiveJudgment, Turn, create_database
from app.storage.repository import Repository
from evals.graders.judge import ask_judge, build_judge_request, load_rubric
from evals.graders.rules import shown_model_text
from evals.run_eval import cached


def is_sampled(request_id: str, rate: float) -> bool:
    """True for about `rate` of all request IDs, always the same ones."""
    bucket = int(hashlib.sha256(f"judge:{request_id}".encode()).hexdigest()[:8], 16)
    return bucket / 0xFFFFFFFF < rate


async def judge_turns(
    repository: Repository,
    provider: LLMProvider,
    settings: Settings,
    limit: int,
) -> tuple[int, int]:
    """Judge up to `limit` unjudged sampled turns. Returns (judged, unfaithful)."""
    rubric = load_rubric(settings)
    messages = load_messages(settings.resolve(settings.prompts_dir), settings.messages_version)
    already = repository.judged_request_ids(provider.model, rubric.version)
    candidates: list[tuple[Turn, str]] = []
    for turn in repository.turns():
        text = shown_model_text(turn.answer, messages)
        shows_model_text = text is not None and bool(turn.cited_article_ids)
        if (
            shows_model_text
            and turn.request_id not in already
            and is_sampled(turn.request_id, settings.judge_live_sample_rate)
        ):
            candidates.append((turn, text))

    judged = unfaithful = 0
    for turn, text in candidates[:limit]:
        request = build_judge_request(
            settings, rubric, turn.redacted_message, turn.context, text, reference=None
        )
        try:
            verdict, _ = await ask_judge(provider, request)
        except LLMError as error:
            print(f"Stopped: {error}. Run again later to continue.")
            break
        if verdict is None:
            continue
        repository.save_judgment(
            LiveJudgment(
                request_id=turn.request_id,
                judge_model=provider.model,
                rubric_version=rubric.version,
                faithful=verdict.faithful,
                reason=verdict.faithfulness_reason,
            )
        )
        judged += 1
        unfaithful += not verdict.faithful
    print(f"{len(candidates)} sampled turns were waiting")
    return judged, unfaithful


async def run(limit: int) -> None:
    """Connect and judge."""
    settings = get_settings()
    repository = Repository(create_database(settings.resolve(settings.database_path)))
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        provider = cached(settings, client, "groq", settings.groq_judge_model)
        judged, unfaithful = await judge_turns(repository, provider, settings, limit)
    print(f"Judged {judged}; unfaithful {unfaithful} (judge: {settings.groq_judge_model})")


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=40)
    asyncio.run(run(parser.parse_args().limit))


if __name__ == "__main__":
    main()
