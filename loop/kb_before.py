"""Rebuild the knowledge base as it was before a data loop cycle, for the 'before' run.

Copies every article except those the cycle added into data/cache/kb_before/. Run the
'before' commands with SUPPORTLOOP_KB_DIR and SUPPORTLOOP_INDEX_DIR pointing at the copy
(see `make loop-before`).
"""

import shutil

from app.config import PROJECT_ROOT
from loop.mine import load_loop_config

TARGET = PROJECT_ROOT / "data" / "cache" / "kb_before"


def main() -> None:
    """Write the copy."""
    marker = f"added_by: data_loop_cycle_{load_loop_config()['cycle']}"
    TARGET.mkdir(parents=True, exist_ok=True)
    for old in TARGET.glob("*.md"):
        old.unlink()
    kept = 0
    for path in sorted((PROJECT_ROOT / "data" / "kb").glob("*.md")):
        if marker not in path.read_text(encoding="utf-8"):
            shutil.copy(path, TARGET / path.name)
            kept += 1
    print(f"Copied {kept} files to {TARGET.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
