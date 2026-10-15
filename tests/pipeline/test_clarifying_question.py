"""ask_clarifying_question ends the turn, and its `question` always reaches the reply."""
from __future__ import annotations

import importlib
from unittest.mock import patch

from conftest import resp, text_block, tool_use

from app.pipeline import writer

# app.pipeline re-exports the respond() function under the module's name.
respond_mod = importlib.import_module("app.pipeline.respond")

QUESTION = "Which track is the vocal on: 1) Audio 1, 2) Audio 2?"


async def test_bare_question_sent_as_written(run) -> None:
    """A bare ask_clarifying_question call ends the turn; its question is the reply, streamed, with no writer call."""
    chunks: list[str] = []

    async def on_chunk(t: str) -> None:
        chunks.append(t)

    with patch.object(writer, "write_response", wraps=writer.write_response) as w:
        result, calls = await run([resp(tool_use("ask_clarifying_question", {"question": QUESTION}, "q1")),
                                   resp(text_block("more"))], on_chunk=on_chunk)
    assert len(calls) == 1, len(calls)
    assert result.text == QUESTION, result.text
    assert chunks == [QUESTION], chunks
    assert not w.called
    assert result.confidence_tier == "generic", result.confidence_tier


async def test_written_text_goes_to_writer_with_question(run) -> None:
    """When the decider also wrote text, that text stands and the writer is told to ask the question."""
    with patch.object(writer, "write_response", wraps=writer.write_response) as w:
        result, _ = await run([resp(text_block("Which track?"),
                                    tool_use("ask_clarifying_question", {"question": QUESTION}, "q1"))])
    assert result.text == "writer text", result.text
    facts = w.call_args.args[0]
    assert QUESTION in facts and "Which track?" in facts, facts
    assert facts.index(QUESTION) < facts.index("Which track?"), facts


async def test_undo_request_keeps_writer(run) -> None:
    """An undo request still gets the writer's in-code decline, even when the decider only asked."""
    with patch.object(writer, "write_response", wraps=writer.write_response) as w:
        result, _ = await run([resp(tool_use("ask_clarifying_question", {"question": QUESTION}, "q1"))],
                              messages=[{"role": "user", "content": "undo that last change"}])
    assert w.called
    assert QUESTION not in w.call_args.args[0], w.call_args.args[0]
    assert result.text == "writer text", result.text
