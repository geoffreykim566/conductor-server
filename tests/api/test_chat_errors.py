"""/v3/chat failures: a turn that errors gets its free message back and sends only a kind
and fixed text; a finished turn is never refunded."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.api.main import app
from app.api.routes import chat
from app.core.ratelimit import limiter
from app.pipeline.openai_io import SolError

USER = {"id": "u1", "free_limit": 50, "free_used": 3}


@pytest.fixture
def client():
    app.dependency_overrides[current_user] = lambda: USER
    limiter.enabled = False
    with patch.object(chat.budget, "over_daily_budget", new=AsyncMock(return_value=False)), \
            patch.object(chat.db, "claim_free_message", new=AsyncMock(return_value=USER)), \
            patch.object(chat.db, "refund_free_message", new=AsyncMock()) as refund, \
            patch.object(chat.db, "insert_event", new=AsyncMock(return_value="e1")):
        yield TestClient(app), refund
    app.dependency_overrides.clear()
    limiter.enabled = True


def events(resp) -> list[dict]:
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]


@pytest.mark.parametrize("exc, kind, code", [
    (SolError("down", "quota", "HTTP 429: insufficient_quota", 429), "down", 429),
    (SolError("down", "timeout", "ReadTimeout"), "down", None),
    (KeyError("a bug"), "retry", 500),
])
def test_error_refunds_and_hides_the_cause(client, exc, kind, code) -> None:
    c, refund = client
    with patch.object(chat, "respond", new=AsyncMock(side_effect=exc)):
        evs = events(c.post("/v3/chat", json={"message": "hi"}))
    assert evs[-1] == {"type": "error", "kind": kind, "code": code, "message": chat.ERROR_TEXT[kind]}, evs
    refund.assert_awaited_once_with("u1")


def test_resume_error_refunds_too(client) -> None:
    """A resume isn't charged, but the parked request's charge is given back."""
    c, refund = client
    with patch.object(chat, "pending_research_query", return_value="q"), \
            patch.object(chat, "respond", new=AsyncMock(side_effect=SolError("down", "outage", "HTTP 503"))):
        evs = events(c.post("/v3/chat", json={"message": "", "resume": "allow_research", "history": []}))
    assert evs[-1]["kind"] == "down", evs
    refund.assert_awaited_once_with("u1")


def test_finished_turn_is_not_refunded(client) -> None:
    c, refund = client
    result = SimpleNamespace(usage=[{"input_tokens": 1, "output_tokens": 1}], confidence_tier="generic",
                             text="Done.", pending_research_query=None, sources=[], walkthrough_steps=[],
                             auto_run=False, messages=[])
    with patch.object(chat, "respond", new=AsyncMock(return_value=result)):
        evs = events(c.post("/v3/chat", json={"message": "hi"}))
    assert evs[-1]["type"] == "done", evs
    refund.assert_not_awaited()
