"""The reply's card: identity keys for actions, and span bookkeeping when a step is
replaced. Rules and why: README.md (One card per turn)."""
import json


def attach_key(name: str, inp: dict) -> str:
    """Exact identity of a call: tool + every argument."""
    return json.dumps([name, inp], sort_keys=True, default=str)


def endorse_key(name: str, inp: dict) -> str:
    """Identity by target only: a second open_setting for the same route is a correction
    of the first, whatever value it picks."""
    if name == "open_plugin":
        return f"open_plugin:{str(inp.get('plugin', '')).strip().lower()}"
    if name == "set_param":
        return f"set_param:{str(inp.get('plugin', '')).strip().lower()}:{str(inp.get('param', '')).strip().lower()}"
    if name == "open_setting":
        return f"open_setting:{str(inp.get('name', '')).strip().lower()}"
    return attach_key(name, inp)


def replace_span(card_steps: list, start: int, end: int, new: list, *span_maps: dict) -> None:
    """Swap card_steps[start:end] for `new` and shift every recorded span after it."""
    card_steps[start:end] = new
    shift = len(new) - (end - start)
    if shift:
        for spans in span_maps:
            for k, (a, b) in list(spans.items()):
                if a >= end:
                    spans[k] = (a + shift, b + shift)


def mark_replaced(trace: list[dict], name: str) -> None:
    """Earlier open_setting calls for this route no longer describe the card; the
    grader stops counting them."""
    for c in trace:
        if c["tool"] == "open_setting" and c["input"].get("name") == name and c["output"].get("attached"):
            c["output"] = {**c["output"], "attached": False, "replaced": True}
