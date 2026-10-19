"""Turn text: a restated reply replaces the earlier copy; text beside an all-refused call gives way."""
from __future__ import annotations

from conftest import resp, text_block, tool_use

from app.pipeline.turn_state import TurnState


def test_restated_reply_replaces_the_earlier_copy() -> None:
    """A follow-up's restatement keeps one copy (the later); distinct text and action-call text are kept."""
    s = TurnState()
    s.add_text("Press Run to open the Sample Rate setting, then compare it with your interface. Is the pitch lower too?")
    s.add_text("Press Run to open the project’s Sample Rate setting, then compare it with your interface.\n\nIs the pitch lower too?",
               follow_up=True)
    assert len(s.text_parts) == 1 and "project’s" in s.text_parts[0], s.text_parts
    s.add_text('Which rate do you want: "44.1 kHz" or "48 kHz"?', follow_up=True)
    assert len(s.text_parts) == 2, s.text_parts
    s2 = TurnState()
    s2.add_text("Press Run to load Compressor on the selected track.")
    s2.add_text("Press Run to open Channel EQ on the selected track.")
    assert len(s2.text_parts) == 2, s2.text_parts


async def test_text_beside_refused_call_gives_way(run) -> None:
    """A refused dropdown pick's "Press Run to set X" is dropped once the next call writes the reply."""
    result, _ = await run([
        resp(text_block("Press Run to set imported files to Flex On, Smart Tempo Off."),
             tool_use("open_setting", {"name": "smart tempo import default", "value": "Flex On"}, "c1")),
        resp(text_block("Press Run to open the import setting. Which Flex On option do you want?"),
             tool_use("open_setting", {"name": "smart tempo import default"}, "c2")),
        resp(text_block("")),
    ], messages=[{"role": "user", "content": "set imported files to flex on"}])
    assert "Smart Tempo Off" not in result.text and "Which Flex On option" in result.text, result.text
