"""Everything a turn accumulates while its tool loop runs, and rebuilding it from a
parked transcript on resume (nothing is stored server-side between requests)."""
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app import tools
from app.pipeline.cards import attach_key, endorse_key, mark_replaced, replace_span


def _restates(new: str, old: str) -> bool:
    """`new` is a rewrite of `old`: Sol rewrote its whole reply on the ask_options follow-up,
    word for word or reworded (sol-log.md, 10-17)."""
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[‘’“”]", "'", s)).strip().lower()
    a, b = norm(new), norm(old)
    return b in a or SequenceMatcher(None, a, b).ratio() >= 0.6


@dataclass
class TurnState:
    trace: list[dict] = field(default_factory=list)
    # Every iteration's text, not just the last: text written alongside a tool
    # call is part of the answer.
    text_parts: list[str] = field(default_factory=list)
    card_steps: list = field(default_factory=list)  # every attach this turn, in call order
    attach_keys: set = field(default_factory=set)
    route_spans: dict[str, tuple[int, int]] = field(default_factory=dict)  # model-called open_setting -> its span
    more_actions: bool = False  # the last decider call still owed an action (Sol's remaining_actions)
    provisional_text: list[str] = field(default_factory=list)  # written beside calls that were all refused

    @property
    def steps(self) -> list | None:
        return list(self.card_steps) or None

    def add_text(self, text: str, follow_up: bool = False) -> None:
        """Keep an iteration's text. Text written beside calls that were all refused gives way to
        it, and a follow-up's text (no tool call) replaces a part it restates. Only a follow-up:
        two different action lines ("Press Run to load X" / "...open Y") score as alike as a
        reworded restatement (README: Turn text)."""
        drop = set(self.provisional_text)
        self.provisional_text = []
        self.text_parts = [p for p in self.text_parts if p not in drop and not (follow_up and _restates(text, p))]
        self.text_parts.append(text)

    def append_steps(self, tool: str, inp: dict, steps: list | None) -> tuple[int, int]:
        start = len(self.card_steps)
        self.card_steps.extend(steps or [])
        self.attach_keys.add(attach_key(tool, inp))
        return start, len(self.card_steps)

    def replace_steps(self, start: int, end: int, new: list) -> None:
        replace_span(self.card_steps, start, end, new, self.route_spans)


def restore_turn_state(tail: list[dict]) -> TurnState:
    """Replay the completed tool-loop iterations between the user message and the
    pending assistant message, so an attach made before a research prompt survives."""
    state = TurnState()
    calls: dict[str, dict] = {}
    for m in tail:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if m.get("role") == "assistant":
                if b.get("type") == "text" and b.get("text"):
                    state.text_parts.append(b["text"])
                elif b.get("type") == "tool_use":
                    calls[b.get("id")] = {"tool": b.get("name"), "input": b.get("input") or {}}
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                call = calls[b["tool_use_id"]]
                try:
                    output = json.loads(b.get("content") or "{}")
                except (TypeError, ValueError):
                    output = {"raw": b.get("content")}
                if not isinstance(output, dict):
                    output = {"raw": output}
                state.trace.append({"tool": call["tool"], "input": call["input"], "output": output})
                if call["tool"] in tools.ACTION_TOOLS and output.get("attached"):
                    key = endorse_key(call["tool"], call["input"])
                    new = output.get("steps") or []
                    if output.get("replaces_earlier"):
                        # Replaced an earlier span live; replay the same replacement.
                        span = state.route_spans.get(key)
                        if span:
                            state.replace_steps(*span, new)
                            state.route_spans[key] = (span[0], span[0] + len(new))
                        mark_replaced(state.trace[:-1], call["input"].get("name"))
                        state.attach_keys.add(attach_key(call["tool"], call["input"]))
                        continue
                    span = state.append_steps(call["tool"], call["input"], new)
                    if call["tool"] == "open_setting":
                        state.route_spans[key] = span
    return state
