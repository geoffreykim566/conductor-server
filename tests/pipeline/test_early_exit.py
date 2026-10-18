"""Early exit (settings.EARLY_EXIT_ON_ACTION): an iteration of only accepted actions ends the turn."""
from __future__ import annotations

from conftest import open_plugin, resp, text_block, tool_use


async def test_direct_action_exits(run) -> None:
    """A direct action that attached ends the turn without another decider call."""
    result, calls = await run([resp(open_plugin("Compressor", "a1")), resp(text_block("done"))], early_exit=True)
    assert len(calls) == 1, len(calls)
    assert result.walkthrough_steps == [{"ax_open_plugin": "Compressor"}], result.walkthrough_steps


async def test_refusal_keeps_looping(run) -> None:
    """A refused action keeps looping so the decider can react."""
    _, calls = await run([resp(tool_use("open_setting", {"name": "no such route"}, "a1")),
                          resp(text_block("done"))], early_exit=True)
    assert len(calls) == 2, len(calls)


async def test_pane_only_dropdown_with_unnamed_options_keeps_looping(run) -> None:
    """A dropdown opened without a value, with text naming none of its options, gets the follow-up call to ask."""
    _, calls = await run([resp(text_block("Opening the import defaults."),
                               tool_use("open_setting", {"name": "smart tempo import default"}, "a1")),
                          resp(text_block("Which one: Flex On, Smart Tempo On or Flex On, Smart Tempo Off?"))], early_exit=True)
    assert len(calls) == 2, len(calls)


async def test_pane_only_dropdown_with_named_option_exits(run) -> None:
    """Text that already names an option ends the turn as usual."""
    _, calls = await run([resp(text_block("Pick Flex On, Smart Tempo On there."),
                               tool_use("open_setting", {"name": "smart tempo import default"}, "a1")),
                          resp(text_block("more"))], early_exit=True)
    assert len(calls) == 1, len(calls)
