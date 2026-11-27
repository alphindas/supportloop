"""Before and after a data loop cycle, on messages that were never mined.

Uses the Banking77 'loop_holdout' pool, which mining never sees. Intent labels are used
here only to pick and group messages:
- 'filled topics': every holdout message of an intent whose gap the cycle filled;
- 'other topics': a seeded random sample of all other intents, to look for harm.

'Resolved' = the bot answered without handing off, and the judge found the answer
faithful to the articles it was shown. The judge is not validated by a human, and
faithful does not mean the answer solves the customer's problem.

Usage: uv run python -m loop.holdout --kb before   (then --kb after, then --report)
Model calls are cached, so a run stopped by a quota continues when run again.
"""

import argparse
import asyncio
import json
from random import Random

import httpx
import yaml

from app.banking77 import Message
from app.chat.factory import build_chat_service
from app.config import PROJECT_ROOT, Settings, get_settings
from evals.graders.judge import ask_judge, build_judge_request, load_rubric
from evals.graders.rules import shown_model_text
from evals.run_eval import RecordingProvider, cached, is_temporary

OTHER_SAMPLE = 30
SEED = 20261127
RAW = PROJECT_ROOT / "reports" / "raw"


def choose(pool: list[Message], filled: set[str], size: int, seed: int) -> list[dict]:
    """Every filled-topic message, plus a fixed random sample of the rest."""
    ordered = sorted(pool, key=lambda m: m.message_id)
    topic = [m for m in ordered if m.intent in filled]
    rest = [m for m in ordered if m.intent not in filled]
    Random(seed).shuffle(rest)
    return [
        {"id": m.message_id, "message": m.text, "intent": m.intent, "group": group}
        for group, chosen in (("filled", topic), ("other", rest[:size]))
        for m in chosen
    ]


def kb_settings(settings: Settings, which: str) -> Settings:
    """Point 'before' at the copy made by loop.kb_before."""
    if which == "after":
        return settings
    return settings.model_copy(
        update={
            "kb_dir": PROJECT_ROOT / "data" / "cache" / "kb_before",
            "index_dir": PROJECT_ROOT / "data" / "cache" / "index_before",
        }
    )


async def run(which: str, tasks: list[dict], settings: Settings) -> list[dict]:
    """Answer and judge each message. Raises on quota or outage."""
    settings = kb_settings(settings, which)
    rubric = load_rubric(settings)
    rows = []
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        generator = RecordingProvider(cached(settings, client, "groq", None), [10**9])
        judge = cached(settings, client, "groq", settings.groq_judge_model)
        service = build_chat_service(settings, client, generator)
        for number, task in enumerate(tasks, start=1):
            generator.error = None
            result, trace = await service.handle("holdout", f"h-{task['id']}", task["message"])
            if generator.error is not None and is_temporary(generator.error):
                raise generator.error
            text = shown_model_text(result.answer, service.messages)
            faithful = None
            if text is not None:
                request = build_judge_request(
                    settings, rubric, trace.redacted_message, trace.context, text, None
                )
                verdict, _ = await ask_judge(judge, request)
                faithful = None if verdict is None else verdict.faithful
            rows.append(
                {
                    "id": task["id"],
                    "group": task["group"],
                    "behavior": result.behavior,
                    "escalate": result.escalate,
                    "cited": [c.article_id for c in result.citations],
                    "answer": result.answer,
                    "faithful": faithful,
                }
            )
            if number % 20 == 0:
                print(f"{which}: {number}/{len(tasks)}", flush=True)
    return rows


def main() -> None:
    """Run one side and save it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kb", choices=["before", "after"], required=True)
    which = parser.parse_args().kb
    data = yaml.safe_load((PROJECT_ROOT / "config" / "data.yaml").read_text())
    pool_file = PROJECT_ROOT / data["banking77"]["dir"] / "pools" / "loop_holdout.jsonl"
    pool = [Message(**json.loads(line)) for line in pool_file.read_text().splitlines()]
    gaps = yaml.safe_load((PROJECT_ROOT / "loop" / "cycle1" / "gaps.yaml").read_text())
    tasks = choose(pool, set(gaps["filled_gaps"]), OTHER_SAMPLE, SEED)
    rows = asyncio.run(run(which, tasks, get_settings()))
    output = RAW / f"holdout_cycle1_{which}.json"
    output.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {output.name}: {len(rows)} messages")


if __name__ == "__main__":
    main()
