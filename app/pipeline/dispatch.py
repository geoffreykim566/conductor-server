"""Running one tool call against the turn's card: duplicates, re-visited settings and the
attach cap. Rules: README.md (One card per turn)."""
import json

from app import tools
from app.pipeline import notes, settings
from app.pipeline.cards import attach_key, endorse_key, mark_replaced
from app.pipeline.executors import EXECUTORS
from app.pipeline.turn_state import TurnState


async def _execute(tu, state: TurnState, ax_fixture: dict | None, research_denied: bool,
                   plugin_read: dict | None) -> dict:
    name, inp = tu.name, tu.input
    if name == "read_plugin_values" and plugin_read is not None:
        return dict(plugin_read)
    if name in tools.ACTION_TOOLS and attach_key(name, inp) in state.attach_keys:
        return {"attached": False, "reason": notes.DUPLICATE_ATTACH_REFUSAL}
    if name == "open_setting" and endorse_key(name, inp) in state.route_spans:
        # One visit per setting per card; the later call is the correction and wins.
        result = await EXECUTORS[name](inp, ax_fixture)
        if result.get("attached"):
            key = endorse_key(name, inp)
            start, end = state.route_spans[key]
            new = result.get("steps") or []
            state.replace_steps(start, end, new)
            state.route_spans[key] = (start, start + len(new))
            mark_replaced(state.trace, inp.get("name"))
            state.attach_keys.add(attach_key(name, inp))
            result = {**result, "replaces_earlier": True}
        return result
    if name in tools.ACTION_TOOLS and len(state.attach_keys) >= settings.MAX_ATTACHES_PER_TURN:
        return {"attached": False, "reason": notes.ATTACH_CAP_REFUSAL}
    if name == "web_research" and research_denied:
        return dict(notes.RESEARCH_DECLINED)
    executor = EXECUTORS.get(name)
    return {"error": f"unknown tool {name!r}"} if executor is None else await executor(inp, ax_fixture)


async def handle_tool_use(tu, state: TurnState, ax_fixture: dict | None,
                          research_denied: bool, usage: list[dict], plugin_read: dict | None = None) -> dict:
    """Run one tool call, record it on the state, and return its tool_result block.
    `plugin_read`: a read_plugin_values call's result, supplied by the client on resume."""
    result = await _execute(tu, state, ax_fixture, research_denied, plugin_read)
    # web_research reports its own API spend; count it, never show it to the model.
    call_usage = result.pop("_usage", None) if isinstance(result, dict) else None
    if call_usage:
        usage.append(call_usage)
    state.trace.append({"tool": tu.name, "input": tu.input, "output": result})
    if tu.name in tools.ACTION_TOOLS and result.get("attached") and not result.get("replaces_earlier"):
        span = state.append_steps(tu.name, tu.input, result.get("steps"))
        if tu.name == "open_setting":
            state.route_spans[endorse_key(tu.name, tu.input)] = span
    return {"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(result)}
