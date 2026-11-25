"""The simulator is repeatable, resumable and keeps intent labels out of the API."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ab.simulate import choose_messages, simulate, user_id_for
from app.banking77 import Message
from app.chat.factory import build_chat_service
from app.config import Settings
from app.llm.base import LLMError
from app.llm.fake import FakeProvider
from app.main import create_app
from app.storage.db import create_database
from app.storage.repository import Repository

POOL = [
    Message(f"b77-test-{i}", f"question number {i} about my card", f"intent_{i}") for i in range(9)
]


def test_selection_is_stable_and_a_bigger_limit_extends_it() -> None:
    assert choose_messages(POOL, 3, seed=1) == choose_messages(list(reversed(POOL)), 3, seed=1)
    assert choose_messages(POOL, 6, seed=1)[:3] == choose_messages(POOL, 3, seed=1)


def test_user_ids_are_stable_valid_and_distinct() -> None:
    ids = {user_id_for(m.message_id) for m in POOL}
    assert len(ids) == len(POOL)
    assert user_id_for("b77-test-1") == user_id_for("b77-test-1")


def test_replay_fills_database_resumes_and_hides_intents(test_settings: Settings, tmp_path) -> None:
    provider = FakeProvider()
    service = build_chat_service(test_settings, httpx.AsyncClient(), provider)
    truth = tmp_path / "truth.jsonl"
    with TestClient(create_app(test_settings, service)) as client:
        first = simulate(client.post, POOL[:3], truth, "r", progress=lambda _: None)
        second = simulate(client.post, POOL[:5], truth, "r", progress=lambda _: None)
    assert sum(first.values()) == 3 and sum(second.values()) == 2
    repo = Repository(create_database(test_settings.database_path))
    turns = repo.turns("simulation")
    assert len(turns) == 5 and len({t.user_id for t in turns}) == 5
    recorded = [json.loads(line) for line in truth.read_text().splitlines()]
    assert {r["request_id"] for r in recorded} == {t.request_id for t in turns}
    sent = "".join(m.content for r in provider.requests for m in r.messages)
    assert "intent_" not in sent
    assert b"intent_" not in test_settings.database_path.read_bytes()


def test_replay_stops_on_a_system_error(test_settings: Settings, tmp_path) -> None:
    provider = FakeProvider([LLMError("down")])
    service = build_chat_service(test_settings, httpx.AsyncClient(), provider)
    app = create_app(test_settings, service)
    with TestClient(app) as client, pytest.raises(SystemExit, match="llm_error"):
        simulate(client.post, POOL[:3], tmp_path / "t.jsonl", "r")
    assert not (tmp_path / "t.jsonl").exists()
