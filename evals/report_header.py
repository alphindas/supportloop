"""The header every report starts with, so any number can be traced to its setup."""

import subprocess
from datetime import date

from app.config import PROJECT_ROOT, Settings


def git_commit() -> str:
    """Current commit, marked '+uncommitted' if tracked or new code files differ from it."""

    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        commit = run("rev-parse", "--short", "HEAD")
        dirty = run("status", "--porcelain", "--", "app", "evals", "config", "scripts", "data/kb")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit}+uncommitted" if dirty else commit


def report_header(
    title: str,
    settings: Settings,
    *,
    eval_set: str,
    models: dict[str, str],
    judge_used: bool,
) -> str:
    """Markdown header. The judge model is always recorded, even when no judge ran."""
    judge_note = "used in this report" if judge_used else "configured; not used in this report"
    rows = {
        "Generated": date.today().isoformat(),
        "Git commit": git_commit(),
        "Config": "config/settings.yaml",
        "Prompt version": settings.prompt_version,
        "Eval set": eval_set,
        **models,
        "Judge model": f"{settings.groq_judge_model} ({judge_note})",
    }
    table = "\n".join(f"| {key} | {value} |" for key, value in rows.items())
    return f"# {title}\n\n| Field | Value |\n|---|---|\n{table}\n"
