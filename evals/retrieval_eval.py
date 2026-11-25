"""Evaluate the configured retriever on the held-out test split and write the report.

Usage: uv run python -m evals.retrieval_eval
"""

import json

from app.chat.factory import build_retriever
from app.config import PROJECT_ROOT, get_settings
from app.rag.retriever import HybridRetriever
from evals.benchmark_retrieval import evaluate, load_benchmark_config, load_questions
from evals.report_header import report_header
from evals.retrieval_metrics import choose_threshold
from evals.stats import bootstrap_ci, percentile

REPORT = PROJECT_ROOT / "reports" / "retrieval_v1.md"
RAW = PROJECT_ROOT / "reports" / "raw" / "retrieval_v1.json"
BENCH_RETRIEVAL = PROJECT_ROOT / "reports" / "raw" / "benchmark_retrieval.json"
BENCH_LLM = PROJECT_ROOT / "reports" / "raw" / "benchmark_llm.json"


def summarise(results: list[dict], resamples: int, seed: int) -> dict:
    """Mean Recall@k and MRR with 95% bootstrap intervals, plus latency."""
    positive = [r for r in results if r["expected"]]
    summary = {"n": len(positive)}
    for key in ("recall", "reciprocal_rank"):
        values = [r[key] for r in positive]
        summary[key] = sum(values) / len(values)
        summary[f"{key}_ci"] = bootstrap_ci(values, resamples, seed)
    latencies = [r["latency_ms"] for r in results]
    summary["latency_p50_ms"] = percentile(latencies, 50)
    summary["latency_p95_ms"] = percentile(latencies, 95)
    return summary


def metric_cell(summary: dict, key: str) -> str:
    """'0.900 [0.817, 0.967]'."""
    low, high = summary[f"{key}_ci"]
    return f"{summary[key]:.3f} [{low:.3f}, {high:.3f}]"


APP_SETUP = "Hybrid + reranker (the app)"


def run_stages(retriever: HybridRetriever, questions: list[dict], k: int) -> dict:
    """Run the same answerable questions with parts of the pipeline switched off."""
    positives = [q for q in questions if q["expected_article_ids"]]
    return {
        "BM25 only": evaluate(retriever, positives, k, mode="bm25", rerank=False),
        "Dense only": evaluate(retriever, positives, k, mode="dense", rerank=False),
        "Hybrid (RRF)": evaluate(retriever, positives, k, rerank=False),
        APP_SETUP: evaluate(retriever, positives, k),
    }


def paired_difference(
    first: list[dict], second: list[dict], key: str, resamples: int, seed: int
) -> str:
    """Mean per-question difference (first - second) with a 95% bootstrap interval.

    Both setups answer the same questions, so comparing them question by question is
    more precise than comparing two separate intervals.
    """
    assert [r["id"] for r in first] == [r["id"] for r in second]
    differences = [a[key] - b[key] for a, b in zip(first, second, strict=True)]
    low, high = bootstrap_ci(differences, resamples, seed)
    verdict = "no clear difference" if low <= 0 <= high else "clear difference"
    mean = sum(differences) / len(differences)
    return f"{mean:+.3f} [{low:+.3f}, {high:+.3f}] ({verdict})"


def escalation_table(results: dict[str, list[dict]], threshold: float) -> list[str]:
    """How the score threshold behaves on answerable and unanswerable questions."""
    lines = [
        "| Split | Answerable wrongly escalated | Unanswerable banking caught | Off-topic caught |",
        "|---|---|---|---|",
    ]
    for split, rows in results.items():
        cells = [split]
        for group in (
            [r for r in rows if r["expected"]],
            [r for r in rows if r["kind"] == "negative_banking"],
            [r for r in rows if r["kind"] == "negative_offtopic"],
        ):
            below = sum(r["top_score"] < threshold for r in group)
            cells.append(f"{below}/{len(group)} ({below / len(group):.0%})")
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def benchmark_sections() -> list[str]:
    """Model-comparison tables, copied from the saved benchmark runs."""
    lines: list[str] = []
    if BENCH_RETRIEVAL.exists():
        data = json.loads(BENCH_RETRIEVAL.read_text())
        lines += [
            "",
            "## Model selection: embedder and reranker (dev split only)",
            "",
            "Source: `make benchmark-retrieval`. Each row ran in its own process. VRAM is the "
            "peak PyTorch reserved while answering queries; the CUDA driver uses some more.",
            "",
            "| Embedder | Reranker | Recall@5 | MRR | p50 ms | p95 ms | Peak VRAM MiB |",
            "|---|---|---|---|---|---|---|",
        ]
        for run in data["runs"]:
            chosen = (run["embedder"], run["reranker"]) == (
                data["selected"]["embedder"],
                data["selected"]["reranker"],
            )
            mark = " **(selected)**" if chosen else ""
            lines.append(
                f"| {run['embedder']} | {run['reranker']}{mark} | {run['recall_at_k']:.3f} "
                f"| {run['mrr']:.3f} | {run['latency_p50_ms']:.0f} "
                f"| {run['latency_p95_ms']:.0f} | {run['vram_peak_mib']:.0f} |"
            )
        cpu = data["cpu_run"]
        lines += [
            "",
            f"Selected pair on **CPU**: p50 {cpu['latency_p50_ms']:.0f} ms, "
            f"p95 {cpu['latency_p95_ms']:.0f} ms (matters when Ollama needs the GPU).",
        ]
    if BENCH_LLM.exists():
        data = json.loads(BENCH_LLM.read_text())
        lines += [
            "",
            "## Model selection: local LLM",
            "",
            f"Source: `make benchmark-llm`, {data['generated']}. {data['task_count']} tasks from "
            "the dev split, with context from the retriever above (embedder and reranker released "
            "first). 'Pass' means correct behaviour, all code checks passed and, for answers, an "
            "expected article cited. It does **not** judge whether the wording is correct. "
            "With this few tasks, small gaps are noise.",
            "",
            "| Model | Pass | Behaviour correct | Valid JSON | Code checks passed | p50 s "
            "| p95 s | Output tok/s | VRAM GiB (share on GPU) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for run in data["runs"]:
            mark = " **(selected)**" if run["model"] == data["selected_local"] else ""
            vram = (
                "hosted"
                if run["vram_gib"] is None
                else f"{run['vram_gib']:.2f} ({run['gpu_share']:.0%})"
            )
            speed = "-" if run["tokens_per_second"] is None else f"{run['tokens_per_second']:.0f}"
            lines.append(
                f"| {run['provider']}:{run['model']}{mark} | {run['passed']}/{run['n']} "
                f"| {run['behaviour_correct']}/{run['n']} | {run['valid_json']}/{run['n']} "
                f"| {run['checks_passed']}/{run['n']} | {run['latency_p50_s']:.1f} "
                f"| {run['latency_p95_s']:.1f} | {speed} | {vram} |"
            )
    return lines


def main() -> None:
    """Calibrate on dev, report on test."""
    settings = get_settings()
    config = load_benchmark_config()
    retrieval, boot = config["retrieval"], config["bootstrap"]
    eval_path = PROJECT_ROOT / retrieval["eval_set"]
    dev = load_questions(eval_path, "dev")
    test = load_questions(eval_path, "test")
    retriever, _ = build_retriever(settings)
    retriever.retrieve("warm up", top_k=1)

    k = retrieval["recall_k"]
    dev_results = evaluate(retriever, dev, k)
    test_results = evaluate(retriever, test, k)
    calibrated = choose_threshold(
        [r["top_score"] for r in dev_results if r["expected"]],
        retrieval["max_false_escalation_rate"],
    )

    ablation = {
        split: {
            name: summarise(rows, boot["resamples"], boot["seed"])
            for name, rows in run_stages(retriever, questions, k).items()
        }
        for split, questions in (("test", test), ("dev", dev))
    }
    summaries = ablation["test"]
    app_rows = [r for r in test_results if r["expected"]]
    dense_rows = run_stages(retriever, test, k)["Dense only"]

    reviewed = sum(row["review_status"] == "human_reviewed" for row in dev + test)
    total_rows = len(dev) + len(test)
    lines = [
        report_header(
            "Retrieval evaluation v1",
            settings,
            eval_set=f"{retrieval['eval_set']} ({reviewed}/{total_rows} rows human-reviewed)",
            models={
                "Embedding model": settings.embedding_model,
                "Reranker model": settings.reranker_model,
                "Retrieval device": settings.retrieval_device,
                "Corpus fingerprint": retriever.corpus_fingerprint,
                "Generator LLM": "none (retrieval only)",
            },
            judge_used=False,
        ),
        "## Held-out test split",
        "",
        f"{summaries['BM25 only']['n']} questions with an expected article. Recall@{k} and MRR "
        f"count articles, not chunks. 95% bootstrap intervals ({boot['resamples']} resamples, "
        f"seed {boot['seed']}). A zero-width interval does not mean zero uncertainty.",
        "",
        f"| Setup | Recall@{k} | MRR | p50 ms | p95 ms |",
        "|---|---|---|---|---|",
    ]
    for name, summary in summaries.items():
        lines.append(
            f"| {name} | {metric_cell(summary, 'recall')} "
            f"| {metric_cell(summary, 'reciprocal_rank')} "
            f"| {summary['latency_p50_ms']:.0f} | {summary['latency_p95_ms']:.0f} |"
        )

    lines += [
        "",
        "**Paired comparison, app minus dense-only (test):**",
        "",
        f"- Recall@{k}: "
        + paired_difference(app_rows, dense_rows, "recall", boot["resamples"], boot["seed"]),
        "- MRR: "
        + paired_difference(
            app_rows, dense_rows, "reciprocal_rank", boot["resamples"], boot["seed"]
        ),
        "",
        "### Same ablation on the dev split (used for model selection)",
        "",
        f"| Setup | Recall@{k} | MRR |",
        "|---|---|---|",
        *[
            f"| {name} | {metric_cell(summary, 'recall')} "
            f"| {metric_cell(summary, 'reciprocal_rank')} |"
            for name, summary in ablation["dev"].items()
        ],
        "",
        "Compare the two tables: the chosen setup scores much higher on dev than on the "
        "held-out test questions. Dev is small, the models were chosen on it, and the two "
        "splits may differ in difficulty. **Quote the test numbers, not the dev numbers.** "
        "Nothing in the system has been changed in response to the test results.",
    ]
    lines += ["", "### By question type (the app's setup)", ""]
    lines += [f"| Group | n | Recall@{k} | MRR |", "|---|---|---|---|"]
    for field, value in [
        ("source", "banking77_eval_pool"),
        ("source", "ai_written"),
        ("kind", "single"),
        ("kind", "multi"),
    ]:
        group = [r for r in app_rows if r[field] == value]
        summary = summarise(group, boot["resamples"], boot["seed"])
        lines.append(
            f"| {value} | {len(group)} | {metric_cell(summary, 'recall')} "
            f"| {metric_cell(summary, 'reciprocal_rank')} |"
        )

    lines += ["", "### Questions where an expected article was missed (test)", ""]
    questions = {q["id"]: q["question"] for q in test}
    misses = [r for r in app_rows if r["recall"] < 1]
    lines += [
        f'- `{r["id"]}` "{questions[r["id"]]}": expected {r["expected"]}, got {r["top_articles"]}'
        for r in misses
    ] or ["- none"]

    lines += [
        "",
        "## Escalation threshold",
        "",
        "Calibrated on **dev** only: the highest top-reranker-score cut-off that wrongly "
        f"escalates at most {retrieval['max_false_escalation_rate']:.0%} of answerable dev "
        f"questions. Calibrated value: **{calibrated:.4f}**. Value in config: "
        f"**{settings.escalation_score_threshold:.4f}**. The table uses the config value. The "
        "dev row is optimistic because the value was chosen on it. The threshold is only one "
        "safety layer; the model can also choose to escalate.",
        "",
        *escalation_table(
            {"dev": dev_results, "test": test_results}, settings.escalation_score_threshold
        ),
    ]
    lines += benchmark_sections()
    lines += [
        "",
        "## Limitations",
        "",
        "- Articles, the AI-written questions and all labels were drafted by AI. Unless rows "
        "are marked human-reviewed above, no person has checked them. Scores are likely "
        "optimistic.",
        "- The real Banking77 messages were drawn at random, but three too vague to label "
        "were removed, which makes the set a little easier.",
        "- The knowledge base is small (see the article count in `data/kb`), so retrieval is "
        "much easier than on a large corpus.",
        "- Model choice used only 30 dev questions, so close candidates cannot be separated.",
        "- Latency is one run on one laptop GPU, one query at a time.",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines))
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(
        json.dumps(
            {
                "calibrated_threshold": calibrated,
                "dev": dev_results,
                "test": test_results,
                "summaries": summaries,
            },
            indent=1,
        )  # fmt: skip
        + "\n"
    )
    print(f"Wrote {REPORT.relative_to(PROJECT_ROOT)}; calibrated threshold {calibrated:.4f}")
    for name, summary in summaries.items():
        print(f"  {name}: recall={summary['recall']:.3f} mrr={summary['reciprocal_rank']:.3f}")


if __name__ == "__main__":
    main()
