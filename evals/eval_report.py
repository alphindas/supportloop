"""Turn saved eval results into metrics and a markdown report. Calls no model."""

import json
from collections.abc import Callable
from pathlib import Path

import yaml

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


def review_path(config_name: str, round_number: int) -> Path:
    """Where one round's verdicts are saved. Round 1 keeps the plain file name."""
    suffix = "" if round_number == 1 else f".round{round_number}"
    return HUMAN_DIR / f"{config_name}{suffix}.jsonl"


def load_human_review(config_name: str, round_number: int = 1) -> list[dict]:
    """One round's verdicts, if any. Who gave them is stated in the notes file. In each
    record, the 'human' field is that reviewer's verdict, whoever the reviewer was."""
    path = review_path(config_name, round_number)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_review_notes(config_name: str) -> dict:
    """Who reviewed, and written explanations for each round.

    Without a notes file the report says the reviewer is not recorded. It never assumes
    the reviewer was a person.
    """
    notes = {
        "reviewer": "reviewer not recorded",
        "short_label": "Reviewer",
        "summary": "Who gave these verdicts is not recorded, so do not read them as human "
        "validation of the judge.",
        "rounds": {},
    }
    path = HUMAN_DIR / f"{config_name}.notes.yaml"
    if path.exists():
        notes.update(yaml.safe_load(path.read_text(encoding="utf-8")))
    return notes


def agreement_table(reviews: list[dict], label: str) -> list[str]:
    """Agreement, chance agreement, kappa, a split by verdict type and the 2x2 table."""
    total = len(reviews)
    human = [r["human"] for r in reviews]
    judge = [r["judge"] for r in reviews]
    agree = sum(h == j for h, j in zip(human, judge, strict=True))
    human_pass, judge_pass = sum(human) / total, sum(judge) / total
    by_chance = human_pass * judge_pass + (1 - human_pass) * (1 - judge_pass)
    kappa = cohens_kappa(human, judge)
    cells = {
        (h, j): sum(a is h and b is j for a, b in zip(human, judge, strict=True))
        for h in (True, False)
        for j in (True, False)
    }
    by_dimension = []
    for dimension in ("faithful", "correct"):
        group = [r for r in reviews if r["dimension"] == dimension]
        same = sum(r["human"] == r["judge"] for r in group)
        by_dimension.append(f"{dimension} {same}/{len(group)}")
    return [
        f"- Agreement: **{agree}/{total} ({agree / total:.0%})**",
        f"- Agreement expected by chance, given how often each said pass: {by_chance:.0%}",
        "- Cohen's kappa: "
        + ("undefined (only one kind of verdict)" if kappa is None else f"**{kappa:.2f}**"),
        f"- Agreement by verdict type: {', '.join(by_dimension)}",
        "",
        "| | Judge: pass | Judge: fail |",
        "|---|---|---|",
        f"| {label}: pass | {cells[True, True]} | {cells[True, False]} |",
        f"| {label}: fail | {cells[False, True]} | {cells[False, False]} |",
    ]


def human_section(config_name: str, rows: list[dict], wanted: int) -> list[str]:
    """Each review round on its own. Rounds are never pooled."""
    first = load_human_review(config_name, 1)
    if not first:
        return [
            "## Judge review",
            "",
            f"**Not done yet.** A person must review {wanted} judge decisions "
            "(`make human-review ROUND=1`). Until then the judge-based numbers above are "
            "unvalidated.",
        ]
    notes = load_review_notes(config_name)
    rounds = notes["rounds"]
    lines = [
        f"## Judge versus {notes['reviewer']}",
        "",
        notes["summary"].strip(),
        "",
        "**Rounds are reported separately and not pooled.** 30 items is a small sample: "
        "treat kappa as rough.",
    ]
    failed = {r["id"] for r in rows if r["passed"] is False}
    for number in (1, 2):
        reviews = load_human_review(config_name, number)
        if number == 2 and not reviews and 2 not in rounds:
            continue
        lines += ["", f"### Round {number}", ""]
        if rounds.get(number):
            lines += [rounds[number].strip(), ""]
        if number == 1:
            if len(reviews) < wanted:
                lines += [f"**Incomplete: {len(reviews)}/{wanted}.**", ""]
            lines += agreement_table(reviews, notes["short_label"])
        elif len(reviews) < wanted:
            # Showing partial results would tell the reviewer how the judge is voting.
            lines.append(
                f"**Pending: {len(reviews)}/{wanted} recorded.** Results stay hidden until the "
                "round is complete. Before and during the round, do not read the 'Failed "
                "tasks' table below: it quotes the judge."
            )
        else:
            lines += agreement_table(reviews, notes["short_label"])
            listed = len({r["id"] for r in reviews} & failed)
            lines += [
                "",
                f"{listed} of the {len(reviews)} tasks in this round failed the eval, so this "
                "report lists them under 'Failed tasks', often with the judge's reason. A "
                "reviewer who was shown that list first was not blind on those items.",
            ]
    return lines


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


def failure_reason(row: dict) -> str:
    """The single main reason a task failed. Checked in this order."""
    if not row["checks"]["behaviour_correct"]:
        return f"wrong behaviour: expected {row['expected_behavior']}, got {row['behavior']}"
    if row["checks"]["pii_ok"] is False:
        return "personal data leaked"
    verdict = row["verdict"]
    if row["checks"]["numbers_ok"] is False:
        return "right behaviour, unsupported number"
    if verdict and not verdict["faithful"]:
        return "right behaviour, judged unfaithful"
    if row["checks"]["citation_ok"] is False:
        return "right behaviour, citation check failed"
    return "right behaviour, judged incorrect (often: part of the reference missing)"


def failure_summary(rows: list[dict]) -> list[str]:
    """How many failures had each main reason."""
    failed = [r for r in rows if r["passed"] is False]
    counts: dict[str, int] = {}
    for row in failed:
        counts[failure_reason(row)] = counts.get(failure_reason(row), 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        f"## Why tasks failed ({len(failed)} of {len(rows)})",
        "",
        "Each failed task is counted once. Reasons involving the judge are only as good as "
        "the judge.",
        "",
        "| Main reason | Tasks |",
        "|---|---|",
        *[f"| {reason} | {count} |" for reason, count in ordered],
    ]


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
    lines += ["", *failure_summary(rows)]
    if meta.get("retrieval_check"):
        lines += ["", *meta["retrieval_check"]]
    lines += ["", *human_section(meta["config_name"], rows, human_sample_size)]
    lines += [
        "",
        "## How to read this",
        "",
        "- Tasks, labels and reference answers are AI-drafted. Unless the header says rows "
        "were human-reviewed, no person has checked them.",
        "- The judge is itself a language model and can be wrong. Check the judge review "
        "section above before relying on its scores.",
        "- Intervals cover the luck of which tasks are in the set. They do not cover model "
        "randomness (reruns reuse cached replies), judge mistakes or unrealistic tasks.",
        "- About 150 tasks can only reliably separate systems that differ a lot.",
        "",
        *failure_lines(rows),
    ]
    path.write_text("\n".join(lines) + "\n")
