"""Run the app on an eval set, grade the replies and write a report.

The same ChatService the API uses answers every task. Model replies are cached, so a
rerun costs nothing and gives the same numbers. If a rate limit or daily quota is hit,
progress is saved: run the same command later to continue.

Usage:
    uv run python -m evals.run_eval                      # configured provider
    uv run python -m evals.run_eval --limit 40           # at most 40 new LLM calls
    uv run python -m evals.run_eval --report-only        # rebuild the report, no calls
"""

import argparse
import asyncio
import json
import re
from datetime import date
from pathlib import Path

import httpx

from app.chat.factory import build_chat_service
from app.chat.pipeline import ChatService
from app.config import PROJECT_ROOT, Settings, get_settings
from app.guardrails.pii import redact
from app.llm.base import (
    LLMError,
    LLMProvider,
    LLMQuotaExceededError,
    LLMRequest,
    LLMResponse,
    request_fingerprint,
)
from app.llm.cache import CachedProvider, ResponseCache
from app.llm.factory import build_provider
from evals.benchmark_retrieval import evaluate, load_benchmark_config
from evals.eval_report import Rates, write_report
from evals.graders.judge import ask_judge, build_judge_request, load_rubric
from evals.graders.rules import grade_rules, shown_model_text, task_passed
from evals.report_header import git_commit
from evals.stats import bootstrap_ci

HUMAN_SAMPLE_SIZE = 30


class BatchLimitReached(Exception):
    """The --limit number of new LLM calls has been made."""


class RecordingProvider:
    """Wraps a provider to remember the last request and error, and to enforce --limit.

    The pipeline turns LLM errors into a hand-off, which is right for customers. The
    eval must not grade such a hand-off as the bot's answer, so it looks here.
    """

    def __init__(self, inner: LLMProvider, budget: list[int]) -> None:
        self._inner = inner
        self._budget = budget  # one shared counter of new calls still allowed
        self.name, self.model = inner.name, inner.model
        self.last_request: LLMRequest | None = None
        self.last_response: LLMResponse | None = None
        self.error: LLMError | None = None

    def build_payload(self, request: LLMRequest) -> dict:
        """Same body as the wrapped provider."""
        return self._inner.build_payload(request)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Call the wrapped provider and keep notes."""
        self.last_request, self.last_response, self.error = request, None, None
        if self._budget[0] <= 0:
            self.error = LLMError("batch limit reached")
            raise self.error
        try:
            response = await self._inner.complete(request)
        except LLMError as error:
            self.error = error
            raise
        if not response.cached:
            self._budget[0] -= 1
        self.last_response = response
        return response


def is_temporary(error: LLMError) -> bool:
    """Should the run stop and resume later, rather than grade this as a failure?

    A rejected request (HTTP 400) is the model failing the task, which a customer would
    also experience. Everything else is an outage or a limit.
    """
    return isinstance(error, LLMQuotaExceededError) or "HTTP 400" not in str(error)


def config_name(provider: str, model: str, prompt_version: str) -> str:
    """For example 'groq-openai-gpt-oss-20b_prompt-v1'."""
    safe = re.sub(r"[^A-Za-z0-9.]+", "-", f"{provider}-{model}").strip("-")
    return f"{safe}_prompt-{prompt_version}"


def shown_path(path: Path) -> str:
    """Project-relative if possible, so reports do not contain home directories."""
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else path.name


def load_tasks(path: Path) -> list[dict]:
    """Read an eval set."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cached(settings: Settings, client: httpx.AsyncClient, provider: str, model: str | None):
    """A provider with the response cache switched on."""
    uncached = settings.model_copy(update={"llm_cache_enabled": False})
    return CachedProvider(
        build_provider(uncached, client, provider, model),
        ResponseCache(settings.resolve(settings.llm_cache_path)),
    )


async def run_task(
    service: ChatService, provider: RecordingProvider, task: dict, previous: dict | None
) -> dict:
    """One task in a fresh conversation. Raises if the run should stop."""
    provider.last_request = provider.last_response = provider.error = None
    result, trace = await service.handle("eval", f"eval-{task['id']}", task["input"])
    if provider.error is not None and is_temporary(provider.error):
        if str(provider.error) == "batch limit reached":
            raise BatchLimitReached
        raise provider.error

    key = None
    if provider.last_request is not None:
        key = request_fingerprint(provider, provider.last_request)
    response = provider.last_response
    latency = None
    if previous and previous.get("request_key") == key and previous.get("latency_ms") is not None:
        latency = previous["latency_ms"]  # keep the first measurement, so reruns agree
    elif response is not None and not response.cached:
        latency = round(trace.latency_ms - response.wait_ms, 1)

    text = shown_model_text(result.answer, service.messages)
    return {
        "id": task["id"],
        "category": task["category"],
        "input": trace.redacted_message,
        "expected_behavior": task["expected_behavior"],
        "reference_answer": task["reference_answer"],
        "behavior": result.behavior,
        "answer": result.answer,
        "shown_text": text,
        "cited": [c.article_id for c in result.citations],
        "context": trace.context,
        "confidence": result.confidence,
        "escalate_flag": result.escalate,
        "escalation_reasons": result.escalation_reasons,
        "guardrail_events": result.guardrail_events,
        "stopped_by_rules": any(e.startswith("prompt_injection:") for e in result.guardrail_events),
        "checks": grade_rules(task, result, trace, service.messages),
        "request_key": key,
        "latency_ms": latency,
        "input_tokens": response.input_tokens if response else None,
        "output_tokens": response.output_tokens if response else None,
        "verdict": None,
        "judge_tokens": None,
        "passed": None,
    }


def retrieval_check(service: ChatService, tasks: list[dict], settings: Settings) -> list[str]:
    """Compare the app's retrieval with hybrid retrieval on these new questions.

    These questions played no part in choosing models, the threshold or dropping BM25.
    """
    boot = load_benchmark_config()["bootstrap"]
    questions = [
        {**t, "question": redact(t["input"]).text, "kind": t["category"]}
        for t in tasks
        if t["expected_article_ids"]
    ]
    runs = {
        name: evaluate(service.retriever, questions, 5, mode=mode)
        for name, mode in (("Dense + reranker", "dense"), ("Hybrid + reranker", "hybrid"))
    }
    lines = [
        "## Fresh check of the BM25 decision (retrieval only)",
        "",
        f"{len(questions)} answerable inputs from this eval set. They played no part in "
        "choosing models or the threshold, or in dropping BM25. Labels are AI-drafted.",
        "",
        "| Setup | Recall@5 | MRR |",
        "|---|---|---|",
    ]
    for name, rows in runs.items():
        cells = []
        for key in ("recall", "reciprocal_rank"):
            values = [r[key] for r in rows]
            low, high = bootstrap_ci(values, boot["resamples"], boot["seed"])
            cells.append(f"{sum(values) / len(values):.3f} [{low:.3f}, {high:.3f}]")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    for label, key in (("Recall@5", "recall"), ("MRR", "reciprocal_rank")):
        differences = [
            a[key] - b[key]
            for a, b in zip(runs["Dense + reranker"], runs["Hybrid + reranker"], strict=True)
        ]
        low, high = bootstrap_ci(differences, boot["resamples"], boot["seed"])
        verdict = "no clear difference" if low <= 0 <= high else "clear difference"
        lines.append(
            f"- Paired difference, dense minus hybrid, {label}: "
            f"{sum(differences) / len(differences):+.3f} [{low:+.3f}, {high:+.3f}] ({verdict})"
        )
    return lines


async def run(
    limit: int | None,
    settings: Settings,
    paths: dict,
    generator_override: LLMProvider | None = None,
    judge_override: LLMProvider | None = None,
) -> dict:
    """Generate replies, then judge them. Returns the run to save.

    Tests pass in their own providers. Normally both are real and cached.
    """
    tasks = load_tasks(paths["eval_set"])
    previous_run = json.loads(paths["raw"].read_text()) if paths["raw"].exists() else None
    previous = {r["id"]: r for r in previous_run["rows"]} if previous_run else {}
    budget = [limit if limit is not None else 10**9]
    rows: dict[str, dict] = {}
    stop_reason = None

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        inner = generator_override or cached(settings, client, settings.llm_provider, None)
        generator = RecordingProvider(inner, budget)
        service = build_chat_service(settings, client, generator)
        service.retriever.retrieve("warm up", top_k=1)  # the first search is slower

        try:
            for number, task in enumerate(tasks, start=1):
                rows[task["id"]] = await run_task(
                    service, generator, task, previous.get(task["id"])
                )
                if number % 25 == 0:
                    print(f"generated {number}/{len(tasks)}", flush=True)
        except BatchLimitReached:
            stop_reason = "batch limit reached during generation"
        except LLMError as error:
            stop_reason = f"generator unavailable: {error}"

        judge_inner = judge_override or cached(settings, client, "groq", settings.groq_judge_model)
        judge = RecordingProvider(judge_inner, budget)
        rubric = load_rubric(settings)
        to_judge = [r for r in rows.values() if r["shown_text"] is not None]
        print(f"judging {len(to_judge)} replies that contain model text", flush=True)
        for number, row in enumerate(to_judge, start=1):
            request = build_judge_request(
                settings, rubric, row["input"], row["context"], row["shown_text"],
                row["reference_answer"],
            )  # fmt: skip
            try:
                verdict, response = await ask_judge(judge, request)
            except LLMError as error:
                if is_temporary(error):
                    stop_reason = f"judge unavailable: {error}"
                    break
                print(f"judge could not grade {row['id']}: {error}")
                continue
            if verdict is not None:
                row["verdict"] = verdict.model_dump()
            row["judge_tokens"] = (response.input_tokens or 0) + (response.output_tokens or 0)
            if number % 25 == 0:
                print(f"judged {number}/{len(to_judge)}", flush=True)

        check = retrieval_check(service, tasks, settings)

    ordered = [rows[t["id"]] for t in tasks if t["id"] in rows]
    for row in ordered:
        row["passed"] = task_passed(
            row["expected_behavior"], row["checks"], row["verdict"], row["shown_text"] is not None
        )
    if stop_reason:
        print(f"STOPPED EARLY: {stop_reason}\nProgress is saved. Run the command again later.")

    name = paths["name"]
    # Keep the original date and commit if nothing changed, so a rerun is identical.
    unchanged = previous_run is not None and previous_run["rows"] == ordered
    if unchanged:
        header = previous_run["meta"]["header"]
    else:
        header = {
            "Generated": date.today().isoformat(),
            "Git commit": git_commit(),
            "Prompt version": settings.prompt_version,
            "Judge model": f"{judge.name}:{judge.model} (used in this report)",
        }
    meta = {
        "config_name": name,
        "eval_set": shown_path(paths["eval_set"]),
        "eval_set_version": paths["eval_set"].stem,
        "task_count": len(tasks),
        "rows_human_reviewed": sum(t["review_status"] == "human_reviewed" for t in tasks),
        "header": header,
        "models": {
            "Generator LLM": f"{service.provider.name}:{service.provider.model}",
            "Judge rubric": f"evals/rubrics/judge_{settings.judge_rubric_version}.txt",
            "Embedding model": settings.embedding_model,
            "Reranker model": settings.reranker_model,
            "Retrieval mode": settings.retrieval_mode,
            "Escalation threshold": str(settings.escalation_score_threshold),
            "Corpus fingerprint": service.retriever.corpus_fingerprint,
        },
        "retrieval_check": check,
    }
    return {"meta": meta, "rows": ordered}


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--eval-set", default="evals/sets/v1.jsonl")
    parser.add_argument("--limit", type=int, help="at most this many new LLM calls")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    eval_set = PROJECT_ROOT / args.eval_set
    if settings.llm_provider == "fake":
        raise SystemExit("The fake provider is for tests. Set llm_provider to groq or ollama.")
    model = (
        settings.groq_generator_model if settings.llm_provider == "groq" else settings.ollama_model
    )
    name = config_name(settings.llm_provider, model, settings.prompt_version)
    stem = f"eval_{eval_set.stem}_{name}"
    paths = {
        "name": name,
        "eval_set": eval_set,
        "raw": PROJECT_ROOT / "reports" / "raw" / f"{stem}.json",
        "report": PROJECT_ROOT / "reports" / f"{stem}.md",
    }
    if args.report_only:
        result = json.loads(paths["raw"].read_text())
    else:
        result = asyncio.run(run(args.limit, settings, paths))
        paths["raw"].write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    boot = load_benchmark_config()["bootstrap"]
    write_report(
        paths["report"], settings, result, Rates(boot["resamples"], boot["seed"]), HUMAN_SAMPLE_SIZE
    )
    done = sum(r["passed"] is not None for r in result["rows"])
    print(
        f"Wrote {shown_path(paths['report'])}: {done}/{result['meta']['task_count']} "
        "tasks fully graded"
    )


if __name__ == "__main__":
    main()
