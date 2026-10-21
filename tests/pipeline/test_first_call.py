"""The turn's first decider call is never forced or re-asked: what Sol says first is the reply."""
from __future__ import annotations

import json

import pytest

from conftest import resp, text_block

CARD_TURN = [
    {"role": "user", "content": "how do i open channel eq"},
    {"role": "assistant", "content": [{"type": "tool_use", "id": "a0", "name": "open_plugin",
                                       "input": {"plugin": "Channel EQ"}}]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a0",
                                  "content": json.dumps({"attached": True, "steps": []})}]},
    {"role": "assistant", "content": [{"type": "text", "text": "This opens Channel EQ."}]},
]


async def test_plain_turn_is_one_call(run) -> None:
    """A plain turn's prose ends it in one call."""
    _, calls = await run([resp(text_block("hi"))])
    assert len(calls) == 1, len(calls)


@pytest.mark.parametrize("text", ["yes please, do it for me", "thanks!", "what does it do?"])
async def test_after_a_card_is_one_call(run, text) -> None:
    """A go-ahead, a closer or a question after a card is answered in one call."""
    _, calls = await run([resp(text_block("ok"))], messages=CARD_TURN + [{"role": "user", "content": text}])
    assert len(calls) == 1, (text, len(calls))


async def test_status_update_after_card_keeps_first_reply(run) -> None:
    """A "now what" after a card is answered once, and Sol's steps reach the reply."""
    steps = "1. Play the vocal.\n2. Lower Threshold until you see 3-6 dB of reduction."
    result, calls = await run([resp(text_block(steps))], messages=CARD_TURN + [{"role": "user", "content": "now what"}])
    assert len(calls) == 1, len(calls)
    assert "Lower Threshold" in result.text, result.text
