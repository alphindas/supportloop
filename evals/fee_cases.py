"""Replay two fee questions that a local model got wrong, on one or more local models.

In the simulated traffic, llama3.2:3b invented a "£10 minimum" fee in one reply and said
UK and EEA debit cards cost 1.5% in another. The number check passed both. This runs the
same two messages through the whole app. It prints replies and does NOT grade them: a
person has to compare them with the articles.

Usage: uv run python -m evals.fee_cases   (needs Ollama; no Groq quota, no database)
"""

import argparse
import asyncio

import httpx

from app.chat.factory import build_chat_service
from app.config import PROJECT_ROOT, get_settings
from evals.report_header import report_header

CASES = {
    "a8db2bee": "What fee is included if I top up by card?",
    "f3d6916d": "What are the top-up fees?",
}
MODELS = ["llama3.2:3b", "phi4-mini"]
REPEATS = 3


async def replay(models: list[str]) -> list[str]:
    """Return the report body: every distinct reply per model and case."""
    lines: list[str] = []
    contexts: dict[str, dict[str, str]] = {}
    async with httpx.AsyncClient(timeout=180) as client:
        for model in models:
            settings = get_settings().model_copy(
                update={
                    "llm_provider": "ollama",
                    "ollama_model": model,
                    "retrieval_device": "cpu",
                    "llm_cache_enabled": False,
                }
            )
            service = build_chat_service(settings, client)
            lines += ["", f"## `{model}`"]
            for case, message in CASES.items():
                replies: dict[tuple[str, str], int] = {}
                for run in range(REPEATS):
                    result, trace = await service.handle("fee-check", f"{case}-{run}", message)
                    contexts[case] = trace.context
                    events = ", ".join(result.guardrail_events) or "none"
                    key = (f"{result.behavior}; guardrail events: {events}", result.answer)
                    replies[key] = replies.get(key, 0) + 1
                lines += ["", f"### `{case}`: {message}"]
                for (status, answer), count in replies.items():
                    lines += ["", f"{count} of {REPEATS} runs ({status}):", "", f"> {answer}"]
    lines += ["", "## Fee article shown to the models"]
    for case, context in contexts.items():
        lines += ["", f"`{case}`, `topup-fees`:", "", "```", context.get("topup-fees", ""), "```"]
    return lines


def main() -> None:
    """Run the cases and write the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=MODELS)
    models = parser.parse_args().models
    body = asyncio.run(replay(models))
    header = report_header(
        "Local models on two wrong-fee cases",
        get_settings(),
        eval_set="none (two messages from the simulated traffic)",
        models={"Generator LLM": ", ".join(f"ollama:{m}" for m in models)},
        judge_used=False,
    )
    note = (
        "\nReplies only; nothing here is graded automatically. Two questions are far too few "
        "to compare models.\n"
    )
    report = PROJECT_ROOT / "reports" / "local_model_fee_cases.md"
    report.write_text(header + note + "\n".join(body) + "\n", encoding="utf-8")
    print(f"Wrote {report.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
