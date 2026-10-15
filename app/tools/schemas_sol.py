"""Sol's tools (DECIDER=sol): the same tools minus cite_kb, descriptions without the KB, a
research bar of "no answer of your own", and `answer` / `more_actions` on the actions.
Derived from schemas.py so routes and plugin rules stay shared. Why: README.md (Sol)."""
import copy

from app.tools.schemas import ACTION_TOOLS, TOOLS


def _sub(text: str, old: str, new: str) -> str:
    # Fails at import if schemas.py's wording moved, rather than silently keeping KB text.
    assert old in text, f"schemas_sol: anchor missing: {old[:60]!r}"
    return text.replace(old, new, 1)


# Sol writes no text beside a tool call, so its reply rides on the action call (the
# adapter moves it into a text block); without it each card turn cost a second call.
ANSWER_PROP = {"type": "string", "description": (
    "Your written reply to the user, shown beside this card: what's going on and the fix, as you'd "
    "write it in your answer (for a plain command, one short line). Fill it on the first action call "
    "of a response; leave it empty on the others.")}
# Sol queues one action per response even when a request needs two, and early exit then
# dropped the second; it says when another is coming instead (respond._can_exit_early).
MORE_ACTIONS_PROP = {"type": "boolean", "description": (
    "true if the user's request needs another action you'll queue after this one's result "
    "(e.g. set a parameter on the plug-in this call adds); false if this completes it.")}
SOL_ONLY_ARGS = ("answer", "more_actions")


def _sol_tool(t: dict) -> dict:
    t = copy.deepcopy(t)
    t.pop("cache_control", None)
    d = t["description"]
    if t["name"] == "ask_clarifying_question":
        d = _sub(d, "(a KB problem with several candidate causes", "(several candidate causes")
        d = _sub(d, " If the question is about a KB problem, cite it with cite_kb in the same response.", "")
    elif t["name"] == "web_research":
        d = _sub(d, "outside this KB's coverage", "you can't answer reliably from your own Logic Pro knowledge")
        d = _sub(d, ", or anything else the knowledge base doesn't cover", "")
        d = _sub(d, "questions the knowledge base already covers -- this is for genuinely out-of-KB information",
                 "questions you can answer -- this is for information you genuinely don't have")
        d = _sub(d, "Call this instead of answering from pretrained knowledge when a question asks for "
                    "something you'd otherwise have to guess at.",
                 "Call it only when you have no answer of your own; never to confirm something you already believe.")
    elif t["name"] == "open_plugin":
        d = _sub(d, ", whether or not the KB mentions it", "")
        d = _sub(d, "; no KB entry is needed first", "")
    t["description"] = d
    if t["name"] in ACTION_TOOLS:
        s = t["input_schema"]
        s["properties"] = {**s["properties"], "answer": ANSWER_PROP, "more_actions": MORE_ACTIONS_PROP}
        s["required"] = [*s["required"], *SOL_ONLY_ARGS]
    return t


SOL_TOOLS = [_sol_tool(t) for t in TOOLS if t["name"] != "cite_kb"]
