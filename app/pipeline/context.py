"""What the decider sees besides history: the cached system prompt and tools, this turn's live
state block, and this turn's screenshots spliced into the user message per call.
Caching and why screenshots never enter `msgs`: README.md (Context & caching)."""
from dataclasses import dataclass

from app import tools
from app.pipeline.transcript import last_user_text_index
from app.prompts import SYSTEM_PROMPT

_LIVE_STATE_HEADER = (
    "\n\n## Live state for this turn\n\n"
    "Values read directly from the running Logic Pro project via the "
    "Accessibility API -- not something the user said or you inferred. "
    "Authoritative for every control and value listed here; beats a stated "
    "claim or seed_weight for those items. It is partial: anything it doesn't "
    "list is not unknown -- read it from the attached screenshot. Labels are "
    "Logic's internal accessibility names, not the on-screen ones.\n\n"
)


def media_type_for_b64(b64: str) -> str:
    """Screenshots carry no media type: v0.3.0 clients send PNG, v0.3.1+ JPEG.
    base64 of a JPEG's SOI marker starts "/9j/"; anything else is treated as PNG."""
    if b64.startswith("/9j/"):
        return "image/jpeg"
    return "image/png"


@dataclass
class TurnContext:
    system: list[dict]
    tools: list[dict]
    live_state: str | None
    turn_idx: int | None  # this turn's user message in msgs
    screenshot_msg: dict | None

    @property
    def had_screenshots(self) -> bool:
        return self.screenshot_msg is not None

    @classmethod
    def build(cls, msgs: list[dict], screenshots_b64: list[str] | None,
              ax_fixture: dict | None, ax_state: str | None, plugin_reads: bool = False) -> "TurnContext":
        # ax_fixture: the battery's hand-written state. ax_state: the client's live AX dump.
        state_blocks = []
        if ax_fixture:
            state_blocks.append("\n".join(f"- {k}: {v}" for k, v in ax_fixture.items()))
        if ax_state:
            state_blocks.append(ax_state)
        live_state = "\n\n".join(state_blocks) if state_blocks else None

        # Live state is its own block after the static prompt, so the prompt prefix still caches.
        system = [{"type": "text", "text": SYSTEM_PROMPT}]
        if state_blocks:
            system.append({
                "type": "text",
                "text": _LIVE_STATE_HEADER + live_state,
            })

        # On a resume the user message isn't msgs[-1] (the parked tail follows it).
        turn_idx = last_user_text_index(msgs) if msgs else None
        screenshot_msg = None
        if screenshots_b64 and msgs and turn_idx is not None:
            screenshot_msg = {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type_for_b64(b64), "data": b64}}
                    for b64 in screenshots_b64
                ] + [{"type": "text", "text": msgs[turn_idx]["content"]}],
            }
        # Only a client that can run the read is offered it (v0.4.1 would get an unanswerable park).
        offered = [t for t in tools.TOOLS if plugin_reads or t["name"] != "read_plugin_values"]
        return cls(system=system, tools=offered, live_state=live_state,
                   turn_idx=turn_idx, screenshot_msg=screenshot_msg)

    def for_call(self, base: list[dict]) -> list[dict]:
        """Per-call copy of `base` with this turn's user message swapped for its
        screenshot version. Only ever on the copy: `msgs` goes back to the client as
        history, and the history validator rejects images."""
        if self.turn_idx is None or self.screenshot_msg is None:
            return base
        out = list(base)
        out[self.turn_idx] = self.screenshot_msg
        return out
