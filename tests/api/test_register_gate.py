"""Register's waitlist gate: a known Mac skips it; a new Mac needs an approved email under the cap."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import register
from app.core import signing
from app.core.ratelimit import limiter

HASH = "a" * 64
DEV = {"X-Conductor-Device": HASH}


@pytest.fixture
def gate():
    """(client, known_device, claim_install, release_install, register_user) with the gate on."""
    limiter.enabled = False
    with patch.object(signing, "CONDUCTOR_ID_SECRET", "test-secret"), \
            patch.object(register.config, "WAITLIST_REQUIRED", True), \
            patch.object(register.config, "WAITLIST_INSTALL_CAP", 2), \
            patch.object(register.db, "known_device", new=AsyncMock(return_value=False)) as known, \
            patch.object(register.waitlist, "claim_install", new=AsyncMock(return_value="ok")) as claim, \
            patch.object(register.waitlist, "release_install", new=AsyncMock()) as release, \
            patch.object(register.db, "set_user_origin", new=AsyncMock()), \
            patch.object(register.db, "register_user",
                         new=AsyncMock(side_effect=lambda new_id, dev: new_id)) as reg:
        yield TestClient(app), known, claim, release, reg
    limiter.enabled = True


def test_known_mac_needs_no_email(gate) -> None:
    c, known, claim, _, reg = gate
    known.return_value = True
    existing = uuid.uuid4()
    reg.side_effect = None
    reg.return_value = existing
    r = c.post("/v3/register", headers=DEV)
    assert r.status_code == 200, r.text
    assert signing.verify(r.json()["conductor_id"]) == existing
    claim.assert_not_awaited()


@pytest.mark.parametrize("body", [None, {}, {"email": ""}, {"email": "not an email"}])
def test_new_mac_without_an_email_is_refused(gate, body) -> None:
    c, _, claim, _, reg = gate
    r = c.post("/v3/register", headers=DEV, json=body) if body is not None else \
        c.post("/v3/register", headers=DEV)
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "email_required"
    claim.assert_not_awaited()
    reg.assert_not_awaited()


@pytest.mark.parametrize("reason", ["not_on_waitlist", "not_approved", "install_limit"])
def test_refusal_reason_is_passed_on(gate, reason) -> None:
    c, _, claim, _, reg = gate
    claim.return_value = reason
    r = c.post("/v3/register", headers=DEV, json={"email": "a@b.co"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == reason
    reg.assert_not_awaited()


def test_approved_email_registers_and_is_normalized(gate) -> None:
    c, _, claim, release, reg = gate
    r = c.post("/v3/register", headers=DEV, json={"email": "  Sam@Example.COM "})
    assert r.status_code == 200, r.text
    claim.assert_awaited_once_with("sam@example.com", 2)
    new_id = reg.await_args.args[0]
    assert signing.verify(r.json()["conductor_id"]) == new_id
    release.assert_not_awaited()


def test_mac_without_a_hash_still_needs_an_email(gate) -> None:
    c, known, claim, _, _ = gate
    assert c.post("/v3/register").status_code == 403
    known.assert_not_awaited()
    assert c.post("/v3/register", json={"email": "a@b.co"}).status_code == 200
    claim.assert_awaited_once()


def test_slot_is_given_back_when_the_mac_was_known_after_all(gate) -> None:
    c, _, _, release, reg = gate
    reg.side_effect = None
    reg.return_value = uuid.uuid4()
    r = c.post("/v3/register", headers=DEV, json={"email": "a@b.co"})
    assert r.status_code == 200, r.text
    release.assert_awaited_once_with("a@b.co")


def test_gate_off_registers_without_an_email(gate) -> None:
    c, _, claim, _, _ = gate
    with patch.object(register.config, "WAITLIST_REQUIRED", False):
        assert c.post("/v3/register", headers=DEV).status_code == 200
    claim.assert_not_awaited()


def test_new_mac_records_its_origin(gate) -> None:
    c, *_ = gate
    with patch.object(register.db, "set_user_origin", new=AsyncMock()) as origin, \
            patch.object(register.geo, "country", return_value="DE"):
        r = c.post("/v3/register", json={"email": "Sam@Example.com"}, headers=DEV)
    assert r.status_code == 200, r.text
    uid, email, country = origin.await_args.args
    assert (email, country) == ("sam@example.com", "DE"), origin.await_args
    assert signing.verify(r.json()["conductor_id"]) == uid


def test_known_mac_keeps_its_origin(gate) -> None:
    c, known, _, _, reg = gate
    known.return_value = True
    reg.side_effect = None
    reg.return_value = uuid.uuid4()
    with patch.object(register.db, "set_user_origin", new=AsyncMock()) as origin:
        assert c.post("/v3/register", headers=DEV).status_code == 200
    origin.assert_not_awaited()
