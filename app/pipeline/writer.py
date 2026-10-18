"""The writer: a cheaper model that turns the decider's decided facts into the reply,
never seeing tools, results or confidence. The facts block it gets is built here,
in code. Why the split and each facts rule exists: README.md (Writer)."""
from app.core import config
from app.core.config import WRITER_MODEL
from app.pipeline import model_io, settings
from app.pipeline.cards import card_descriptions
from app.pipeline.confidence import confidence_tier
from app.pipeline.heuristics import is_undo_request, last_user_text
from app.pipeline.model_io import OnChunk
from app.prompts import WRITER_SYSTEM_PROMPT


# The in-code undo decline when there's no writer to phrase it (SOL_WRITER "none").
UNDO_DECLINE = ("I can't undo changes by message yet. Scroll up to that change's card and "
                "press Revert to put it back.")


def plain_history(messages: list[dict]) -> list[dict]:
    """Decider transcript -> plain user/assistant text turns only. Turns with no
    text (pure tool calls / tool results) are dropped, not sent empty."""
    plain = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            if content:
                plain.append({"role": msg["role"], "content": content})
            continue
        if isinstance(content, list):
            text = "".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
            if text:
                plain.append({"role": msg["role"], "content": text})
    return plain


async def write_response(
    facts: str,
    prior_messages: list[dict],
    on_chunk: OnChunk | None,
) -> tuple[str, dict]:
    system_text = (
        WRITER_SYSTEM_PROMPT + "\n\n## What to say this turn\n\n" + facts
    )
    system = [{"type": "text", "text": system_text}]
    history = plain_history(prior_messages)
    resp = await model_io.call_model(system, None, history, on_chunk, model=settings.WRITER_MODEL or WRITER_MODEL)
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, model_io.usage_dict(resp.usage)


def _facts(
    tier: str,
    trace: list[dict],
    text: str,
    prior_messages: list[dict],
    live_state: str | None,
    had_screenshots: bool,
    has_actions: bool,
) -> str:
    """The writer's facts: the decider's text plus code-built framing."""
    facts = text
    if has_actions:
        # The card's contents come from the calls, not the decider's prose, and
        # nothing on it has run yet.
        queued = "\n".join(f"- {line}" for line in card_descriptions(trace, ask_note=not settings.WRITER_CARD_V2))
        # v2: v1's "one short sentence" cut manual steps and checklists, and the option note
        # became option lists the text never offered (sol-log.md, 10-17).
        rule = ("NONE of them has happened yet: describe them as about to happen, never as done. "
                "Keep everything else the text below says, including steps the user does by hand "
                "after the card and any question it asks. Don't add steps, menu paths, options or "
                "questions it doesn't contain." if settings.WRITER_CARD_V2 else
                "NONE of them has happened yet. Say in "
                "one short sentence what the card will do, as about to happen (\"This adds X to "
                "the selected track\" / \"This opens Y\"), never as done, and don't list manual "
                "steps for it -- the card does it. Don't mention anything not listed above.")
        facts = (
            "The reply has a card attached, holding exactly these steps, which the user "
            "runs with one press:\n" + queued + "\n\n" + rule + "\n\n" + text
        )
    if is_undo_request(last_user_text(prior_messages)):
        facts = (
            "The user asked you to undo or revert a change. You can't do that by message yet: "
            "say so in one short sentence, and that they can scroll up to that change's card "
            "and press Revert. Don't suggest any other way to undo it, and don't say anything "
            "was undone.\n\n" + facts
        )
    if tier == "moderate" and settings.HEDGE_MODERATE_TURNS:
        facts = (
            "No verified, confirmed answer was established for this turn -- no "
            "confident, specific menu path, setting, or fix was found. Say plainly "
            "that you don't have a verified answer for this; if you offer anything "
            "further, frame it clearly as unconfirmed general guidance, not a "
            "confirmed fix.\n\n" + text
        )
    # The writer never sees the screenshots; without this it says it can't see the screen.
    if had_screenshots:
        facts = (
            "The facts below were worked out from screenshots of the user's open "
            "Logic Pro windows (plus live project state where noted). Speak as "
            "someone looking at their screen; never say you can't see it.\n\n"
            + facts
        )
    # Appended last so no branch above can drop it. Partial: authoritative only
    # for what it lists.
    if live_state:
        facts += (
            "\n\n## Live values read from the Logic Pro project this turn (not the "
            "user's claim). Authoritative for the items listed here -- if anything "
            "above contradicts one of these values, this is correct. Labels are "
            "Logic's internal accessibility names, not the on-screen ones:\n\n"
            + live_state
        )
    return facts


async def finalize_answer(
    trace: list[dict],
    walkthrough_steps: list | None,
    text: str,
    prior_messages: list[dict],
    on_chunk: OnChunk | None,
    usage: list[dict],
    is_clarifying_question: bool = False,
    question: str = "",
    live_state: str | None = None,
    had_screenshots: bool = False,
    has_actions: bool = False,
) -> tuple[str, str]:
    """Compute the tier, build the facts, run the writer. Returns (reply, tier)."""
    tier = confidence_tier(trace, walkthrough_steps, is_clarifying_question)
    undo = is_undo_request(last_user_text(prior_messages))
    # A bare question goes out as written: the writer answered it instead (README: Writer).
    if question and not text.strip() and not undo:
        if on_chunk:
            await on_chunk(question)
        return question, tier
    if config.DECIDER == "sol" and settings.SOL_WRITER == "none":
        reply = (UNDO_DECLINE if undo else text.strip()) or question
        if question and not undo and question not in reply:
            reply += "\n\n" + question
        if on_chunk:
            await on_chunk(reply)
        return reply, tier
    facts = _facts(tier, trace, text, prior_messages, live_state, had_screenshots, has_actions)
    if question and not undo:
        facts = (
            "This reply asks the user a question and ends there. Ask exactly this question, "
            "keeping its wording and options:\n\n" + question + "\n\nDon't answer it, guess "
            "the answer, or give steps or menu paths. If the text below already asks it, ask "
            "it once.\n\n" + facts
        )
    resp_text, writer_usage = await write_response(facts, prior_messages, on_chunk)
    usage.append(writer_usage)
    return resp_text, tier
