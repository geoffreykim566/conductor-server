"""Code-side reads of the user's own message: is it a question, an undo request, a
re-ask, may its card auto-run. Each phrase list is deliberately narrow; why each phrase
is in or out: README.md (Heuristics). Re-sweep the battery whenever a list changes."""
import re

from app.pipeline.transcript import last_user_text_index

# Question-shaped or bulk requests never auto-run.
_QUESTION_START = re.compile(
    r"^(?:how|what|whats|why|where|wheres|when|which|who|is|are|does|did|should|"
    r"do (?:i|you|we)|can (?:i|we)|could (?:i|we)|explain|show me how|tell me)\b"
)
_QUESTION_ANYWHERE = re.compile(r"\b(?:how (?:do|can|would|should) (?:i|we|you)|how to|show me how|explain)\b")
_POLITE_REQUEST = re.compile(
    r"^(?:please\s+)?(?:can|could|would|will) you\b(?!\s+(?:explain|tell|show me how|describe|help me understand))"
)
_BULK_SIGNALS = (
    "every track", "all tracks", "all the tracks", "all my tracks", "every plugin", "all plugins",
    "all the plugins", "remove all", "delete all", "clear all", "reset all", "whole session",
    "entire session", "whole project", "entire project",
)

# Typed undo/revert is declined (the card's Revert button does it). Only an
# instruction to Conductor counts, not "how do i undo a cut in logic".
_UNDO_REQUEST = re.compile(
    r"\b(?:undo|revert|(?:put|change|set|switch|turn) (?:it|that|this|them|those) back)\b"
)

# Asking to see an earlier destination again (drives backfill.py).
_REASK_SIGNALS = (
    "remind me", "reminder", "one more time", "show me that",
    "show that again", "where was", "where is that", "closed the window",
    "lost the window",
)

def last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"].lower().replace("’", "'").replace("'", "").strip()
    return ""


def offered_text(messages: list[dict]) -> str:
    """The reply the newest user message answers (see tools.TURN_OFFERED_TEXT).
    Any reply counts, since options are often offered as a statement; a first
    turn has none, so the model still can't pick a value the user didn't name."""
    i = last_user_text_index(messages)
    for m in reversed(messages[:i] if i is not None else []):
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        # A question asked only through ask_clarifying_question offers options too.
        text = c if isinstance(c, str) else " ".join(
            b.get("text", "") if b.get("type") == "text" else str((b.get("input") or {}).get("question", ""))
            for b in c if isinstance(b, dict) and (b.get("type") == "text" or b.get("name") == "ask_clarifying_question")
        ) if isinstance(c, list) else ""
        if text.strip():
            return text.lower()
    return ""


def is_question(text: str) -> bool:
    if _POLITE_REQUEST.match(text):
        return bool(_QUESTION_ANYWHERE.search(text))
    return text.endswith("?") or bool(_QUESTION_START.match(text) or _QUESTION_ANYWHERE.search(text))


def is_undo_request(text: str) -> bool:
    return bool(text) and not is_question(text) and bool(_UNDO_REQUEST.search(text))


def auto_run_ok(messages: list[dict], card: list | None) -> bool:
    """Whether the user's own message is a direct instruction (not a question,
    not bulk). respond.py adds the other auto-run conditions."""
    if not card:
        return False
    text = last_user_text(messages)
    return bool(text) and not is_question(text) and not any(sig in text for sig in _BULK_SIGNALS)


def last_user_message_matches(messages: list[dict], signals: tuple[str, ...]) -> bool:
    """True if the newest message is a user turn containing any of the phrases
    (case/apostrophe-insensitive substring match)."""
    if not messages or messages[-1].get("role") != "user":
        return False
    user_text = messages[-1].get("content")
    if not isinstance(user_text, str):
        return False
    normalized = user_text.lower().replace("'", "")
    return any(sig in normalized for sig in signals)


def is_reask(messages: list[dict]) -> bool:
    return last_user_message_matches(messages, _REASK_SIGNALS)
