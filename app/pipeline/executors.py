"""Tool name -> executor, and the status line shown while a tool runs. Tests swap
entries with patch.dict(executors.EXECUTORS, ...) and patch `executors.research`."""
from app import research, tools


async def _ack_clarifying_question() -> dict:
    """The call itself is the signal; it still needs a real tool_result round-trip."""
    return {"acknowledged": True}


async def _now(result: dict) -> dict:
    """Wraps a synchronous executor's result so every entry can be awaited."""
    return result


async def _no_plugin_reader(inp: dict) -> dict:
    """The client runs the read: a read call parks the turn and its result comes back on the
    resume (dispatch). Reaching this means it wasn't parked."""
    return {"error": f"couldn't read {inp.get('plugin')!r} -- say you can't see its exact settings"}


EXECUTORS = {
    "open_plugin": lambda inp, fixture: _now(tools.queue_open_plugin(inp)),
    "set_param": lambda inp, fixture: _now(tools.queue_set_param(inp)),
    "open_setting": lambda inp, fixture: _now(tools.queue_open_setting(inp, fixture)),
    "ask_clarifying_question": lambda inp, fixture: _ack_clarifying_question(),
    "web_research": lambda inp, fixture: research.web_research(inp["query"]),
    "read_plugin_values": lambda inp, fixture: _no_plugin_reader(inp),
}

# Only the one real wait gets a status; everything else is instant and would just flash.
_TOOL_STATUS_PRIORITY = ["web_research"]


def status_for_tools(tool_uses: list) -> str | None:
    names = {tu.name for tu in tool_uses}
    for name in _TOOL_STATUS_PRIORITY:
        if name not in names:
            continue
        if name == "web_research":
            return "Searching the web for a verified answer…"
    return None
