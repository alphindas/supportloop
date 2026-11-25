"""Turn saved eval results into metrics and a markdown report. Calls no model."""

import json
from collections.abc import Callable
from pathlib import Path

from app.config import PROJECT_ROOT, Settings
from evals.report_header import report_header
from evals.stats import bootstrap_percentile, bootstrap_ratio, cohens_kappa

HUMAN_DIR = PROJECT_ROOT / "evals" / "human_review"


class Rates:
    """Computes rates with 95% bootstrap intervals, using one seed throughout."""

    def __init__(self, resamples: int, seed: int) -> None:
        self.resamples, self.seed = resamples, seed

    def share(
        self, rows: list[dict], hit: Callable[[dict], bool], among: Callable[[dict], bool]
    ) -> str:
        """'0.812 [0.744, 0.875] (n=96)' for the share of `among` rows where `hit` is true."""
        result = bootstrap_ratio(
            [float(among(r) and hit(r)) for r in rows],
            [float(among(r)) for r in rows],
            self.resamples,
            self.seed,
        )
        if result is None:
            return "undefined (n=0)"
        value, low, high = result
        return f"{value:.3f} [{low:.3f}, {high:.3f}] (n={sum(among(r) for r in rows)})"

    def percentile(self, values: list[float], q: float, unit: str) -> str:
        """A percentile with its interval."""
        if not values:
            return "no data"
        value, low, high = bootstrap_percentile(values, q, self.resamples, self.seed)
        return f"{value:.0f} {unit} [{low:.0f}, {high:.0f}]"

    def mean(self, values: list[float]) -> str:
        """A mean with its interval."""
        if not values:
            return "no data"
        value, low, high = bootstrap_ratio(values, [1.0] * len(values), self.resamples, self.seed)
        return f"{value:.0f} [{low:.0f}, {high:.0f}] (n={len(values)})"


def auc(positive: list[float], negative: list[float]) -> float | None:
    """Chance that a random passed answer has a higher score than a random failed one.
    0.5 means the score tells us nothing."""
    if not positive or not negative:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positive for n in negative)
    return wins / (len(positive) * len(negative))


def load_human_review(config_name: str) -> list[dict]:
    """The human's verdicts, if any have been recorded."""
    path = HUMAN_DIR / f"{config_name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def human_section(reviews: list[dict], wanted: int) -> list[str]:
    """Judge-human agreement, or a clear statement that it has not been done."""
    lines = ["## Judge versus human", ""]
    if not reviews:
        return [
            *lines,
            f"**Not done yet.** A person must review {wanted} judge decisions "
            "(`make human-review`). Until then the judge-based numbers above are unvalidated.",
        ]
    human = [r["human"] for r in reviews]
    judge = [r["judge"] for r in reviews]
    agree = sum(h == j for h, j in zip(human, judge, strict=True))
    kappa = cohens_kappa(human, judge)
    cells = {
        (h, j): sum(a is h and b is j for a, b in zip(human, judge, strict=True))
        for h in (True, False)
        for j in (True, False)
    }
    status = "" if len(reviews) >= wanted else f" **Incomplete: target is {wanted}.**"
    return [
        *lines,
        f"{len(reviews)} decisions reviewed by a person, without seeing the judge's verdict "
        f"first.{status}",
        "",
        f"- Agreement: **{agree}/{len(reviews)} ({agree / len(reviews):.0%})**",
        "- Cohen's kappa: "
        + ("undefined (only one kind of verdict)" if kappa is None else f"**{kappa:.2f}**"),
        "",
        "| | Judge: pass | Judge: fail |",
        "|---|---|---|",
        f"| Human: pass | {cells[True, True]} | {cells[True, False]} |",
        f"| Human: fail | {cells[False, True]} | {cells[False, False]} |",
        "",
        "One reviewer and a small sample: treat kappa as rough.",
    ]


def metric_lines(rows: list[dict], rates: Rates) -> list[str]:
    """All the headline tables."""

    def every(_: dict) -> bool:
        return True

    def passed(r: dict) -> bool:
        return r["passed"] is True

    def expected(*behaviours: str) -> Callable[[dict], bool]:
        return lambda r: r["expected_behavior"] in behaviours

    def judged(r: dict) -> bool:
        return r["verdict"] is not None

    def answered_expected(r: dict) -> bool:
        return r["checks"]["citation_ok"] is not None

    lines = [
        "## Headline results",
        "",
        "Values are shares from 0 to 1 with 95% bootstrap intervals; n is the number of "
        "tasks in the denominator.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| **Pass rate (all tasks)** | {rates.share(rows, passed, every)} |",
        f"| Behaviour accuracy | "
        f"{rates.share(rows, lambda r: r['checks']['behaviour_correct'], every)} |",
        f"| Faithfulness (judged replies with model text) | "
        f"{rates.share(rows, lambda r: r['verdict']['faithful'], judged)} |",
        "| Correctness (judged replies to answerable tasks) | "
        + rates.share(
            rows,
            lambda r: r["verdict"]["correct"],
            lambda r: judged(r) and r["expected_behavior"] == "answer",
        )
        + " |",
        f"| Citation accuracy (answerable tasks the bot answered) | "
        f"{rates.share(rows, lambda r: r['checks']['citation_ok'], answered_expected)} |",
        "| Escalation precision | "
        + rates.share(
            rows,
            lambda r: r["expected_behavior"] == "escalate",
            lambda r: r["behavior"] == "escalate",
        )
        + " |",
        f"| Escalation recall | "
        f"{rates.share(rows, lambda r: r['behavior'] == 'escalate', expected('escalate'))} |",
        "| **Risky errors**: answered when it should not have | "
        + rates.share(rows, lambda r: r["behavior"] == "answer", expected("escalate", "refuse"))
        + " |",
        "",
        "### Pass rate by expected behaviour",
        "",
        "| Expected | Pass rate |",
        "|---|---|",
        *[
            f"| {b} | {rates.share(rows, passed, expected(b))} |"
            for b in ("answer", "escalate", "refuse")
        ],
        "",
        "### Pass rate by task category",
        "",
        "| Category | Pass rate |",
        "|---|---|",
        *[
            f"| {c} | {rates.share(rows, passed, lambda r, c=c: r['category'] == c)} |"
            for c in dict.fromkeys(r["category"] for r in rows)
        ],
        "",
        "### Expected against actual behaviour",
        "",
        "| Expected \\ Got | answer | escalate | refuse |",
        "|---|---|---|---|",
    ]
    for want in ("answer", "escalate", "refuse"):
        counts = [
            sum(r["expected_behavior"] == want and r["behavior"] == got for r in rows)
            for got in ("answer", "escalate", "refuse")
        ]
        lines.append(f"| {want} | " + " | ".join(str(c) for c in counts) + " |")

    with_llm = [r for r in rows if r["input_tokens"] is not None]
    latencies = [r["latency_ms"] for r in with_llm if r["latency_ms"] is not None]
    tokens = [r["input_tokens"] + r["output_tokens"] for r in with_llm]
    lines += [
        "",
        "## Latency and tokens",
        "",
        "Only tasks that called the LLM. Latency is from each task's first, uncached run, "
        "without time spent waiting on rate limits. It includes retrieval.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Latency p50 | {rates.percentile(latencies, 50, 'ms')} (n={len(latencies)}) |",
        f"| Latency p95 | {rates.percentile(latencies, 95, 'ms')} |",
        f"| Tokens per reply (input + output), mean | {rates.mean(tokens)} |",
        f"| Judge tokens used for this run | {sum(r.get('judge_tokens') or 0 for r in rows):,} |",
    ]

    pii = [r for r in rows if r["checks"]["pii_ok"] is not None]
    attacks = [r for r in rows if r["checks"]["injection_contained"] is not None]
    lines += [
        "",
        "## Safety checks",
        "",
        f"- **PII:** planted fake values were absent from the redacted message, search "
        f"query, model reply and answer in {sum(r['checks']['pii_ok'] for r in pii)}/{len(pii)} "
        "tasks. One redaction bug found while building this set was fixed before the first run.",
        f"- **Injection, stopped by pattern rules before the model:** "
        f"{sum(r['stopped_by_rules'] for r in attacks)}/{len(attacks)}.",
        f"- **Injection, attacker got no model-written text:** "
        f"{sum(r['checks']['injection_contained'] for r in attacks)}/{len(attacks)}.",
        f"- **Injection, refused as expected:** "
        f"{sum(r['behavior'] == 'refuse' for r in attacks)}/{len(attacks)}.",
        "- These attacks were written by the same AI that wrote the rules. They are not "
        "a measure of resistance to a real attacker.",
    ]
    shown = [r for r in rows if r["shown_text"] and r["passed"] is not None]
    good = [r["confidence"] for r in shown if r["passed"]]
    bad = [r["confidence"] for r in shown if not r["passed"]]
    score = auc(good, bad)
    lines += [
        "",
        "## Does the confidence score predict a good reply?",
        "",
        f"Among replies with model text: {len(good)} passed, {len(bad)} failed. "
        + (
            "Not enough of both to say."
            if score is None
            else f"AUC = {score:.2f} (0.5 = no information, 1.0 = perfect ranking). "
            "Confidence is the reranker's top score, not a probability."
        ),
        "",
        "A number check also runs inside the app, so replies with unsupported numbers are "
        "replaced before grading. The number rule here therefore cannot show how often the "
        "model invents numbers.",
    ]
    return lines


def failure_lines(rows: list[dict]) -> list[str]:
    """Every failed task, so nothing is hidden behind an average."""
    lines = [
        "## Failed tasks",
        "",
        "| Task | Category | Expected | Got | Why |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        if r["passed"] is not False:
            continue
        why = []
        if not r["checks"]["behaviour_correct"]:
            why.append("wrong behaviour")
        for key in ("citation_ok", "numbers_ok", "pii_ok"):
            if r["checks"][key] is False:
                why.append(key.replace("_ok", " check"))
        verdict = r["verdict"]
        if verdict and not verdict["faithful"]:
            why.append(f"unfaithful: {verdict['faithfulness_reason']}")
        if verdict and r["expected_behavior"] == "answer" and not verdict["correct"]:
            why.append(f"incorrect: {verdict['correctness_reason']}")
        if r["escalation_reasons"]:
            why.append("reasons: " + ", ".join(r["escalation_reasons"]))
        text = "; ".join(why).replace("|", "/").replace("\n", " ")
        lines.append(
            f"| `{r['id']}` {r['input'][:70].replace('|', '/')} | {r['category']} "
            f"| {r['expected_behavior']} | {r['behavior']} | {text[:260]} |"
        )
    return lines


def write_report(
    path: Path,
    settings: Settings,
    run: dict,
    rates: Rates,
    human_sample_size: int,
) -> None:
    """Build the whole report from a saved run. Rebuilding gives identical numbers."""
    meta, rows = run["meta"], run["rows"]
    reviewed = meta["rows_human_reviewed"]
    unjudged = sum(r["passed"] is None for r in rows)
    lines = [
        report_header(
            f"Answer evaluation, eval set {meta['eval_set_version']}: {meta['config_name']}",
            settings,
            eval_set=f"{meta['eval_set']} ({reviewed}/{meta['task_count']} rows human-reviewed)",
            models=meta["models"],
            judge_used=True,
            overrides=meta["header"],
        ),
    ]
    if len(rows) < meta["task_count"] or unjudged:
        lines.append(
            f"> **INCOMPLETE RUN:** {len(rows)}/{meta['task_count']} tasks run, {unjudged} "
            "still need a judge verdict. Unjudged tasks count as not passed. Run `make eval` "
            "again to continue.\n"
        )
    lines += metric_lines(rows, rates)
    if meta.get("retrieval_check"):
        lines += ["", *meta["retrieval_check"]]
    lines += ["", *human_section(load_human_review(meta["config_name"]), human_sample_size)]
    lines += [
        "",
        "## How to read this",
        "",
        "- Tasks, labels and reference answers are AI-drafted. Unless the header says rows "
        "were human-reviewed, no person has checked them.",
        "- The judge is itself a language model and can be wrong.",
        "- Intervals cover the luck of which tasks are in the set. They do not cover model "
        "randomness (reruns reuse cached replies), judge mistakes or unrealistic tasks.",
        "- About 150 tasks can only reliably separate systems that differ a lot.",
        "",
        *failure_lines(rows),
    ]
    path.write_text("\n".join(lines) + "\n")
