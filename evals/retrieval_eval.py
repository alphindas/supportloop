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
BENCH_LLM_AUTO = PROJECT_ROOT / "reports" / "raw" / "benchmark_llm_auto_offload.json"


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


# name -> (retrieval mode, use the reranker)
SETUPS = {
    "BM25 only": ("bm25", False),
    "Dense only": ("dense", False),
    "Hybrid (RRF)": ("hybrid", False),
    "Dense + reranker": ("dense", True),
    "Hybrid + reranker": ("hybrid", True),
}
RERANKED = {"dense": "Dense + reranker", "hybrid": "Hybrid + reranker"}


def run_stages(retriever: HybridRetriever, questions: list[dict], k: int) -> dict:
    """Run the same answerable questions with parts of the pipeline switched off."""
    positives = [q for q in questions if q["expected_article_ids"]]
    return {
        name: evaluate(retriever, positives, k, mode=mode, rerank=rerank)
        for name, (mode, rerank) in SETUPS.items()
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


def mean(rows: list[dict], key: str) -> float:
    """Average of one metric."""
    return sum(r[key] for r in rows) / len(rows)


def simplification_decision(runs: dict[str, list[dict]], tie_margin: float) -> dict:
    """Apply the rule in config/benchmark.yaml: may BM25 be dropped?"""
    gaps = {
        key: mean(runs["Dense + reranker"], key) - mean(runs["Hybrid + reranker"], key)
        for key in ("recall", "reciprocal_rank")
    }
    # The tiny allowance stops floating-point rounding from flipping an exact tie.
    use_dense = all(gap >= -tie_margin - 1e-9 for gap in gaps.values())
    return {"mode": "dense" if use_dense else "hybrid", "gaps": gaps}


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


def mistake_table(runs: list[dict]) -> list[str]:
    """Not all mistakes are equal: answering when a person was needed is the risky one."""
    lines = [
        "| Model | Answered when it should have handed off or refused | Handed off or refused "
        "an answerable question | Refused when it should have handed off |",
        "|---|---|---|---|",
    ]
    for run in runs:
        pairs = [(r["expected"], json.loads(r["reply"]).get("behavior")) for r in run["rows"]
                 if r["valid_json"]]  # fmt: skip
        risky = sum(want != "answer" and got == "answer" for want, got in pairs)
        cautious = sum(want == "answer" and got != "answer" for want, got in pairs)
        wrong_refusal = sum(want == "escalate" and got == "refuse" for want, got in pairs)
        lines.append(
            f"| {run['provider']}:{run['model']} | {risky} | {cautious} | {wrong_refusal} |"
        )
    lines += [
        "",
        "These are the model's raw choices. In the app, the retrieval score threshold and the "
        "output checks run afterwards and can turn an answer into a hand-off.",
    ]
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
            "Source: `make benchmark-retrieval`, run with retrieval mode "
            f"`{data['runs'][0].get('retrieval_mode', 'hybrid')}`. "
            "Each row ran in its own process. VRAM is the "
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
        missed = data["tasks_with_no_expected_article_retrieved"]
        lines += [
            "",
            f"Hosted reference is not part of the local choice. Answerable tasks whose expected "
            f"article was not retrieved: {len(missed)}.",
        ]
        if BENCH_LLM_AUTO.exists():
            earlier = json.loads(BENCH_LLM_AUTO.read_text())
            shares = [
                f"{r['model']} {r['gpu_share']:.0%} on GPU, p50 {r['latency_p50_s']:.1f} s, "
                f"pass {r['passed']}/{r['n']}"
                for r in earlier["runs"]
                if r["provider"] == "ollama"
            ]
            lines += [
                "",
                "An earlier run left GPU placement to Ollama (no `num_gpu` setting; saved in "
                f"`{BENCH_LLM_AUTO.name}`): " + "; ".join(shares) + ".",
            ]
        lines += ["", "**Which mistakes each model made**", "", *mistake_table(data["runs"])]
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
    test_runs = run_stages(retriever, test, k)
    rule = config["simplification"]
    decision = simplification_decision(
        test_runs if rule["split"] == "test" else run_stages(retriever, dev, k), rule["tie_margin"]
    )
    app_name = RERANKED[settings.retrieval_mode]
    app_rows = test_runs[app_name]
    summaries = ablation["test"]

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
                "Retrieval mode": settings.retrieval_mode,
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
        label = f"{name} **(the app)**" if name == app_name else name
        lines.append(
            f"| {label} | {metric_cell(summary, 'recall')} "
            f"| {metric_cell(summary, 'reciprocal_rank')} "
            f"| {summary['latency_p50_ms']:.0f} | {summary['latency_p95_ms']:.0f} |"
        )

    pairs = [
        ("Dense + reranker", "Hybrid + reranker"),
        (app_name, "Dense only"),
    ]
    lines += ["", "**Paired comparisons on test (first minus second):**", ""]
    for first, second in pairs:
        for label, key in ((f"Recall@{k}", "recall"), ("MRR", "reciprocal_rank")):
            difference = paired_difference(
                test_runs[first], test_runs[second], key, boot["resamples"], boot["seed"]
            )
            lines.append(f"- {first} minus {second}, {label}: {difference}")
    dropped = decision["mode"] == "dense"
    lines += [
        "",
        "### Decision: is BM25 needed?",
        "",
        f"Rule (written in `config/benchmark.yaml` before dense + reranker was measured): use "
        f"dense + reranker if its mean is at most {rule['tie_margin']} below hybrid + reranker "
        f"on both Recall@{k} and MRR, on the {rule['split']} split. Measured gaps: "
        f"Recall@{k} {decision['gaps']['recall']:+.3f}, "
        f"MRR {decision['gaps']['reciprocal_rank']:+.3f}. **Rule result: "
        f"{'drop BM25 (dense + reranker)' if dropped else 'keep the hybrid pipeline'}.** "
        f"The app is configured as `{settings.retrieval_mode}`.",
        "",
        "**Caveat:** this decision was made on the test split. For the choice between these "
        "two pipelines, the test numbers are therefore no longer unseen, and a tie is not "
        "proof that the two are equal. A check on new questions is needed.",
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
        "The reranked setups score much higher on dev than on the test questions. Dev is "
        "small, the models were chosen on it, and the two splits may differ in difficulty. "
        "**Quote the test numbers, not the dev numbers.** The only change made in response "
        "to test results is the BM25 decision above; no thresholds, weights or text were "
        "tuned on test.",
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
