"""The turn's first decider call: unforced, except a go-ahead after a card, which is re-asked once without a tool call."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.pipeline import notes, settings
from conftest import open_plugin, resp, text_block

CARD_TURN = [
    {"role": "user", "content": "how do i open channel eq"},
    {"role": "assistant", "content": [{"type": "tool_use", "id": "a0", "name": "open_plugin",
                                       "input": {"plugin": "Channel EQ"}}]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a0",
                                  "content": json.dumps({"attached": True, "steps": []})}]},
    {"role": "assistant", "content": [{"type": "text", "text": "This opens Channel EQ."}]},
]
GO_AHEAD = CARD_TURN + [{"role": "user", "content": "yes please, do it for me"}]


async def test_first_call_not_forced(run) -> None:
    """A plain turn's first call has no tool_choice, and prose ends it in one call."""
    _, calls = await run([resp(text_block("hi"))])
    assert calls[0].get("tool_choice") is None and len(calls) == 1, (calls[0].get("tool_choice"), len(calls))


async def test_go_ahead_without_tool_call_is_reasked(run) -> None:
    """RETRY_NO_TOOL_FIRST_CALL on: a go-ahead's first call is auto; one that makes no tool call is re-asked once with TOOL_NUDGE."""
    with patch.object(settings, "RETRY_NO_TOOL_FIRST_CALL", True):
        result, calls = await run([resp(text_block("Press Run.")), resp(open_plugin("Channel EQ", "a1")), resp(text_block("ok"))],
                                  messages=GO_AHEAD)
    assert calls[0].get("tool_choice") is None, calls[0].get("tool_choice")
    assert notes.TOOL_NUDGE in str(calls[1].get("system")), calls[1].get("system")
    assert result.walkthrough_steps, result.walkthrough_steps


@pytest.mark.parametrize("text", ["thanks!", "what does it do?"])
async def test_not_a_go_ahead_is_not_reasked(run, text) -> None:
    """A closer or a question after a card is answered in one call."""
    _, calls = await run([resp(text_block("ok"))], messages=CARD_TURN + [{"role": "user", "content": text}])
    assert len(calls) == 1, (text, len(calls))


async def test_retry_flag_off(run) -> None:
    """RETRY_NO_TOOL_FIRST_CALL off: a go-ahead answered in prose is not re-asked."""
    with patch.object(settings, "RETRY_NO_TOOL_FIRST_CALL", False):
        result, calls = await run([resp(text_block("Press Run."))], messages=GO_AHEAD)
    assert len(calls) == 1 and not result.walkthrough_steps, (len(calls), result.walkthrough_steps)


async def test_status_update_after_card_keeps_first_reply(run) -> None:
    """Default (re-ask off): "now what" after a card is answered once, and Sol's steps reach the reply."""
    steps = "1. Play the vocal.\n2. Lower Threshold until you see 3-6 dB of reduction."
    result, calls = await run([resp(text_block(steps))], messages=CARD_TURN + [{"role": "user", "content": "now what"}])
    assert len(calls) == 1, len(calls)
    assert "Lower Threshold" in result.text, result.text


@pytest.mark.parametrize("text, forced", [("yes please, do it for me", True), ("thanks!", False)])
async def test_forced_tool_choice_knob(run, text, forced) -> None:
    """FORCED_TOOL_CHOICE set (models that accept it): only a go-ahead's first call is forced."""
    with patch.object(settings, "FORCED_TOOL_CHOICE", {"type": "any"}):
        _, calls = await run([resp(open_plugin("Channel EQ", "a1")), resp(text_block("ok"))],
                             messages=CARD_TURN + [{"role": "user", "content": text}])
    assert (calls[0].get("tool_choice") == {"type": "any"}) == forced, (text, calls[0].get("tool_choice"))
