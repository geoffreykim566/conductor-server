"""Writer A/B switches: no writer for Sol, and the v2 card block."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.core import config
from app.pipeline import settings, writer

PANE_TRACE = [{"tool": "open_setting", "input": {"name": "buffer size"}, "output": {"attached": True}}]


async def test_no_writer_sends_sol_text_as_is() -> None:
    """SOL_WRITER none: Sol's text is the reply, the writer isn't called, a tool-only question is appended."""
    with patch.object(config, "DECIDER", "sol"), patch.object(settings, "SOL_WRITER", "none"), \
            patch.object(writer, "write_response", AsyncMock()) as w:
        reply, _ = await writer.finalize_answer(PANE_TRACE, None, "Press Run to open it.", [{"role": "user", "content": "open the buffer"}],
                                                None, [], question="Which size?", has_actions=True)
    assert reply == "Press Run to open it.\n\nWhich size?" and not w.called, reply


async def test_no_writer_undo_is_declined_in_code() -> None:
    """SOL_WRITER none: an undo request gets the fixed decline, whatever Sol wrote."""
    with patch.object(config, "DECIDER", "sol"), patch.object(settings, "SOL_WRITER", "none"):
        reply, _ = await writer.finalize_answer([], None, "Done, it's undone.", [{"role": "user", "content": "undo that"}], None, [])
    assert reply == writer.UNDO_DECLINE, reply


def test_card_v2_keeps_steps_and_drops_option_note() -> None:
    """WRITER_CARD_V2: no "one short sentence" rule and no option note from the card line."""
    with patch.object(settings, "WRITER_CARD_V2", True):
        facts = writer._facts("strong", PANE_TRACE, "Sol text", [{"role": "user", "content": "x"}], None, False, True)
    assert "one short sentence" not in facts and "naming the options" not in facts and "by hand" in facts, facts
    with patch.object(settings, "WRITER_CARD_V2", False):
        facts = writer._facts("strong", PANE_TRACE, "Sol text", [{"role": "user", "content": "x"}], None, False, True)
    assert "one short sentence" in facts and "naming the options" in facts, facts
