"""/v3/feedback: a report is stored with its context and pings the webhook; bad input is refused."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.api.main import app
from app.api.routes import feedback
from app.core import feedback_ping
from app.core.ratelimit import limiter
from conftest import API_USER


@pytest.fixture
def fb():
    """(TestClient, insert mock, ping mock) with auth and the rate limit off."""
    app.dependency_overrides[current_user] = lambda: API_USER
    limiter.enabled = False
    with patch.object(feedback.db, "insert_feedback", new=AsyncMock(return_value="f1")) as insert, \
            patch.object(feedback.feedback_ping, "send", new=AsyncMock()) as ping:
        yield TestClient(app), insert, ping
    app.dependency_overrides.clear()
    limiter.enabled = True


def test_bug_with_context_is_stored_and_pinged(fb) -> None:
    c, insert, ping = fb
    ctx = {"chat": [{"role": "user", "text": "hi"}], "run_log": "[wt] ..."}
    r = c.post("/v3/feedback", json={"kind": "bug", "title": "  Card stopped  ", "message": "",
                                     "app_version": "0.4.3", "context": ctx})
    assert r.status_code == 200, r.text
    assert insert.await_args.kwargs == {"user_id": "u1", "kind": "bug", "title": "Card stopped",
                                        "message": None, "app_version": "0.4.3", "context": ctx}
    ping.assert_awaited_once_with("f1", "bug", "Card stopped", "0.4.3")


def test_feedback_without_context(fb) -> None:
    c, insert, _ = fb
    r = c.post("/v3/feedback", json={"kind": "feedback", "title": "Love it"})
    assert r.status_code == 200, r.text
    assert insert.await_args.kwargs["context"] is None


@pytest.mark.parametrize("body", [
    {"kind": "bug", "title": ""},
    {"kind": "bug", "title": "   "},
    {"kind": "praise", "title": "x"},
    {"kind": "bug"},
])
def test_bad_reports_are_refused(fb, body) -> None:
    c, insert, _ = fb
    assert c.post("/v3/feedback", json=body).status_code == 422
    insert.assert_not_awaited()


def test_oversized_context_is_refused(fb) -> None:
    c, insert, _ = fb
    big = {"run_log": "x" * (feedback.MAX_CONTEXT_BYTES + 1)}
    assert c.post("/v3/feedback", json={"kind": "bug", "title": "t", "context": big}).status_code == 413
    insert.assert_not_awaited()


@pytest.mark.parametrize("url, key", [
    ("https://discord.com/api/webhooks/1/abc", "content"),
    ("https://hooks.slack.com/services/T/B/x", "text"),
])
def test_ping_body_per_service(url, key) -> None:
    assert feedback_ping.ping_body(url, "hi") == {key: "hi"}


async def test_ping_failure_is_swallowed() -> None:
    with patch.object(feedback_ping, "FEEDBACK_WEBHOOK_URL", "https://hooks.slack.com/x"), \
            patch.object(feedback_ping.httpx.AsyncClient, "post", new=AsyncMock(side_effect=OSError("down"))):
        await feedback_ping.send("f1", "bug", "t", "0.4.3")
