"""Shaping the round-tripped history: trimming it, and spotting a parked research or plug-in-read turn."""
from app.core.config import MAX_HISTORY_MESSAGES


def _pending_call(history: list[dict] | None, name: str) -> dict | None:
    """Input of the `name` call a parked transcript is waiting on, or None if `history`
    doesn't end in an assistant message with that tool_use (and no results after it)."""
    if not history:
        return None
    last = history[-1]
    if last.get("role") != "assistant" or not isinstance(last.get("content"), list):
        return None
    for b in last["content"]:
        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == name:
            return b.get("input") if isinstance(b.get("input"), dict) else {}
    return None


def pending_research_query(history: list[dict] | None) -> str | None:
    """The web_research query a parked transcript is waiting on, or None."""
    call = _pending_call(history, "web_research")
    if call is None:
        return None
    q = call.get("query")
    return q if isinstance(q, str) else ""


def pending_plugin_read(history: list[dict] | None) -> dict | None:
    """The read_plugin_values call ({plugin, track?}) a parked transcript is waiting on, or None."""
    return _pending_call(history, "read_plugin_values")


def trim_history(messages: list[dict]) -> list[dict]:
    """Keep the newest MAX_HISTORY_MESSAGES, snapped forward to the next real
    turn boundary (a plain-string user message) so a trim never starts on a
    dangling tool_result whose tool_use got cut — a call output with no call
    is malformed history (it was rejected outright by the Anthropic API). If no such boundary exists in the window
    (a pathologically long single tool-loop), don't truncate at all rather
    than risk sending a broken message list.
    """
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    window = messages[-MAX_HISTORY_MESSAGES:]
    for i, msg in enumerate(window):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return window[i:]
    return messages
