"""Plug-in reads: offered only to a client that can read, parking at read_plugin_values, resuming
with the client's values or a decline, and the api's checks on both."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.api.history import pending_plugin_read, pending_research_query
from app.api.schemas import ChatRequest
from app.pipeline import notes
from conftest import resp, text_block, tool_use

USER = [{"role": "user", "content": "what are my compressor settings"}]
READ_CALL = resp(tool_use("read_plugin_values", {"plugin": "Compressor", "track": "Vocal"}, "call_p"))
FINAL = resp(text_block("Threshold is -19.5 dB."))
VALUES = {"plugin": "Compressor", "track": "Vocal", "values": {"Threshold": "-19.5 dB", "Ratio": "8.7:1"}}


def _offered(call: dict) -> list[str]:
    return [t["name"] for t in call["tools"]]


async def test_not_offered_unless_the_client_can_read(run) -> None:
    """An older client (no plugin_reads) is never offered the tool; a v0.4.2 one is."""
    _, calls = await run([FINAL], messages=USER)
    assert "read_plugin_values" not in _offered(calls[0]), _offered(calls[0])
    _, calls = await run([FINAL], messages=USER, plugin_reads=True)
    assert "read_plugin_values" in _offered(calls[0]), _offered(calls[0])


async def test_parks_at_the_read(run) -> None:
    """A read call parks the turn with its input; nothing is answered yet."""
    result, _ = await run([READ_CALL, FINAL], messages=USER, plugin_reads=True)
    assert result.pending_plugin_read == {"plugin": "Compressor", "track": "Vocal"}, result.pending_plugin_read
    assert result.text == "" and result.pending_research_query is None
    assert pending_plugin_read(result.messages) == {"plugin": "Compressor", "track": "Vocal"}
    assert pending_research_query(result.messages) is None


async def test_resume_allow_gives_sol_the_values(run) -> None:
    """allow_plugin_read hands the client's values to the parked call and finishes the turn."""
    parked, _ = await run([READ_CALL], messages=USER, plugin_reads=True)
    result, calls = await run([FINAL], messages=parked.messages, plugin_reads=True,
                              resume="allow_plugin_read", plugin_values=VALUES)
    assert result.pending_plugin_read is None and result.text == "Threshold is -19.5 dB.", result.text
    assert result.trace[-1]["tool"] == "read_plugin_values" and result.trace[-1]["output"] == VALUES
    tr = result.messages[len(parked.messages)]
    assert tr["content"][0]["tool_use_id"] == "call_p" and json.loads(tr["content"][0]["content"]) == VALUES


async def test_a_second_read_parks_again(run) -> None:
    """After one read is answered, a read of another plug-in asks again."""
    parked, _ = await run([READ_CALL], messages=USER, plugin_reads=True)
    eq_read = resp(tool_use("read_plugin_values", {"plugin": "Channel EQ"}, "call_q"))
    result, _ = await run([eq_read], messages=parked.messages, plugin_reads=True,
                          resume="allow_plugin_read", plugin_values=VALUES)
    assert result.pending_plugin_read == {"plugin": "Channel EQ"}, result.pending_plugin_read


async def test_resume_deny_declines_every_read(run) -> None:
    """deny_plugin_read declines the parked read and any later one, and the turn still answers."""
    parked, _ = await run([READ_CALL], messages=USER, plugin_reads=True)
    again = resp(tool_use("read_plugin_values", {"plugin": "Compressor"}, "call_r"))
    result, _ = await run([again, FINAL], messages=parked.messages, plugin_reads=True, resume="deny_plugin_read")
    reads = [c for c in result.trace if c["tool"] == "read_plugin_values"]
    assert [c["output"] for c in reads] == [notes.PLUGIN_READ_DECLINED] * 2, reads
    assert result.pending_plugin_read is None and result.text, result.text


def test_plugin_values_shape_is_checked() -> None:
    """The client's read is replayed to the model, so only its exact shape is accepted."""
    ChatRequest(message="", resume="allow_plugin_read", plugin_values=VALUES)
    ChatRequest(message="", resume="allow_plugin_read", plugin_values={"error": "not on the track"})
    for bad in ({"values": {"Threshold": 3}}, {"values": "x"}, {"plugin": "C", "extra": "x"},
                {"values": {f"k{i}": "v" for i in range(101)}}, {"error": "x" * 9000}):
        with pytest.raises(ValidationError):
            ChatRequest(message="", resume="allow_plugin_read", plugin_values=bad)


async def test_two_reads_in_one_call_get_their_own_asks(run) -> None:
    """Only the first read of a parked batch gets the values; the other is sent back to ask again."""
    both = resp(tool_use("read_plugin_values", {"plugin": "Compressor"}, "call_c"),
                tool_use("read_plugin_values", {"plugin": "Channel EQ"}, "call_e"))
    parked, _ = await run([both], messages=USER, plugin_reads=True)
    assert parked.pending_plugin_read == {"plugin": "Compressor"}, parked.pending_plugin_read
    eq_again = resp(tool_use("read_plugin_values", {"plugin": "Channel EQ"}, "call_e2"))
    result, _ = await run([eq_again], messages=parked.messages, plugin_reads=True,
                          resume="allow_plugin_read", plugin_values=VALUES)
    outputs = {c["input"]["plugin"]: c["output"] for c in result.trace if c["tool"] == "read_plugin_values"}
    assert outputs == {"Compressor": VALUES, "Channel EQ": notes.PLUGIN_READ_ONE_AT_A_TIME}, outputs
    assert result.pending_plugin_read == {"plugin": "Channel EQ"}, result.pending_plugin_read
