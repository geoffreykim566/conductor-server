"""Fixed text the pipeline hands the decider (refusals and nudges) or the user (the undo
decline). Code decides when each applies; this file only holds the wording."""
from app.pipeline import settings

# In place of a web_research call the user declined.
RESEARCH_DECLINED = {
    "error": (
        "The user declined web research for this turn. Do not call web_research "
        "again this turn. Answer from general Logic Pro knowledge if you can, "
        "framed clearly as unverified general guidance, not a confirmed answer -- "
        "or say plainly that you don't have a verified answer for this."
    )
}

# In place of a read_plugin_values call the user declined.
PLUGIN_READ_DECLINED = {
    "error": (
        "The user declined opening the plug-in to read its values. Do not call "
        "read_plugin_values again this turn. Answer without its exact settings: say you "
        "can't see them, and don't estimate them from knob positions or the screenshot."
    )
}

TOOL_NUDGE = (
    "Call a tool before you answer: the action the user just agreed to (each turn gets its own "
    "card, so queue it again even if an earlier reply offered it), or ask_clarifying_question "
    "if you can't tell what they want run."
)
FINAL_ANSWER_NUDGE = "\n\nAnswer now with your best available information — no more tool calls."

ATTACH_CAP_REFUSAL = (
    f"this turn already has {settings.MAX_ATTACHES_PER_TURN} steps queued, the limit for one "
    "card. Tell the user what's queued and that you'll do the rest when they ask next."
)
DUPLICATE_ATTACH_REFUSAL = "this exact step is already queued this turn -- it runs once."

# Sent to the user in place of the reply when they ask to undo or revert by message.
UNDO_DECLINE = ("I can't undo changes by message yet. Scroll up to that change's card and "
                "press Revert to put it back.")
