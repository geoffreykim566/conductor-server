"""The one place the pipeline calls the decider (Sol, through openai_io), plus converting
response blocks back into request-shaped dicts. Tests patch `model_io.call_model`."""
from typing import Awaitable, Callable

from app.pipeline import openai_io

OnChunk = Callable[[str], Awaitable[None]]
OnStatus = Callable[[str], Awaitable[None]]


async def call_model(system: list[dict], tools_param: list[dict] | None, msgs: list[dict],
                     tool_choice: dict | None = None):
    """One decider call. tools_param=None is the tools-off final call."""
    return await openai_io.call_decider(system, tools_param, msgs, tool_choice)


def serialize_content(content: list) -> list[dict]:
    """Response blocks -> plain request-shape dicts: Result.messages is replayed as the
    next turn's history (README: History round-trip)."""
    out = []
    for b in content:
        if b.type == "text":
            out.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return out


def usage_dict(u) -> dict:
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }
