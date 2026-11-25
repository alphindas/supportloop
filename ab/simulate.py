"""Replay real Banking77 messages through the RUNNING API, one per simulated user.

Intent labels are written to a separate ground-truth file (data/sim/<run>.jsonl) and are
never sent to the API or stored in its database. Data-loop mining must not read that
file; it is only used afterwards to score what mining found.

Usage: start the API (`make run`), then
    uv run python -m ab.simulate --limit 200 --run sim1
Running the same command again continues where it stopped.

No feedback (thumbs up or down) is simulated: invented ratings would look like real
customer signals.
"""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from random import Random

import httpx
import yaml

from app.banking77 import Message
from app.config import PROJECT_ROOT

TRUTH_DIR = PROJECT_ROOT / "data" / "sim"


def user_id_for(message_id: str) -> str:
    """A stable user ID: the same message always comes from the same simulated user.

    Each user sends exactly one message, so messages are independent in later tests.
    """
    return "sim-" + hashlib.sha256(message_id.encode()).hexdigest()[:16]


def choose_messages(pool: list[Message], limit: int, seed: int) -> list[Message]:
    """A fixed random order, so a larger limit extends a smaller run."""
    ordered = sorted(pool, key=lambda m: m.message_id)
    Random(seed).shuffle(ordered)
    return ordered[:limit]


def already_sent(truth_file: Path) -> set[str]:
    """Message IDs recorded by an earlier run."""
    if not truth_file.exists():
        return set()
    return {json.loads(line)["message_id"] for line in truth_file.read_text().splitlines()}


def simulate(
    post: Callable[..., httpx.Response],
    messages: list[Message],
    truth_file: Path,
    run: str,
    progress: Callable[[str], None] = print,
) -> Counter:
    """Send each unsent message. Returns how many replies had each behaviour.

    Stops at the first reply that reports a system error: carrying on would fill the
    database with failures caused by the setup rather than by the bot.
    """
    truth_file.parent.mkdir(parents=True, exist_ok=True)
    done = already_sent(truth_file)
    todo = [m for m in messages if m.message_id not in done]
    counts: Counter = Counter()
    for number, message in enumerate(todo, start=1):
        user_id = user_id_for(message.message_id)
        response = post(
            "/chat",
            json={
                "user_id": user_id,
                "conversation_id": f"{run}-{user_id[4:]}",
                "message": message.text,
            },
            headers={"X-SupportLoop-Source": "simulation"},
        )
        response.raise_for_status()
        reply = response.json()
        errors = {"llm_error", "retrieval_error"} & set(reply["guardrail_events"])
        if errors:
            raise SystemExit(
                f"Stopped after {number - 1} messages: the API reported {sorted(errors)}. "
                "Check the server log, then run the same command to continue."
            )
        record = {
            "request_id": reply["request_id"],
            "user_id": user_id,
            "message_id": message.message_id,
            "intent": message.intent,
        }
        with truth_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        counts[reply["behavior"]] += 1
        if number % 20 == 0 or number == len(todo):
            progress(f"{number}/{len(todo)} sent ({len(done)} from earlier runs)")
    return counts


def main() -> None:
    """Command line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pool", choices=["mining", "loop_holdout", "ab"], default="mining")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--run", default="sim1", help="name of this run")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    data = yaml.safe_load((PROJECT_ROOT / "config" / "data.yaml").read_text())
    pool_file = PROJECT_ROOT / data["banking77"]["dir"] / "pools" / f"{args.pool}.jsonl"
    pool = [Message(**json.loads(line)) for line in pool_file.read_text().splitlines()]
    messages = choose_messages(pool, args.limit, data["splits"]["seed"])
    with httpx.Client(base_url=args.api, timeout=300) as client:
        health = client.get("/health").raise_for_status().json()
        print(f"API model: {health['llm']}; sending up to {len(messages)} messages")
        counts = simulate(client.post, messages, TRUTH_DIR / f"{args.run}.jsonl", args.run)
    print(f"New replies by behaviour: {dict(counts)}")


if __name__ == "__main__":
    main()
