"""Shared fakes: scripted decider responses, route helpers, and the `run` fixture
that drives one pipeline turn with the decider and research mocked.

Test modules import the builders with `from conftest import ...` (tests/ is on
sys.path under pytest's default import mode; keep this the only conftest.py)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import pipeline, tools
from app.api.deps import current_user
from app.api.main import app
from app.api.routes import chat
from app.core.ratelimit import limiter
from app.pipeline import executors, model_io, settings

# --- model response builders -------------------------------------------------


def usage() -> SimpleNamespace:
    return SimpleNamespace(input_tokens=10, output_tokens=10,
                           cache_creation_input_tokens=0, cache_read_input_tokens=0)


def tool_use(name: str, input_: dict, id_: str) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=id_)


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def resp(*blocks) -> SimpleNamespace:
    """One decider response holding `blocks` (the shape openai_io returns)."""
    return SimpleNamespace(content=list(blocks), usage=usage())


def open_plugin(plugin: str, id_: str, **extra) -> SimpleNamespace:
    return tool_use("open_plugin", {"plugin": plugin, **extra}, id_)


def set_param(plugin: str, param: str, value: str, id_: str) -> SimpleNamespace:
    return tool_use("set_param", {"plugin": plugin, "param": param, "value": value}, id_)


# --- routes (real seed/routes.json, no DB) -----------------------------------


def route(name: str) -> list:
    """The pane-only steps open_setting queues for an approved route."""
    return tools.queue_open_setting({"name": name})["steps"]


def queue_setting(name: str, value: str | None = None, said: str = "", offered: str = "") -> dict:
    """open_setting's executor as if the user's message were `said` and the
    previous reply `offered` (the turn-text context vars the pipeline sets)."""
    token, token2 = tools.TURN_USER_TEXT.set(said), tools.TURN_OFFERED_TEXT.set(offered)
    try:
        return tools.queue_open_setting({"name": name, **({"value": value} if value else {})})
    finally:
        tools.TURN_USER_TEXT.reset(token)
        tools.TURN_OFFERED_TEXT.reset(token2)


# --- fixtures ----------------------------------------------------------------


class FakeModel:
    """Stands in for model_io.call_model. Each call takes the next scripted response,
    the last one repeating, and records its arguments as a dict (system, tools,
    messages, tool_choice)."""

    def __init__(self) -> None:
        self.responses: list = []
        self.decider_calls: list[dict] = []

    def script(self, responses: list) -> list[dict]:
        """Start a new turn's script; returns the list decider kwargs land in."""
        self.responses, self.decider_calls = list(responses), []
        return self.decider_calls

    async def call(self, system, tools_param, msgs, tool_choice=None):
        self.decider_calls.append({"system": system, "tools": tools_param, "messages": msgs,
                                   "tool_choice": tool_choice})
        return self.responses[min(len(self.decider_calls) - 1, len(self.responses) - 1)]


@pytest.fixture
def model():
    """Patches the decider call for the test; script it via model.script()."""
    fake = FakeModel()
    with patch.object(model_io, "call_model", new=AsyncMock(side_effect=fake.call)):
        yield fake


@pytest.fixture
def research():
    """web_research mocked for the test; set .return_value to change findings."""
    mock = AsyncMock(return_value={"findings": "x", "sources": []})
    with patch.object(executors.research, "web_research", new=mock):
        yield mock


@pytest.fixture
def run(model, research):
    """async run(responses, messages=None, early_exit=False, **respond_kwargs) ->
    (Result, decider_calls). Drives pipeline.respond() through scripted decider
    responses. settings.EARLY_EXIT_ON_ACTION is off unless asked for: most scripts
    keep the decider going after an action, which is what they exercise."""
    async def _run(responses: list, messages: list[dict] | None = None,
                   early_exit: bool = False, **kwargs):
        calls = model.script(responses)
        with patch.object(settings, "EARLY_EXIT_ON_ACTION", early_exit):
            result = await pipeline.respond(messages or [{"role": "user", "content": "test"}], **kwargs)
        return result, calls
    return _run


# --- /v3/chat ----------------------------------------------------------------

API_USER = {"id": "u1", "free_limit": 50, "free_used": 3}


@pytest.fixture
def client():
    """(TestClient, refund mock) for /v3/chat with auth, budget, the free-message claim and
    the event insert stubbed; patch chat.respond for the turn itself."""
    app.dependency_overrides[current_user] = lambda: API_USER
    limiter.enabled = False
    with patch.object(chat.budget, "over_daily_budget", new=AsyncMock(return_value=False)), \
            patch.object(chat.db, "claim_free_message", new=AsyncMock(return_value=API_USER)), \
            patch.object(chat.db, "refund_free_message", new=AsyncMock()) as refund, \
            patch.object(chat.db, "insert_event", new=AsyncMock(return_value="e1")):
        yield TestClient(app), refund
    app.dependency_overrides.clear()
    limiter.enabled = True


def events(resp) -> list[dict]:
    """The SSE events of a /v3/chat response."""
    return [json.loads(line[6:]) for line in resp.text.splitlines() if line.startswith("data: ")]
