"""DECIDER=sol: the Responses translation both ways, the Sol-only args, retries, and a full turn."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core import config
from app.pipeline import openai_io
from app.prompts import SOL_SYSTEM_PROMPT


def fc(name: str, args: dict, call_id: str) -> dict:
    return {"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args)}


def msg(text: str) -> dict:
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}


def rj(*output) -> dict:
    return {"model": "gpt-6.1-sol", "output": list(output), "error": None,
            "usage": {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 60}, "output_tokens": 20}}


def http(status: int, body) -> httpx.Response:
    req = httpx.Request("POST", openai_io.URL)
    return httpx.Response(status, request=req, **({"json": body} if isinstance(body, dict) else {"text": body}))


@pytest.fixture
def sol():
    """DECIDER=sol with the Responses endpoint mocked; script it with .side_effect = [httpx.Response, ...]."""
    post = AsyncMock()
    with patch.object(config, "DECIDER", "sol"), patch.object(config, "OPENAI_API_KEY", "test"), \
            patch.object(openai_io._client, "post", new=post), patch.object(openai_io.asyncio, "sleep", new=AsyncMock()):
        yield post


def test_input_translation() -> None:
    """System -> instructions + developer blocks; tool calls, results and images map to Responses items."""
    system = [{"type": "text", "text": "PROMPT"}, {"type": "text", "text": "LIVE"}]
    msgs = [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "AAA"}},
                                         {"type": "text", "text": "add a compressor", "cache_control": {"type": "ephemeral"}}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Adding it."},
                                              {"type": "tool_use", "id": "c1", "name": "open_plugin", "input": {"plugin": "Compressor"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": '{"attached": true}'}]}]
    rs = {"type": "reasoning", "id": "rs_1", "encrypted_content": "x", "summary": []}
    instructions, items = openai_io._input(system, msgs, {"c1": {"reasoning": [rs], "args": {}}})
    assert instructions == "PROMPT"
    assert items[0] == {"role": "developer", "content": "LIVE"}, items[0]
    assert items[1]["content"] == [{"type": "input_image", "image_url": "data:image/png;base64,AAA"},
                                   {"type": "input_text", "text": "add a compressor"}], items[1]
    assert items[2:] == [rs, {"role": "assistant", "content": "Adding it."},
                         {"type": "function_call", "call_id": "c1", "name": "open_plugin", "arguments": '{"plugin": "Compressor"}'},
                         {"type": "function_call_output", "call_id": "c1", "output": '{"attached": true}'}], items[2:]


def test_blocks_strip_sol_args() -> None:
    """`answer` becomes the text block, `remaining_actions` what's still owed, empty args are dropped."""
    blocks, remaining, _, sol_args, synth = openai_io._blocks(rj(fc(
        "open_setting", {"name": "buffer size", "value": "", "answer": "Raise the buffer.",
                         "remaining_actions": ["open Compressor"]}, "c1")))
    assert [b.type for b in blocks] == ["text", "tool_use"], blocks
    assert blocks[0].text == "Raise the buffer." and synth and remaining == ["open Compressor"]
    assert blocks[1].input == {"name": "buffer size"}, blocks[1].input
    assert sol_args["c1"] == {"answer": "Raise the buffer.", "remaining_actions": ["open Compressor"]}, sol_args


def test_replay_shows_sol_its_own_call() -> None:
    """The stripped args go back into the function call; text synthesized from `answer` goes back as Sol's message, not the arg."""
    msgs = [{"role": "user", "content": "x"},
            {"role": "assistant", "content": [{"type": "text", "text": "Adding it."},
                                              {"type": "tool_use", "id": "c1", "name": "open_plugin", "input": {"plugin": "Compressor"}}]}]
    stash = {"c1": {"args": {"answer": "Adding it.", "remaining_actions": ["set Threshold"]}, "reasoning": [], "synth_text": "Adding it."}}
    _, items = openai_io._input([{"type": "text", "text": "P"}], msgs, stash)
    assert items[1:] == [{"role": "assistant", "content": "Adding it."},
                         {"type": "function_call", "call_id": "c1", "name": "open_plugin", "arguments": json.dumps(
                             {"plugin": "Compressor", "remaining_actions": ["set Threshold"]})}], items


def test_written_text_wins_over_answer() -> None:
    """When Sol does write text, the answer arg doesn't double it."""
    blocks, remaining, _, _, synth = openai_io._blocks(rj(msg("Here's the fix."), fc(
        "open_plugin", {"plugin": "Compressor", "answer": "Adding it.", "remaining_actions": []}, "c1")))
    assert blocks[0].text == "Here's the fix." and not remaining and not synth, blocks


async def test_retries_rate_limit_and_malformed_args(sol) -> None:
    """A 429 and truncated tool arguments are retried; the third response is used."""
    sol.side_effect = [http(429, "slow down"), http(200, rj({"type": "function_call", "call_id": "c1", "name": "open_plugin",
                                                            "arguments": '{"plugin": "Comp'})),
                       http(200, rj(msg("Done.")))]
    resp = await openai_io.call_decider([{"type": "text", "text": "P"}], [], [{"role": "user", "content": "hi"}])
    assert sol.call_count == 3 and resp.content[0].text == "Done.", resp
    assert resp.usage.input_tokens == 40 and resp.usage.cache_read_input_tokens == 60, resp.usage


async def test_final_call_sends_tools_with_choice_none(sol) -> None:
    """The tools-off final call still sends Sol's tools (history may hold calls), with tool_choice none."""
    sol.side_effect = [http(200, rj(msg("ok")))]
    await openai_io.call_decider([{"type": "text", "text": "P"}], None, [{"role": "user", "content": "hi"}])
    body = sol.call_args.kwargs["json"]
    assert body["tool_choice"] == "none" and {t["name"] for t in body["tools"]} >= {"open_plugin"}, body


async def test_sol_turn_remaining_actions_and_replay(sol, run) -> None:
    """A full Sol turn: no KB in the prompt or tools, remaining_actions keeps the turn open for the
    second action, its reasoning and plan are replayed, and the answer arg becomes the decider text."""
    rs = {"type": "reasoning", "id": "rs_1", "encrypted_content": "enc", "summary": []}
    sol.side_effect = [
        http(200, rj(rs, fc("open_plugin", {"plugin": "Compressor", "answer": "Adding a compressor at -18 dB.",
                                            "remaining_actions": ["set Compressor Threshold to -18"]}, "c1"))),
        http(200, rj(fc("set_param", {"plugin": "Compressor", "param": "Threshold", "value": "-18", "answer": "",
                                      "remaining_actions": []}, "c2"))),
    ]
    result, _ = await run([], messages=[{"role": "user", "content": "add a compressor with threshold -18"}], early_exit=True)
    assert sol.call_count == 2, sol.call_count
    first, second = (c.kwargs["json"] for c in sol.call_args_list)
    assert first["instructions"] == SOL_SYSTEM_PROMPT
    assert "cite_kb" not in {t["name"] for t in first["tools"]}
    assert rs in second["input"], second["input"]
    replayed = next(i for i in second["input"] if i.get("call_id") == "c1" and i["type"] == "function_call")
    assert json.loads(replayed["arguments"])["remaining_actions"] == ["set Compressor Threshold to -18"], replayed
    assert [c["tool"] for c in result.trace] == ["open_plugin", "set_param"], result.trace
    assert result.trace[0]["input"] == {"plugin": "Compressor"}, result.trace[0]["input"]
    assert result.messages[1]["content"][0] == {"type": "text", "text": "Adding a compressor at -18 dB."}, result.messages[1]
