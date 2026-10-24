"""Converts a solution's raw path (menu/shortcut/click steps) into client-executable
walkthrough steps. Ported as-is from the real server's router.py::_path_to_walkthrough_steps()
— pure function, no dependencies on anything v1-specific, logic unchanged."""


def path_to_walkthrough_steps(path: list) -> list | None:
    """Convert a raw path into walkthrough step dicts for the client, preserving order.

    Consecutive "menu" steps (top menu bar items) collapse into one menu_path chain,
    since the client locates those together via menu-bar OCR. "click_text"/"click_value_of"
    steps are on-screen controls and stay one-per-step, since each needs its own locate
    call. "shortcut" steps are always their own step, and so is "context_menu"
    (a target's Control-click menu: `on` names the target, `or` an alternative path).
    """
    if not path:
        return None
    steps: list = []
    menu_buf: list = []

    def flush_menu() -> None:
        if menu_buf:
            steps.append({"menu_path": list(menu_buf)})
            menu_buf.clear()

    for step in path:
        if not isinstance(step, dict):
            continue
        stype = step.get("type", "")
        val = step.get("value", "")
        if not val:
            continue
        if stype == "menu":
            menu_buf.append(val)
        elif stype == "shortcut":
            flush_menu()
            steps.append({"shortcut": val})
        elif stype == "click_value_of":
            flush_menu()
            steps.append({"click_value_of": val})
        elif stype == "click_text":
            flush_menu()
            steps.append({"click_text": val})
        elif stype == "context_menu":
            # a target's Control-click menu, opened through AX; `or` is a second path
            # in the same menu, `opens` the sheet that proves it worked
            flush_menu()
            wire = {"context_menu": list(val), "on": step.get("on") or "region"}
            if step.get("or"):
                wire["or"] = list(step["or"])
            if step.get("opens"):
                wire["opens"] = step["opens"]
            steps.append(wire)
    flush_menu()
    return steps or None
