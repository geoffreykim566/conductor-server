"""Approved navigation routes, loaded once from seed/routes.json at import (rebuild after
editing it). The model only ever names a route; the path that runs is always the file's.
Route format: README.md."""
import json
from pathlib import Path

# routes.json is the only place a menu path lives. Runnable routes go to open_setting;
# `reference` entries can't run (outside Logic, or never given steps) -- shown to the
# model as locations it may state, never queued.
ALL_ROUTES: dict[str, dict] = json.loads((Path(__file__).parents[2] / "seed" / "routes.json").read_text())
ROUTES: dict[str, dict] = {n: r for n, r in ALL_ROUTES.items() if not r.get("reference")}
REFERENCES: dict[str, dict] = {n: r for n, r in ALL_ROUTES.items() if r.get("reference")}

# Values an ordered dropdown route accepts besides its listed options.
RELATIVE_VALUES = ("larger", "smaller")


def _step_text(step: dict) -> str:
    value = step.get("value")
    if step.get("type") == "context_menu":
        return f"Control-click the {step.get('on') or 'region'} > " + " > ".join(value)
    if isinstance(value, list):  # anchors: whichever of these labels is showing
        return f"the control showing its current option (e.g. '{value[0]}')"
    if step.get("type") == "shortcut":
        return f"press {value}"
    if step.get("type") in ("click_text", "click_value_of"):
        return f"'{value}'"
    return str(value)


def route_path_text(name: str) -> str:
    """A route's path as the model may state it: its menus joined by " > ", then
    shortcuts / clicks, plus any display-only `also` alternative. A reference
    entry's text as written."""
    route = ALL_ROUTES[name]
    if route.get("reference"):
        return route["text"]
    parts: list[str] = []
    for step in route.get("path") or []:
        text = _step_text(step)
        if step.get("type") == "menu" and parts and not parts[-1].startswith(("press ", "'")):
            parts[-1] += " > " + text
        else:
            parts.append(text)
    out = ", then ".join(parts)
    if route.get("also"):
        out += f" (also {route['also']})"
    return out


def route_line(name: str, route: dict) -> str:
    line = f"- {name}: {route['desc']} -- {route_path_text(name)}"
    if route.get("toggle"):
        line += " [toggle: pass state on/off for what the user wants it to end as]"
    on = next((st.get("on") or "region" for st in route.get("path") or [] if st.get("type") == "context_menu"), None)
    if on:
        line += f" [target: {on} -- pass its name when the user names or points to one]"
    checks = route.get("checks")
    if checks:
        line += (f" [value: the ones the user asked for, comma-separated, from {' | '.join(checks['options'])}"
                 " -- only those are ticked; omit to open it as it is]")
    choice = route.get("choice")
    if choice is None:
        return line
    options = choice.get("options") or []
    if not options:
        return line + " [opens the pane only; no value]"
    values = " | ".join(options) + (" | larger | smaller" if choice.get("ordered") else "")
    free = choice.get("model_may_pick") or []
    if free == options:
        who = "you may choose any of these yourself"
    elif free:
        who = f"you may choose {' or '.join(free)} yourself; any other value only if the user named it"
    else:
        who = "an exact value only if the user named it"
    if choice.get("ordered"):
        who += "; larger/smaller move one step from its current value"
    return line + f" [value: {values} -- {who}]"
