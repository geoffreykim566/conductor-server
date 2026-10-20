# tools

The decider's tools: their schemas (`TOOLS`) and executors. There are two kinds:

- **Knowledge:** `web_research` (executor in `app/research/`), `read_plugin_values` (the client reads the plug-in; offered only to a client that sends `plugin_reads`) and `ask_clarifying_question` (carries the question).
- **Actions:** `open_plugin`, `set_param`, `open_setting`. These don't *do* anything server-side. They validate and emit wire steps that the client runs when the user presses Run.

## Files

| File | What |
|---|---|
| `schemas.py` | The six tool definitions sent to Sol, with `answer` / `remaining_actions` on the actions (why: `pipeline/README.md`, Sol decider); `TOOLS`, `ACTION_TOOLS`, `SOL_ONLY_ARGS` |
| `actions.py` | Executors for the three action tools |
| `choices.py` | Dropdown routes: match a value to an option, check the user named it |
| `routes.py` | Loads `seed/routes.json`: runnable `ROUTES`, `REFERENCES`; a route's path as text and how it's described to the model |
| `route_steps.py` | A route's `path` -> client wire steps (menu chains, shortcuts, clicks) |
| `turn_text.py` | ContextVars holding this turn's user text and the reply it answers |

## Wire steps the client runs

`{"ax_open_plugin": name, "track"?, "new"?}`, `{"ax_set_param": {plugin, param, value, track?}}`, `{"menu_path": [...]}`, `{"shortcut": "Cmd+F"}`, `{"click_text": ...}`, `{"click_value_of": label}`, `{"choose": option, "reopen": [steps], "shows"?}`. Any step may carry `expect`. The client's executor is in `client/core/automation/`. Changing a shape here means changing it there too.

## Quirks & why

- **Actions are typed tools.** When they were KB rows ("open plugin" behind the old vector lookup), the model had to find them first, and their names collided with plugin vocabulary ("plugin manager", "multipressor").
- **`set_param.value` is a string**, parsed server-side (`_parse_param_value`). A number-or-on/off union wasn't held by the model even under strict mode.
- **Routes are the only way to navigate.** The model names a route; the path that runs is always `seed/routes.json`'s. Model-written menu paths have been confidently wrong more than anything else in this codebase.
- **`ask_clarifying_question` requires the question text.** Called with no text, the old writer had nothing to phrase and invented an answer; now the question is the reply (`pipeline/reply.py`).
- **open_setting's description lists each route's path, plus the reference locations** the model may state but not queue.
- **`read_plugin_values` is for answers, not edits.** Sol calls it when its answer depends on a setting the live state shows only as knob travel (`position=N%`) or not at all (window closed). Edits don't need it: a named value is queued as is. A call always parks the turn (only the client can read); see `pipeline/README.md`, Plug-in reads. Battery 10-19: 30/30 on the targeted `pv_*` scenarios.
- **No MCP.** One client and one server, both ours: it would add per-call overhead for no interop benefit.
- **The toggle gate:** a route with `toggle_ax_key` is refused when live state says it's already in its target state, because running it would flip it *away*.

### Dropdown routes (`choice` block in routes.json)
- `options` lists the dropdown's values. An empty list means not verified yet: the route opens the pane only.
- `ordered` allows `larger` / `smaller`.
- `model_may_pick` lists the values the model may choose on its own. **Any other value must appear in the user's message, or in the reply they're answering** (`TURN_OFFERED_TEXT`), checked in `choices.resolve_choice`.
- `shows` maps an option to the shorter text the control displays, for the client's read-back.
- A dropdown route either picks a value (`choose` step) or stops at the pane. It **never leaves a menu open**: an open menu swallowed the next step's keystrokes.
- **Pane-only routes:** the dropped dropdown row becomes the previous step's `expect`. The client then skips the menu or disclosure click when the row is already showing.
- **`picks`:** a route fixed to one option ("flex pitch") ends on a `choose` step, not a click. The client closes stray menus before every step except a choose, and a choose ledgers the old value for Revert.
- **`wait_for_run`:** the route's target depends on the user's selection, so its card never auto-runs.
- An ambiguous value ("flex on" fits four options) is refused with the list, so the reply asks which one.
- **The ask note quotes each option** (`pane_only_ask`): options hold commas ("Flex On, Smart Tempo On"), and a `|`-separated list came out of the old writer as wrong, mangled options.
- **Offered options count as the user's pick** (user call: users shouldn't have to type option names). It's a word match on the previous decider text, including a question asked only through `ask_clarifying_question`, so any option it mentioned is allowed; a first turn has none.
- **`_user_named` compares letters and digits only** (no punctuation needed) and reads "smart tempo" as Logic's "ST" abbreviation.
- **`processing threads` has `model_may_pick: []`:** the fix is max threads, not "Automatic", and the client can't pick a number, so the card stops at the pane.
- **Sol may pick any option on every dropdown except processing threads** (user call 10-19). The narrow lists were a guard on the Claude decider, set to the KB's fixes; with Revert on every pick, a card that stops at the pane costs more than a wrong pick. Buffer takes an exact size as well as larger/smaller: switching between recording (64–128) and mixing (512–1024) is more than one step.

## Adding things

- **A route:** add it to `seed/routes.json` (`desc`, `path`, optional `choice` / `picks` / `wait_for_run` / `toggle_ax_key`). Verify the path live in Logic first. Rebuild (it's read at import).
- **A new action tool:** schema in `schemas.py` + `ACTION_TOOLS`, executor in `actions.py`, then the pipeline side (`app/pipeline/README.md`, Adding things), then the client executor.
