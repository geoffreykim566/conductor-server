"""The tool definitions sent to the decider (Sol). What each tool is for, why the action
tools are typed tools, and why they carry `answer` / `remaining_actions`: README.md."""
from app.tools.routes import REFERENCES, ROUTES, route_line, route_path_text

# Sol writes no text beside a tool call, so its reply rides on the action call (the
# adapter moves it into a text block); without it each card turn cost a second call.
ANSWER_PROP = {"type": "string", "description": (
    "Your written reply to the user, shown beside this card: what's going on and the fix, as you'd "
    "write it in your answer (for a plain command, one short line). Fill it on the first action call "
    "of a response; leave it empty on the others.")}
# Sol queues one action per response even when a request needs several. A yes/no "more
# coming" flag still lost the last one (the low cut in "compressor and eq with low cut", 2/3);
# listing what's left makes it plan, and the turn continues until the list is empty.
REMAINING_ACTIONS_PROP = {"type": "array", "items": {"type": "string"}, "description": (
    "Every other action the user's request still needs after this one, each as a short phrase "
    "(\"set Channel EQ Low Cut Frequency to 80\"), in the order you'll queue them. Include each "
    "one your answer promises that isn't queued yet. [] if this call completes the request.")}
# Stripped before an action runs (pipeline/openai_io.py); never part of the call's own args.
SOL_ONLY_ARGS = ("answer", "remaining_actions")


# No side effect: it makes "this turn makes no claim" a fact in the trace rather
# than something guessed from the reply text.
ASK_CLARIFYING_QUESTION_SCHEMA = {
    "name": "ask_clarifying_question",
    "description": (
        "Call this when your entire response for this turn is a clarifying question "
        "and nothing else -- no diagnosis, guidance, or claim alongside it. Marks the "
        "turn as making no claim, so it won't be hedged as an unconfirmed answer. Only "
        "for the genuine-toss-up case this prompt already describes (several candidate causes "
        "and no distinguishing evidence yet). Never call this if you're also offering "
        "any guidance, even tentative guidance, in the same response -- that response "
        "should stand as a real (possibly hedged) answer, not a claim-free question. "
        "Never call this alongside an action tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            # Required: called with no text, the writer had nothing and invented an answer.
            "question": {
                "type": "string",
                "description": "The exact clarifying question to ask the user, numbered options included.",
            }
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}

# Executor: app/research. The description is the only trigger; nothing forces a call
# (research on every miss was rejected as the costlier, more eager option).
WEB_RESEARCH_SCHEMA = {
    "name": "web_research",
    "description": (
        "Search the web for information you can't answer reliably from your own Logic Pro "
        "knowledge -- specific artist/producer techniques, gear, current Logic Pro features/changes. "
        "Call it only when you have no answer of your own; never to confirm something you already "
        "believe. Don't call it for ordinary troubleshooting or navigation questions you can "
        "answer -- this is for information you genuinely don't have, not a first resort."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused web-search query capturing exactly what needs researching.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

# The client runs the read (opens the plug-in, Controls view); the user approves it like
# research unless auto-run is on. Only for answers that depend on a value: edits don't need it.
READ_PLUGIN_VALUES_SCHEMA = {
    "name": "read_plugin_values",
    "description": (
        "Read the current settings of a plugin on a track: Conductor opens its window if needed and "
        "reads every control's value in its own unit (dB, ms, Hz, %, ratio). The user may be asked "
        "first and can decline. Call it only when your answer depends on a setting the live state "
        "doesn't list in its own unit -- it shows only position= (knob travel), or the plugin's "
        "window isn't open. Not for explaining what a control does, general advice, or queuing a "
        "change to a value the user named."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "plugin": {"type": "string", "description": "Plugin name, as for open_plugin."},
            "track": {
                "type": "string",
                "description": "Track name from the live state, only when the user names or clearly means one; omit for the selected track.",
            },
        },
        "required": ["plugin"],
        "additionalProperties": False,
    },
}

# `value` is a string parsed server-side: a number-or-on/off union wasn't held
# by the model even under strict mode.
OPEN_PLUGIN_SCHEMA = {
    "name": "open_plugin",
    "description": (
        "Queue an action that loads an audio-effect plugin onto a track by name, or opens its "
        "window if that plugin is already on the track. It runs on the user's Mac after your "
        "reply, when they press Run -- it has NOT happened when you write your reply. Works for "
        "any installed plugin, Apple or third-party. Use it for a direct request to add / put / "
        "load / open a plugin. Several action calls in one reply run in call order as one card."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "plugin": {
                "type": "string",
                "description": "Plugin name as Logic lists it (Channel EQ, Compressor, Space Designer, Phat FX, ValhallaSupermassive).",
            },
            "track": {
                "type": "string",
                "description": "Track name from the live state, only when the user names or clearly means one; omit for the selected track.",
            },
            "new_instance": {
                "type": "boolean",
                "description": "true only when the user clearly wants a second copy of a plugin that's already on the track.",
            },
        },
        "required": ["plugin"],
        "additionalProperties": False,
    },
}

SET_PARAM_SCHEMA = {
    "name": "set_param",
    "description": (
        "Queue an action that sets one control of a plugin on a track to an exact value. It runs "
        "on the user's Mac after your reply, when they press Run -- it has NOT happened when you "
        "write your reply. The plugin must be on the track: if the live state doesn't show it, "
        "call open_plugin for it first in the same reply. Setting a value on a band that's "
        "switched off (an EQ's Low Cut, say) switches the band on as part of the same action -- "
        "no separate call or question needed."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "plugin": {"type": "string", "description": "Plugin name, as for open_plugin."},
            "param": {
                "type": "string",
                "description": ("The control's label as the plugin shows it (Low Cut Frequency, Threshold, Ratio, "
                                "Mix), or \"Bypass\" for the whole plugin's power switch: value \"on\" bypasses "
                                "(turns the plugin off), \"off\" turns it back on."),
            },
            "value": {
                "type": "string",
                "description": ("A plain number in the control's displayed unit (\"80\", \"-18\", \"4\"); a "
                                "signed change from its current setting (\"by -3\", \"by +2\"), applied to "
                                "whatever it's set to when the card runs; or \"on\" / \"off\" for a switch."),
            },
            "track": {
                "type": "string",
                "description": "Track name from the live state, only when the user names or clearly means one; omit for the selected track.",
            },
        },
        "required": ["plugin", "param", "value"],
        "additionalProperties": False,
    },
}

OPEN_SETTING_SCHEMA = {
    "name": "open_setting",
    "description": (
        "Queue an action that takes the user to a Logic Pro setting, window or feature by one of "
        "the approved routes below -- the route's verified steps run on the user's Mac after your "
        "reply, when they press Run (it has NOT happened when you write your reply). Use it for a "
        "direct request to open or go to one of these; name must be one of the routes listed. If "
        "what the user wants isn't listed, don't pick the nearest one -- say you don't have a "
        "verified route for it. A route marked [value: ...] ends on a dropdown: pass value to "
        "choose one of its options, or omit it to open the pane with the current value showing "
        "and let the user pick.\n\nRoutes:\n"
        + "\n".join(route_line(name, route) for name, route in sorted(ROUTES.items()))
        + "\n\nVerified locations you may state but NOT pass to open_setting (no runnable steps; "
        "say where it is and let the user do it):\n"
        + "\n".join(f"- {name}: {route_path_text(name)}" for name in sorted(REFERENCES))
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": sorted(ROUTES), "description": "One of the approved routes."},
            "value": {
                "type": "string",
                "description": "Only for a route marked [value: ...]: one of its listed options, or "
                               "larger / smaller where listed. Omit to just open the pane.",
            },
            "state": {
                "type": "string",
                "enum": ["on", "off"],
                "description": "Only for a route marked [toggle]: on or off, what the user wants it to "
                               "end as. It's left alone if it's already there; omit only when the "
                               "user just wants it flipped.",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    },
}

ACTION_TOOLS = {"open_plugin", "set_param", "open_setting"}
for _t in (OPEN_PLUGIN_SCHEMA, SET_PARAM_SCHEMA, OPEN_SETTING_SCHEMA):
    _s = _t["input_schema"]
    _s["properties"] = {**_s["properties"], "answer": ANSWER_PROP, "remaining_actions": REMAINING_ACTIONS_PROP}
    _s["required"] = [*_s["required"], *SOL_ONLY_ARGS]

TOOLS = [ASK_CLARIFYING_QUESTION_SCHEMA, WEB_RESEARCH_SCHEMA, READ_PLUGIN_VALUES_SCHEMA,
         OPEN_PLUGIN_SCHEMA, SET_PARAM_SCHEMA, OPEN_SETTING_SCHEMA]
