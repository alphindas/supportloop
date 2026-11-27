"""Old number check against the new claim check, on three sets. No LLM calls.

Old = every amount appears in a cited article. New = old, plus the claim check.

Usage: uv run python -m evals.fee_check
"""

import json
from pathlib import Path

import yaml

from app.config import PROJECT_ROOT, get_settings
from app.guardrails.claims import claim_problems, load_facts
from app.guardrails.output import ungrounded_numbers
from app.rag.kb import load_articles
from evals.report_header import report_header
from evals.stats import wilson_interval

SETS = PROJECT_ROOT / "evals" / "sets"
RAW = PROJECT_ROOT / "reports" / "raw"
REPORT = PROJECT_ROOT / "reports" / "fee_check_v1.md"
EVAL_V1 = RAW / "eval_v1_groq-openai-gpt-oss-20b_prompt-v1.json"


def flags(text: str, cited: list[str], texts: dict[str, str], message: str, facts: dict):
    """(old check blocks it, new check blocks it, claim problems)."""
    shown = [texts[a] for a in cited if a in texts]
    old = bool(ungrounded_numbers(text, shown, message))
    problems = claim_problems(text, [a for a in cited if a in texts], facts)
    return old, old or bool(problems), problems


def share(count: int, total: int) -> str:
    """'3/21 = 0.14 [0.05, 0.35]'."""
    if not total:
        return "0/0"
    low, high = wilson_interval(count, total)
    return f"{count}/{total} = {count / total:.2f} [{low:.2f}, {high:.2f}]"


def table(rows: list[dict]) -> list[str]:
    """Caught, missed and wrongly blocked for both checks."""
    wrong = [r for r in rows if r["wrong"]]
    right = [r for r in rows if not r["wrong"]]
    lines = [
        "| | Old number check | New check (number + claim) |",
        "|---|---|---|",
    ]
    for label, group, want in (
        ("Wrong claims caught", wrong, True),
        ("Wrong claims missed", wrong, False),
        ("Correct ones wrongly blocked", right, True),
    ):
        cells = [share(sum(r[k] is want for r in group), len(group)) for k in ("old", "new")]
        lines.append(f"| {label} | {cells[0]} | {cells[1]} |")
    return lines


def frozen_rows(facts: dict) -> list[dict]:
    """The 42 frozen claims, each checked against its own article."""
    articles = {a.id: f"{a.title}\n{a.body}" for a in load_articles(PROJECT_ROOT / "data" / "kb")}
    rows = []
    for case in yaml.safe_load((SETS / "fee_claims_v1.yaml").read_text())["cases"]:
        article = case["article_id"]
        old, new, problems = flags(case["claim"], [article], articles, "", facts)
        rows.append(
            {
                "id": case["id"],
                "text": case["claim"],
                "wrong": case["expected"] == "wrong",
                "human": case["review_status"].startswith("human-marked"),
                "old": old,
                "new": new,
                "problems": problems,
            }
        )
    return rows


def reply_rows(replies: list[dict], labels: dict, facts: dict) -> list[dict]:
    """Labelled replies: {id, text, cited, context, message}."""
    wrong = set(labels["wrong"])
    wanted = wrong | set(labels["correct"])
    rows = []
    for reply in replies:
        if reply["id"] not in wanted:
            continue
        old, new, problems = flags(
            reply["text"], reply["cited"], reply["context"], reply["message"], facts
        )
        rows.append(
            {
                "id": reply["id"],
                "text": reply["text"],
                "wrong": reply["id"] in wrong,
                "old": old,
                "new": new,
                "problems": problems,
            }
        )
    if len(rows) != len(wanted):
        raise SystemExit("A labelled reply is missing from the saved replies.")
    return rows


def listing(rows: list[dict], title: str, keep) -> list[str]:
    """The cases of one kind, so every number can be checked by hand."""
    chosen = [r for r in rows if keep(r)]
    lines = ["", f"**{title}: {len(chosen)}**"]
    for row in chosen:
        detail = f" ({'; '.join(row['problems'])})" if row["problems"] else ""
        text = " ".join(row["text"].split())
        lines.append(f"- `{row['id']}`: {text}{detail}")
    return lines


def section(title: str, intro: str, rows: list[dict]) -> list[str]:
    """One set: counts, then what was missed and what was wrongly blocked."""
    return [
        "",
        f"## {title}",
        "",
        intro,
        "",
        *table(rows),
        *listing(rows, "Missed by the new check", lambda r: r["wrong"] and not r["new"]),
        *listing(rows, "Wrongly blocked by the new check", lambda r: not r["wrong"] and r["new"]),
    ]


def main() -> None:
    """Build the report."""
    settings = get_settings()
    facts = load_facts(settings.resolve(settings.money_facts_path))
    frozen = frozen_rows(facts)

    saved = json.loads(EVAL_V1.read_text())["rows"]
    v1 = reply_rows(
        [
            {
                "id": r["id"],
                "text": r["shown_text"],
                "cited": r["cited"],
                "context": r["context"],
                "message": r["input"],
            }
            for r in saved
            if r["shown_text"]
        ],
        yaml.safe_load((SETS / "fee_replies_eval_v1_labels.yaml").read_text()),
        facts,
    )
    fresh_saved = json.loads((RAW / "fee_replies_phi4-mini.json").read_text())
    fresh = reply_rows(
        [
            {
                "id": r["id"],
                "text": r["reply"],
                "cited": r["cited"],
                "context": r["context"],
                "message": r["question"],
            }
            for r in fresh_saved["rows"]
        ],
        yaml.safe_load((SETS / "fee_replies_phi4_labels.yaml").read_text()),
        facts,
    )

    body = Path(PROJECT_ROOT / "evals" / "fee_check_notes.md").read_text()
    lines = [
        report_header(
            "Fee claim check v1: old number check against the new claim check",
            settings,
            eval_set="evals/sets/fee_claims_v1.yaml, saved eval v1 replies, fresh replies",
            models={"Fresh replies": fresh_saved["model"]},
            judge_used=False,
        ),
        "",
        body.strip(),
        *section(
            "(a) Frozen test set, 42 claims",
            "**Not unseen by the builder:** Claude Code wrote these claims before writing the "
            "check. Read this as a development score. It was run after the check was committed, "
            "and the check was not changed afterwards.",
            frozen,
        ),
        "",
        "### By who checked the label",
        "",
        "10 hard claims with a mark by the project owner (7 settled after seeing Claude Code's "
        "label and reason). Picked by Claude Code, not at random.",
        "",
        *table([r for r in frozen if r["human"]]),
        "",
        "32 claims labelled by Claude Code, not human-reviewed.",
        "",
        *table([r for r in frozen if not r["human"]]),
        *section(
            "(b) Saved eval v1 replies (gpt-oss-20b)",
            f"{len(v1)} shown replies with a money statement. Labelled by Claude Code, not "
            "human-reviewed, before the new check was run on them.",
            v1,
        ),
        *section(
            "(c) Fresh phi4-mini replies",
            f"{len(fresh)} replies with a money statement, from {len(fresh_saved['rows'])} "
            "questions written by Claude Code. Raw model replies, claim check off. Labelled by "
            "Claude Code, not human-reviewed, before the new check was run on them.",
            fresh,
        ),
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
