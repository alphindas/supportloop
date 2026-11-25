"""Compare chat models on the same retrieved context.

Step 1 retrieves context in a separate process, which frees the GPU when it exits.
Step 2 runs each model on that context, one at a time, unloading it afterwards.

Usage: uv run python -m evals.benchmark_llm
"""

import asyncio
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from random import Random

import httpx

from app.chat.factory import build_retriever
from app.chat.pipeline import build_llm_request, format_articles
from app.config import PROJECT_ROOT, get_settings
from app.guardrails.output import check_answer, parse_bot_answer
from app.llm.base import LLMError, LLMProvider
from app.llm.cache import CachedProvider, ResponseCache
from app.llm.factory import build_provider
from app.prompts.loader import PromptTemplate, load_prompt
from app.rag.retriever import RetrievedChunk
from evals.benchmark_retrieval import load_benchmark_config, load_questions
from evals.stats import percentile

RAW_OUTPUT = PROJECT_ROOT / "reports" / "raw" / "benchmark_llm.json"


def choose_tasks(questions: list[dict], counts: dict[str, int], seed: int) -> list[dict]:
    """A fixed random sample: answerable, should-escalate and should-refuse tasks."""
    rng = Random(seed)
    groups = {
        "answer": [q for q in questions if q["expected_article_ids"]],
        "escalate": [q for q in questions if q["kind"] == "negative_banking"],
        "refuse": [q for q in questions if q["kind"] == "negative_offtopic"],
    }
    tasks = []
    for behaviour, rows in groups.items():
        for row in rng.sample(rows, counts[behaviour]):
            tasks.append({**row, "expected_behaviour": behaviour})
    return tasks


def retrieve_contexts(tasks: list[dict]) -> list[dict]:
    """Attach the retrieved article texts to every task."""
    settings = get_settings()
    retriever, _ = build_retriever(settings)
    for task in tasks:
        found: list[RetrievedChunk] = retriever.retrieve(task["question"], settings.context_top_k)
        task["article_texts"] = format_articles(found)
    return tasks


def score(task: dict, text: str) -> dict:
    """Code-only grading of one reply."""
    reply = parse_bot_answer(text)
    if reply is None:
        return {"valid_json": False, "behaviour": False, "checks": False, "passed": False}
    behaviour = reply.behavior == task["expected_behaviour"]
    checks = not check_answer(reply, task["article_texts"], task["question"])
    cites_expected = task["expected_behaviour"] != "answer" or bool(
        set(reply.cited_article_ids) & set(task["expected_article_ids"])
    )
    return {
        "valid_json": True,
        "behaviour": behaviour,
        "checks": checks,
        "passed": behaviour and checks and cites_expected,
    }


async def ollama_memory(client: httpx.AsyncClient, base_url: str, model: str) -> tuple:
    """(GiB on the GPU, share of the loaded model that is on the GPU)."""
    loaded = (await client.get(f"{base_url}/api/ps")).json()["models"]
    for entry in loaded:
        if entry["name"] in (model, f"{model}:latest"):
            return entry["size_vram"] / 2**30, entry["size_vram"] / entry["size"]
    return None, None


async def run_model(
    client: httpx.AsyncClient, provider: LLMProvider, tasks: list[dict], prompt: PromptTemplate
) -> dict:
    """Run all tasks on one model."""
    settings = get_settings()
    rows = []
    for task in tasks:
        request = build_llm_request(settings, prompt, task["question"], [], task["article_texts"])
        try:
            response = await provider.complete(request)
        except LLMError as error:
            raise SystemExit(f"{provider.name}:{provider.model} failed: {error}") from error
        rows.append(
            {"id": task["id"], "expected": task["expected_behaviour"], "reply": response.text,
             "latency_ms": response.latency_ms, "output_tokens": response.output_tokens,
             "input_tokens": response.input_tokens, **score(task, response.text)}
        )  # fmt: skip
        print(".", end="", flush=True)
    print()
    vram_gib = gpu_share = tokens_per_second = None
    if provider.name == "ollama":
        vram_gib, gpu_share = await ollama_memory(client, settings.ollama_base_url, provider.model)
        total_tokens = sum(r["output_tokens"] or 0 for r in rows)
        # Includes the time to read the prompt, so it is lower than pure generation speed.
        tokens_per_second = total_tokens / (sum(r["latency_ms"] for r in rows) / 1000)
    latencies = [r["latency_ms"] / 1000 for r in rows]
    return {
        "provider": provider.name,
        "model": provider.model,
        "n": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "behaviour_correct": sum(r["behaviour"] for r in rows),
        "valid_json": sum(r["valid_json"] for r in rows),
        "checks_passed": sum(r["checks"] for r in rows),
        "latency_p50_s": percentile(latencies, 50),
        "latency_p95_s": percentile(latencies, 95),
        "tokens_per_second": tokens_per_second,
        "vram_gib": vram_gib,
        "gpu_share": gpu_share,
        "rows": rows,
    }


def select_local(runs: list[dict], tie_margin: float) -> str:
    """Best pass rate; among near-ties, the lowest median latency."""
    local = [r for r in runs if r["provider"] == "ollama"]
    best = max(r["passed"] / r["n"] for r in local)
    tied = [r for r in local if best - r["passed"] / r["n"] <= tie_margin]
    return min(tied, key=lambda r: r["latency_p50_s"])["model"]


async def benchmark(tasks: list[dict], config: dict) -> list[dict]:
    """Run every candidate."""
    settings = get_settings()
    prompt = load_prompt(settings.resolve(settings.prompts_dir), settings.prompt_version)
    runs = []
    async with httpx.AsyncClient(timeout=config["timeout_seconds"]) as client:
        for model in config["local_models"]:
            print(f"ollama:{model} ", end="", flush=True)
            # No cache for local models: latency must be measured now.
            uncached = settings.model_copy(update={"llm_cache_enabled": False})
            provider = build_provider(uncached, client, "ollama", model)
            warm_up = build_llm_request(settings, prompt, "hello", [], {})
            await provider.complete(warm_up)  # loading the model is not part of latency
            runs.append(await run_model(client, provider, tasks, prompt))
            await client.post(
                f"{settings.ollama_base_url}/api/generate", json={"model": model, "keep_alive": 0}
            )
        for model in config["hosted_reference_models"]:
            print(f"groq:{model} ", end="", flush=True)
            uncached = settings.model_copy(update={"llm_cache_enabled": False})
            # Cached, so a rerun costs no quota and keeps the first call's latency.
            provider = CachedProvider(
                build_provider(uncached, client, "groq", model),
                ResponseCache(settings.resolve(settings.llm_cache_path)),
            )
            runs.append(await run_model(client, provider, tasks, prompt))
    return runs


def main() -> None:
    """Retrieve in a child process, then benchmark."""
    config = load_benchmark_config()
    if len(sys.argv) > 1 and sys.argv[1] == "--retrieve":
        path = Path(sys.argv[2])
        path.write_text(json.dumps(retrieve_contexts(json.loads(path.read_text()))))
        return

    llm = config["llm"]
    questions = load_questions(PROJECT_ROOT / config["retrieval"]["eval_set"], "dev")
    tasks = choose_tasks(questions, llm["task_counts"], llm["seed"])
    with tempfile.NamedTemporaryFile("w+", suffix=".json") as handle:
        json.dump(tasks, handle)
        handle.flush()
        subprocess.run(
            [sys.executable, "-m", "evals.benchmark_llm", "--retrieve", handle.name],
            cwd=PROJECT_ROOT, check=True,
        )  # fmt: skip
        tasks = json.loads(Path(handle.name).read_text())
    missed = [
        task["id"]
        for task in tasks
        if task["expected_article_ids"]
        and not set(task["expected_article_ids"]) & set(task["article_texts"])
    ]
    runs = asyncio.run(benchmark(tasks, llm))
    settings = get_settings()
    payload = {
        "generated": date.today().isoformat(),
        "prompt_version": settings.prompt_version,
        "embedding_model": settings.embedding_model,
        "reranker_model": settings.reranker_model,
        "judge_model": f"{settings.groq_judge_model} (configured; not used in this benchmark)",
        "task_count": len(tasks),
        "tasks_with_no_expected_article_retrieved": missed,
        "selected_local": select_local(runs, llm["tie_margin"]),
        "runs": runs,
    }
    RAW_OUTPUT.write_text(json.dumps(payload, indent=1) + "\n")
    for run in runs:
        print(
            f"{run['provider']}:{run['model']} pass={run['passed']}/{run['n']} "
            f"json={run['valid_json']} p50={run['latency_p50_s']:.1f}s "
            f"vram={run['vram_gib']} gpu_share={run['gpu_share']}"
        )
    print(f"Selected local model: {payload['selected_local']}")


if __name__ == "__main__":
    main()
