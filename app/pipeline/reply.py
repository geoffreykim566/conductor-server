"""The reply: Sol's own text, as written. No writer model: one rewording Haiku dropped steps
and invented picks, and Sol's text needed nothing it added (README: Reply)."""
import re

from app.pipeline import notes
from app.pipeline.confidence import confidence_tier
from app.pipeline.heuristics import is_undo_request, last_user_text
from app.pipeline.model_io import OnChunk


async def finalize_reply(trace: list[dict], walkthrough_steps: list | None, text: str,
                         messages: list[dict], on_chunk: OnChunk | None,
                         is_clarifying_question: bool = False, question: str = "") -> tuple[str, str]:
    """The reply text and its tier. An undo request gets the fixed decline whatever the
    text says; a question asked only through the tool is appended."""
    tier = confidence_tier(trace, walkthrough_steps, is_clarifying_question)
    if is_undo_request(last_user_text(messages)):
        reply = notes.UNDO_DECLINE
    else:
        reply = text.strip() or question
        if question and question not in reply:
            reply += "\n\n" + question
    reply = space_steps(reply)
    if on_chunk and reply:
        await on_chunk(reply)
    return reply, tier


# A numbered line right after another line gets a blank line above it (user call 11-06: cleaner).
_STEP_START = re.compile(r"(?<!\n)\n(?=\d+[.)]\s)")


def space_steps(text: str) -> str:
    return _STEP_START.sub("\n\n", text)
