"""Download Banking77 and split its test messages into pools that never overlap."""

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from random import Random


@dataclass(frozen=True)
class Message:
    """One real customer message from Banking77."""

    message_id: str  # 'b77-test-<row number>'
    text: str
    intent: str


def read_messages(csv_path: Path) -> list[Message]:
    """Read test.csv."""
    with csv_path.open(encoding="utf-8", newline="") as handle:
        return [
            Message(f"b77-test-{row}", record["text"].strip(), record["category"])
            for row, record in enumerate(csv.DictReader(handle))
        ]


def split_into_pools(
    messages: list[Message], per_intent: dict[str, int], seed: int
) -> dict[str, list[Message]]:
    """Give every pool a fixed number of messages from every intent.

    Each intent gets its own random generator seeded from (seed, intent), so the
    result is the same on every run and does not depend on the order of intents.
    """
    by_intent: dict[str, list[Message]] = {}
    for message in messages:
        by_intent.setdefault(message.intent, []).append(message)

    pools: dict[str, list[Message]] = {name: [] for name in per_intent}
    for intent in sorted(by_intent):
        group = list(by_intent[intent])
        if len(group) < sum(per_intent.values()):
            raise ValueError(f"Intent '{intent}' has only {len(group)} messages")
        digest = hashlib.sha256(f"{seed}:{intent}".encode()).hexdigest()
        Random(int(digest, 16)).shuffle(group)
        start = 0
        for name, size in per_intent.items():
            pools[name].extend(group[start : start + size])
            start += size
    return pools


def write_pools(pools: dict[str, list[Message]], directory: Path) -> None:
    """Save one JSON-lines file per pool."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, messages in pools.items():
        lines = [json.dumps(asdict(message), ensure_ascii=False) for message in messages]
        (directory / f"{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
