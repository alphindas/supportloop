"""Files that can hold secrets or customer text must never be committable."""

import shutil
import subprocess

import pytest

from app.config import PROJECT_ROOT

MUST_BE_IGNORED = [
    ".env",
    "data/supportloop.db",
    "data/supportloop.db-wal",
    "data/supportloop.db-shm",
    "data/supportloop.db-journal",
    "data/cache/llm_cache.sqlite3",
    "data/cache/llm_cache.sqlite3-wal",
    "data/sim/sim1.jsonl",
    "data/banking77/test.csv",
    "logs/traces.jsonl",
    "logs/api.log",
]


@pytest.mark.skipif(
    shutil.which("git") is None or not (PROJECT_ROOT / ".git").exists(),
    reason="needs a git checkout",
)
@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_sensitive_paths_are_ignored(path: str) -> None:
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=PROJECT_ROOT, check=False)
    assert result.returncode == 0, f"{path} is not ignored"
