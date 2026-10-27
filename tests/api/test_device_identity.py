"""One user per Mac: register returns a known Mac's id, /v3/me links a pre-hash user, bad hashes are ignored."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.api.main import app
from app.api.routes import me, register
from app.core import signing
from app.core.ratelimit import limiter

HASH = "a" * 64


@pytest.fixture
def client():
    limiter.enabled = False
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.enabled = True


@pytest.fixture(autouse=True)
def secret():
    with patch.object(signing, "CONDUCTOR_ID_SECRET", "test-secret"):
        yield


def test_register_new_mac_gets_the_new_id(client) -> None:
    with patch.object(register.db, "register_user",
                      new=AsyncMock(side_effect=lambda new_id, dev: new_id)) as reg:
        r = client.post("/v3/register", headers={"X-Conductor-Device": HASH.upper()})
    assert r.status_code == 200, r.text
    new_id, dev = reg.await_args.args
    assert dev == HASH
    assert signing.verify(r.json()["conductor_id"]) == new_id


def test_register_known_mac_gets_its_existing_id(client) -> None:
    existing = uuid.uuid4()
    with patch.object(register.db, "register_user", new=AsyncMock(return_value=existing)):
        r = client.post("/v3/register", headers={"X-Conductor-Device": HASH})
    assert signing.verify(r.json()["conductor_id"]) == existing


@pytest.mark.parametrize("header", [None, "", "abc", "g" * 64, HASH + "0"])
def test_register_without_a_valid_hash_sends_none(client, header) -> None:
    headers = {"X-Conductor-Device": header} if header is not None else {}
    with patch.object(register.db, "register_user",
                      new=AsyncMock(side_effect=lambda new_id, dev: new_id)) as reg:
        assert client.post("/v3/register", headers=headers).status_code == 200
    assert reg.await_args.args[1] is None


def _me(client, user: dict, headers: dict) -> AsyncMock:
    app.dependency_overrides[current_user] = lambda: user
    with patch.object(me.db, "link_device", new=AsyncMock()) as link:
        r = client.get("/v3/me", headers={"X-Conductor-Id": "x", **headers})
    assert r.status_code == 200, r.text
    return link


def test_me_links_a_user_without_a_hash(client) -> None:
    user = {"id": "u1", "device_hash": None, "free_used": 0, "free_limit": 50}
    _me(client, user, {"X-Conductor-Device": HASH}).assert_awaited_once_with("u1", HASH)


def test_me_leaves_a_linked_user_alone(client) -> None:
    user = {"id": "u1", "device_hash": "b" * 64, "free_used": 0, "free_limit": 50}
    _me(client, user, {"X-Conductor-Device": HASH}).assert_not_awaited()


def test_me_without_a_hash_links_nothing(client) -> None:
    user = {"id": "u1", "device_hash": None, "free_used": 0, "free_limit": 50}
    _me(client, user, {}).assert_not_awaited()
