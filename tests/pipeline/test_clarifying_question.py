"""ask_clarifying_question ends the turn, and its `question` always reaches the reply."""
from __future__ import annotations

from conftest import resp, text_block, tool_use

from app.pipeline import notes

QUESTION = "Which track is the vocal on: 1) Audio 1, 2) Audio 2?"


async def test_bare_question_sent_as_written(run) -> None:
    """A bare ask_clarifying_question call ends the turn; its question is the reply, streamed."""
    chunks: list[str] = []

    async def on_chunk(t: str) -> None:
        chunks.append(t)

    result, calls = await run([resp(tool_use("ask_clarifying_question", {"question": QUESTION}, "q1")),
                               resp(text_block("more"))], on_chunk=on_chunk)
    assert len(calls) == 1, len(calls)
    assert result.text == QUESTION, result.text
    assert chunks == [QUESTION], chunks
    assert result.confidence_tier == "generic", result.confidence_tier


async def test_written_text_then_question(run) -> None:
    """Text written beside the question comes first, then the question; a question the text already holds isn't repeated."""
    result, _ = await run([resp(text_block("It depends on the track."),
                                tool_use("ask_clarifying_question", {"question": QUESTION}, "q1"))])
    assert result.text == "It depends on the track.\n\n" + QUESTION, result.text
    result, _ = await run([resp(text_block("Quick check. " + QUESTION),
                                tool_use("ask_clarifying_question", {"question": QUESTION}, "q1"))])
    assert result.text == "Quick check. " + QUESTION, result.text


async def test_undo_request_gets_the_fixed_decline(run) -> None:
    """An undo request gets the in-code decline, whatever the decider wrote or asked."""
    result, _ = await run([resp(text_block("Done, I've undone it."),
                                tool_use("ask_clarifying_question", {"question": QUESTION}, "q1"))],
                          messages=[{"role": "user", "content": "undo that last change"}])
    assert result.text == notes.UNDO_DECLINE, result.text
