"""/admin/waitlist/action: approve-and-email approves then queues only new sends; emailing needs a key."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.admin import routes
from app.api.main import app

AUTH = ("admin", "pw")
IDS = [str(uuid.uuid4()), str(uuid.uuid4())]


@pytest.fixture
def adm():
    with patch.object(routes, "ADMIN_PASSWORD", "pw"), \
            patch.object(routes.invite_mail, "configured", return_value=True), \
            patch.object(routes.waitlist_queries, "apply", new=AsyncMock(return_value=2)) as apply, \
            patch.object(routes.waitlist_queries, "to_email",
                         new=AsyncMock(return_value=[(IDS[0], "a@b.co")])) as to_email, \
            patch.object(routes.waitlist_queries, "send_invites", new=AsyncMock()) as send:
        yield TestClient(app), apply, to_email, send


def _act(c, action, ids=IDS):
    return c.post("/admin/waitlist/action", auth=AUTH, json={"action": action, "ids": ids})


def test_approve_email_approves_then_sends_new_only(adm) -> None:
    c, apply, to_email, send = adm
    r = _act(c, "approve_email")
    assert r.status_code == 200 and r.json() == {"changed": 2, "emailing": 1}, r.text
    assert apply.await_args.args[0] == "approve"
    assert to_email.await_args.kwargs == {"only_new": True}
    send.assert_awaited_once_with([(IDS[0], "a@b.co")])


def test_email_again_resends_without_changing_rows(adm) -> None:
    c, apply, to_email, _ = adm
    assert _act(c, "email").json() == {"changed": 0, "emailing": 1}
    apply.assert_not_awaited()
    assert to_email.await_args.kwargs == {"only_new": False}


@pytest.mark.parametrize("action", ["approve", "unapprove", "reset_installs", "delete"])
def test_plain_actions_send_nothing(adm, action) -> None:
    c, apply, _, send = adm
    assert _act(c, action).json() == {"changed": 2, "emailing": 0}
    assert apply.await_args.args[0] == action
    send.assert_not_awaited()


def test_emailing_without_a_key_changes_nothing(adm) -> None:
    c, apply, _, _ = adm
    with patch.object(routes.invite_mail, "configured", return_value=False):
        r = _act(c, "approve_email")
    assert r.status_code == 409 and r.json()["detail"] == "email_not_configured", r.text
    apply.assert_not_awaited()


def test_needs_auth_and_ids(adm) -> None:
    c, *_ = adm
    assert c.post("/admin/waitlist/action", json={"action": "approve", "ids": IDS}).status_code == 401
    assert _act(c, "approve", ids=[]).status_code == 422
    assert _act(c, "launch", ids=IDS).status_code == 422
