"""/v3/chat plug-in reads: a parked read streams plugin_read_prompt, and its resume is checked
against the parked call and never charged."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.routes import chat
from conftest import events

PARKED = [{"role": "user", "content": "what are my settings"},
          {"role": "assistant", "content": [
              {"type": "tool_use", "id": "c1", "name": "read_plugin_values", "input": {"plugin": "Compressor"}}]}]


def _result(**kw) -> SimpleNamespace:
    base = dict(usage=[{"input_tokens": 1, "output_tokens": 1}], confidence_tier="generic", text="",
                pending_research_query=None, pending_plugin_read=None, sources=[], walkthrough_steps=[],
                auto_run=False, messages=PARKED)
    return SimpleNamespace(**{**base, **kw})


def test_parked_read_streams_its_prompt(client) -> None:
    c, _ = client
    parked = _result(pending_plugin_read={"plugin": "Compressor", "track": "Vocal"})
    with patch.object(chat, "respond", new=AsyncMock(return_value=parked)) as respond:
        evs = events(c.post("/v3/chat", json={"message": "what are my settings", "plugin_reads": True}))
    assert evs[-1] == {"type": "plugin_read_prompt", "plugin": "Compressor", "track": "Vocal",
                       "history": PARKED}, evs
    assert respond.await_args.kwargs["plugin_reads"] is True


def test_read_resume_is_not_charged(client) -> None:
    c, _ = client
    values = {"plugin": "Compressor", "values": {"Threshold": "-19.5 dB"}}
    with patch.object(chat, "respond", new=AsyncMock(return_value=_result(text="Done."))) as respond, \
            patch.object(chat.db, "claim_free_message", new=AsyncMock()) as claim:
        evs = events(c.post("/v3/chat", json={"message": "", "resume": "allow_plugin_read", "history": PARKED,
                                              "plugin_reads": True, "plugin_values": values}))
    assert evs[-1]["type"] == "done", evs
    claim.assert_not_awaited()
    assert respond.await_args.kwargs["plugin_values"] == values


def test_read_resume_needs_a_parked_read(client) -> None:
    """A research-shaped (or empty) history can't be resumed as a read."""
    c, _ = client
    research = PARKED[:1] + [{"role": "assistant", "content": [
        {"type": "tool_use", "id": "c1", "name": "web_research", "input": {"query": "q"}}]}]
    resp = c.post("/v3/chat", json={"message": "", "resume": "deny_plugin_read", "history": research})
    assert resp.status_code == 422, resp.status_code
