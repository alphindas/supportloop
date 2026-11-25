"""Benchmark embedder and reranker combinations.

Each combination runs in its own process, so GPU memory is fully freed between models
and each VRAM reading belongs to one combination only.

Usage: uv run python -m evals.benchmark_retrieval
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

from app.config import PROJECT_ROOT, get_settings
from app.rag.chunking import chunk_articles, corpus_fingerprint
from app.rag.kb import load_articles
from app.rag.models import build_embedder, build_reranker
from app.rag.retriever import HybridRetriever, RetrievalConfig, build_index
from evals.retrieval_metrics import distinct_articles, recall_at_k, reciprocal_rank

RAW_OUTPUT = PROJECT_ROOT / "reports" / "raw" / "benchmark_retrieval.json"


def load_benchmark_config() -> dict:
    """Read config/benchmark.yaml."""
    return yaml.safe_load((PROJECT_ROOT / "config" / "benchmark.yaml").read_text())


def load_questions(path: Path, split: str) -> list[dict]:
    """Read one split of the retrieval set."""
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [row for row in rows if row["split"] == split]


def retrieval_config() -> RetrievalConfig:
    """Retrieval settings from config."""
    s = get_settings()
    return RetrievalConfig(s.bm25_top_k, s.dense_top_k, s.rrf_k, s.rerank_candidates)


def evaluate(
    retriever: HybridRetriever,
    questions: list[dict],
    recall_k: int,
    mode: str = "hybrid",
    rerank: bool = True,
) -> list[dict]:
    """Run every question once and record the ranking, metrics and latency."""
    results = []
    for row in questions:
        started = time.perf_counter()
        found = retriever.retrieve(
            row["question"], top_k=retriever.config.rerank_candidates, mode=mode, rerank=rerank
        )
        latency_ms = (time.perf_counter() - started) * 1000
        ranked = distinct_articles([r.chunk.article_id for r in found])
        expected = row["expected_article_ids"]
        results.append(
            {
                "id": row["id"],
                "kind": row["kind"],
                "source": row["source"],
                "expected": expected,
                "top_articles": ranked[:recall_k],
                "recall": recall_at_k(ranked, expected, recall_k) if expected else None,
                "reciprocal_rank": reciprocal_rank(ranked, expected) if expected else None,
                "top_score": found[0].rerank_score if found else None,
                "latency_ms": latency_ms,
            }
        )
    return results


def run_one(embedder_name: str, reranker_name: str, device: str) -> dict:
    """Measure one combination on the dev split. Runs inside its own process."""
    import torch

    from evals.stats import percentile

    settings, config = get_settings(), load_benchmark_config()["retrieval"]
    chunks = chunk_articles(
        load_articles(settings.resolve(settings.kb_dir)), settings.chunk_max_words
    )
    questions = load_questions(PROJECT_ROOT / config["eval_set"], "dev")

    embedder = build_embedder(embedder_name, device)
    reranker = build_reranker(reranker_name, device)
    with tempfile.TemporaryDirectory() as directory:
        started = time.perf_counter()
        build_index(chunks, embedder, Path(directory))
        index_seconds = time.perf_counter() - started
        retriever = HybridRetriever(chunks, embedder, reranker, Path(directory), retrieval_config())
        retriever.retrieve("warm up", top_k=1)  # first call is slower; do not time it
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        results = evaluate(retriever, questions, config["recall_k"])

    positive = [r for r in results if r["expected"]]
    latencies = [r["latency_ms"] for r in results]
    return {
        "embedder": embedder_name,
        "reranker": reranker_name,
        "device": device,
        "recall_at_k": sum(r["recall"] for r in positive) / len(positive),
        "mrr": sum(r["reciprocal_rank"] for r in positive) / len(positive),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "index_seconds": index_seconds,
        # Peak memory PyTorch reserved while answering queries. The CUDA driver itself
        # uses some more on top of this.
        "vram_peak_mib": torch.cuda.max_memory_reserved() / 2**20 if device == "cuda" else None,
        "corpus_fingerprint": corpus_fingerprint(chunks),
        "results": results,
    }


def select(runs: list[dict], tie_margin: float, tie_breaker: str) -> dict:
    """Apply the rule written in config/benchmark.yaml."""
    best_recall = max(r["recall_at_k"] for r in runs)
    best_mrr = max(r["mrr"] for r in runs)
    tied = [
        r
        for r in runs
        if best_recall - r["recall_at_k"] <= tie_margin and best_mrr - r["mrr"] <= tie_margin
    ]
    # If no run is near the best on both metrics, fall back to the best MRR.
    return min(tied, key=lambda r: r[tie_breaker]) if tied else max(runs, key=lambda r: r["mrr"])


def spawn(embedder: str, reranker: str, device: str) -> dict:
    """Run one combination in a fresh Python process and read back its JSON result."""
    with tempfile.NamedTemporaryFile(suffix=".json") as output:
        subprocess.run(
            [sys.executable, "-m", "evals.benchmark_retrieval", "--one",
             embedder, reranker, device, output.name],
            cwd=PROJECT_ROOT, check=True,
        )  # fmt: skip
        return json.loads(Path(output.name).read_text())


def main() -> None:
    """Run all combinations on the GPU, then time the winner on the CPU."""
    if len(sys.argv) > 1 and sys.argv[1] == "--one":
        embedder, reranker, device, output = sys.argv[2:6]
        Path(output).write_text(json.dumps(run_one(embedder, reranker, device)))
        return

    config = load_benchmark_config()["retrieval"]
    runs = []
    for embedder in config["embedders"]:
        for reranker in config["rerankers"]:
            run = spawn(embedder, reranker, "cuda")
            runs.append(run)
            print(
                f"{embedder} + {reranker}: recall={run['recall_at_k']:.3f} mrr={run['mrr']:.3f} "
                f"p50={run['latency_p50_ms']:.0f}ms vram={run['vram_peak_mib']:.0f}MiB",
                flush=True,
            )
    winner = select(runs, config["tie_margin"], config["tie_breaker"])
    print(f"Selected on dev: {winner['embedder']} + {winner['reranker']}")
    print("Timing the selected combination on CPU (needed if Ollama takes the GPU)...", flush=True)
    cpu_run = spawn(winner["embedder"], winner["reranker"], "cpu")
    print(f"CPU p50={cpu_run['latency_p50_ms']:.0f}ms p95={cpu_run['latency_p95_ms']:.0f}ms")

    RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs": runs,
        "selected": {"embedder": winner["embedder"], "reranker": winner["reranker"]},
        "cpu_run": cpu_run,
    }
    RAW_OUTPUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"Saved {RAW_OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
