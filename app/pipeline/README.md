# pipeline

One turn of conversation. `respond(messages, ...)` takes the full history ending in the new user message and returns a `Result`: the reply text, the card's steps, the trace of tool calls, and the new history for the client to send back next turn. Nothing is stored server-side; history is the only state.

## Files

| File | What |
|---|---|
| `respond.py` | The turn loop (`run_turn`) and the auto-run decision (`respond`) |
| `dispatch.py` | Runs one tool call against the card: duplicate, re-visited setting and cap rules |
| `executors.py` | Tool name -> executor; status line while a tool runs |
| `turn_state.py` | `TurnState` (trace, card steps, spans, turn text) and rebuilding it on resume |
| `cards.py` | Action identity keys and span bookkeeping |
| `context.py` | System prompt, live-state block, screenshot splice |
| `reply.py` | The reply: Sol's text, the undo decline, a tool-only question appended; streams it |
| `heuristics.py` | Reads of the user's own text: question? undo? greeting/closer? a go-ahead after a card? |
| `backfill.py` | Re-shows an earlier card on "show me that again" |
| `confidence.py` | Confidence tier from the trace; research sources |
| `model_io.py` | The only decider call site; response blocks -> request-shape dicts |
| `openai_io.py` | The Sol decider on OpenAI's Responses API, translated to and from the pipeline's blocks |
| `transcript.py` | Turn boundary and pending tool calls in a message list |
| `settings.py` | Tunables (`MAX_ITERATIONS`, decider effort, early exit, ...) |
| `notes.py` | Fixed text: refusals and nudges for the decider, the undo decline for the user |
| `result.py` | `Result` dataclass |

## How a turn flows

1. **Context.** The system prompt (`prompts/decider.py`) plus a live-state block (the client's AX dump, or the battery's `ax_fixture`). The screenshots are spliced into this turn's user message for each call only.
2. **Decider loop** (≤ `MAX_ITERATIONS`). Sol (`config.SOL_MODEL`, effort `settings.DECIDER_EFFORT`) is called with its tools. It answers and calls actions; its reply rides on the first action call's `answer` argument.
   - The first call is unforced, except for a go-ahead after a card (Forced first call, below).
   - Each tool call goes through `dispatch.handle_tool_use`, which updates the card.
   - Every iteration's text is kept (Turn text, below).
3. **The turn ends** when Sol stops calling tools, an iteration qualifies for early exit, Sol calls `ask_clarifying_question`, or it runs out of iterations. Running out gets one tools-off "answer now" call, so a turn is never empty.
4. **Reply.** `reply.finalize_reply`: Sol's text, as written.
5. **Auto-run.** `respond` decides whether the card may run without the user pressing Run.

## Conventions

- **Read tunables as `settings.X` at call time**, never `from app.pipeline.settings import X`. Tests patch them on the module.
- **Call the decider only through `model_io.call_model`**, by module attribute. Tests patch `model_io.call_model` (the `run` fixture) or `openai_io._client.post` (the Responses translation).
- **Executors are looked up in `executors.EXECUTORS`** (tests `patch.dict` it). `research` and `tools` are reached as module attributes for the same reason.
- **Code decides, prompts don't.** Anything that has to hold every time is enforced here, not requested in a prompt: auto-run, the undo decline, the turn-text rules, the confidence tier. Prompt-only versions of rules like these held ~40–50% of the time.

## Quirks & why

### Sol decider
- **Why Sol, with no KB.** The KB-strict Sonnet prompt missed general troubleshooting (hidden main window; ChatGPT and Gemini answered it at once). In the 10-12 to 10-15 A/B, GPT-6.1 Sol answering from its own Logic knowledge matched Opus + KB on the core battery, made fewer wrong UI claims (0% vs 8%), ran faster (median 6.1 s vs 6.9 s) at a third of the cost, and won the user's blind read on concision. Details: `diagnosis-log.md` (archived with the logs).
- **No fallback model (user call, 10-17).** The Sonnet decider, its KB and the Haiku writer were removed rather than kept as a rollback: keeping a second path working wasn't worth its upkeep. The old path is tag `archive/v042-sonnet-kb`; the KB content is in `~/Desktop/OLD Conductor/kb-2026-10-17/`. An OpenAI outage is an error to handle, not a reason to switch models (open item in the feature log).
- **What grounds it:** the approved routes (`open_setting`; every card's path comes from `seed/routes.json`), a short "Logic facts" list in its prompt for things it got wrong unaided, and `web_research` only when it has no answer of its own. Add a fact when a miss repeats; keep each one worded as a plain fact, not a symptom match.
- **The prompt and tools are the exact tested text.** Edit them directly and re-run the battery. The prompt still lists "cite_kb", "KB" among words never to say: harmless, left so the tested text stays byte-identical.
- **Responses API, not Chat Completions:** OpenAI doesn't support function calling with Sol on Chat Completions. `store` is off; Sol's encrypted reasoning items are replayed within a turn (OpenAI recommends it) but never enter history.
- **`answer` arg on the action tools:** Sol never writes text beside a tool call, so a card turn ended with no explanation, and asking for it took a second call (~5 s). The reply now rides on the first action call and the adapter turns it into the text block. Written text wins if Sol writes both (logged as `[sol_answer_dropped]`; an unconfirmed cause of a 10-15 reply that lost its steps).
- **`remaining_actions` arg:** Sol queues one action per response even when a request needs several (an explicit `parallel_tool_calls` didn't change that), and early exit then dropped the rest ("add a compressor at -18" lost the threshold). A yes/no "more coming" flag still lost the last of three live ("compressor and eq with low cut" lost the low cut 2/3); listing what's left makes Sol plan, and the turn continues while the list is non-empty (`more_actions` on the response, `TurnState.more_actions`). 10/10 after.
- **Sol sees its own calls as it made them.** The adapter strips `answer` / `remaining_actions` before anything runs, but replays them (and the response's reasoning) into the turn's later calls from a per-turn stash, so Sol still sees its plan. Text synthesized from `answer` is replayed as Sol's own message, with `answer` left out of the call: seeing its reply only inside the call, Sol wrote the whole reply again on a follow-up call (the `ask_options` one), and both copies were kept (9/96 core turns, 10-16). A note telling it the reply was already shown changed nothing.
- **Empty args are dropped** (Sol sends `value: ""` for an omitted optional one, which the dropdown routes refused), and **malformed tool JSON is retried** like a 429 (Sol once sent truncated arguments). `[sol_text]` logs Sol's text per call.

### Reply (`reply.finalize_reply`)
- **No writer model.** A Haiku writer used to reword the decider's text, because Sonnet leaked its own machinery into replies. Sol doesn't. In the 10-17 A/B on identical Sol text (118 turns), no writer dropped and invented nothing and saved ~1 s; Haiku 4.5 cut 9 replies well below Sol's text (steps, questions) and invented 2 picks; Haiku 5.5 with a keep-the-steps card block kept content but recited the card rule on ~25 turns. Run outputs: `test_runs/2026-10-17/wab_*`.
- **What the writer did that code now does:** the undo decline (`notes.UNDO_DECLINE`, whatever Sol wrote; typed undo is denied for now, the card's Revert button does it), and a question asked only through `ask_clarifying_question` reaching the user (appended unless the text already holds it). It also used to hide Sol's duplicate and refused-call text (Turn text, below).
- The reply goes to the client as a single chunk event, since Sol's call doesn't stream (the writer used to stream token by token). Check it renders the same in the live pass.

### One card per turn
- Every action is a step on the same card, in call order. The card holds at most `MAX_ATTACHES_PER_TURN` steps.
- **Duplicates** (same tool + args) are refused: the step runs once.
- **Re-visited setting:** a second `open_setting` for the same route replaces the first. The later call is the correction the prose follows.

### Forced first call (`heuristics.force_first_call`)
- **Normally the first call is unforced.** Forcing a tool makes the API suppress text before the call.
- **The one forced case** is a go-ahead after a reply that queued a card ("yes please, do it"). Unforced, it got "press Run" about the earlier card.
- **Exemptions:**
  - Re-asks (forcing would starve backfill).
  - Closers like "thanks".
  - Whole-project destructive requests (declined with no tool call).
  - Bare greetings, matched against the whole message because "hi" is inside "this".
  - Anything question-shaped.
- **`FORCED_TOOL_CHOICE` is None** (Sonnet rejected a forced choice with a 400; unmeasured with Sol).
- **The `TOOL_NUDGE` re-ask is off** (`RETRY_NO_TOOL_FIRST_CALL`, 10-18). It was Sonnet's stand-in for forcing: a go-ahead answered with no tool was asked again, and the second call's text replaced the first. With Sol the trigger catches far more than go-aheads (any non-question after a card: "now what", "i hit R but its just blinking"), and in the 10-18 live pass the re-ask replaced a real reply 3/3 times: steps dropped ("…follow these steps" with none), an explanation reduced to a clarifying question. With both knobs off, `force_first_call` has no effect; it stays for a model that accepts a forced choice.

### Early exit (`respond._can_exit_early`)
- **The rule:** an iteration whose calls were all accepted actions ends the turn, without the prose-only follow-up call (~2.5 s). Direct commands drop from ~5 s to ~2.5–3 s.
- **Exceptions that keep looping:**
  - Any refusal or error, so the decider can react.
  - Sol's `remaining_actions` not yet empty.
  - A pane-only dropdown whose options the text doesn't name (`ask_options`): Sol writes its answer before seeing the "ask which one" note, so without the follow-up the reply never named them and "the last one" next turn picked Off.

### Turn text (`TurnState.add_text`)
Every iteration's text is kept, with two exceptions found when Sol's text went to the user unrewritten (10-17; Haiku had hidden both):
- **A follow-up's restatement replaces the earlier copy.** On the `ask_options` follow-up Sol sometimes rewrote its whole reply, word for word or reworded (4 of 10 sample-rate turns after the replay fix). Only text from a call with no tool call counts as a follow-up: two different action lines ("Press Run to load Compressor…" / "…open Channel EQ…") scored as alike (0.77) as a reworded restatement (0.64), so text beside actions is never merged.
- **Text beside calls that were all refused gives way to the next call's text.** Sol guessed a dropdown value ("Flex On, Smart Tempo Off"), wrote "Press Run to set …", was refused, then opened the pane and asked; both sentences reached the user (4 times in ~25 dropdown turns). If nothing follows, the text stays, so the turn is never empty.

History keeps both copies; only the reply drops them.

### Tunables
- `DECIDER_EFFORT` is medium: the same graded quality as high, ~1 s faster median, ~7% cheaper. Low was no faster and failed more.

### Heuristics phrase lists
- They're hand-curated and deliberately narrow.
- Bare "again" and "forgot" are excluded ("thanks again, that fixed it").
- "cant find it" was removed after it matched 7 battery turns.
- The destructive list is project-scoped only, because "delete everything on this track" is undo-able.
- **`offered_text` also reads `ask_clarifying_question`'s question.** A question asked only through the tool offers options too; without it, "yes" after "do you mean On + Align Bars and Beats?" named nothing and the value was refused.
- **Undo requests are declined in code** (`is_undo_request`, skipped when question-shaped). A prompt line alone let a reply say "press Command-Z" (wrong for settings, which aren't in Logic's Undo), and a broader rule also denied "how do i undo a cut".
- **Re-sweep the full battery after changing any list.** Checking only the scenario you were fixing has given false confidence more than once.

### Auto-run (`respond.respond`)
A card runs without Run only when all of these hold:
- the user's message is a direct instruction (not question-shaped, not bulk);
- the card isn't a re-shown one (backfill);
- no route on the card has `wait_for_run`.

The KB era also held back any card a citation led to (a "bypass control surfaces" card off a moderate match once auto-ran on a turn whose own reply said "I don't have a verified fix"). That guard went with the citations, so a symptom phrased as a command ("my vocal sounds muddy, fix it") auto-runs the fix Sol picks when the client's auto-run setting is on. That's on purpose (user call 10-19): "fix it" is a direct command and Revert undoes the card. A word-match hold was tried and dropped: it needed a hand-kept list of words too common to name a route ("sound", "time", "rate") and still misjudged cases ("mic" vs "microphone access").

There's deliberately no user-facing explain/do mode toggle (user call): the decider picks per turn, and the Run press stays the floor for anything the rules above don't clear.

### Confidence tier
Computed from the trace, deterministically: a clarifying question -> generic; a card -> strong; successful research -> research; otherwise generic. The moderate tier came from KB citations and went with them. The client badge is disabled (see `app/api/README.md`); the tier is still recorded in events and used by the battery.

### Backfill
If the user asks to see something again and the model answers from memory with no tool call, the earlier route is re-attached. It's gated on re-ask language in the *user's* message: matching the destination name in the reply misfired when a topic recurred for other reasons. Zero or several candidates are left alone. Hostile phrasings are covered in `tests/pipeline/test_backfill.py`.

### Context & caching
- **Live state is its own system block** after the static prompt, so the prompt prefix stays identical across turns. OpenAI caches the prefix automatically (`prompt_cache_key` groups the calls); no breakpoints are set.
- **Screenshots only ever go on the per-call copy** (`TurnContext.for_call`), never into `msgs`. `msgs` is the next turn's history, and the history validator rejects images there.

### History round-trip
- `model_io.serialize_content` turns response blocks into plain dicts for history.
- **History is the decider's transcript**, so the next turn (including the offered-option check, `heuristics.offered_text`) reads what Sol wrote. It keeps the duplicate and refused-call text the reply drops.

### Research approval
- With `research_confirm`, a `web_research` call parks the turn *before any tool in that batch runs*. The client then resumes with the whole batch, so every `tool_use` gets exactly one `tool_result`.
- On resume, `turn_state.restore_turn_state` replays the parked tail, so an earlier attach survives.
- On deny, the call gets `RESEARCH_DECLINED` in place of a result.

### Plug-in reads
- `read_plugin_values` is offered only when the request says `plugin_reads` (v0.4.2+). v0.4.1 can't answer a park, so it never sees the tool.
- A read call **always parks** (`Result.pending_plugin_read`), before any tool in its batch runs, like research. There's no server executor: the client opens the plug-in, reads its Controls view and resumes with `allow_plugin_read` + `plugin_values`, which become the call's `tool_result`. `deny_plugin_read` answers it, and any later read that turn, with `PLUGIN_READ_DECLINED`.
- Each read asks: a second read in the same turn (another plug-in) parks again. Research approval is per turn; a read opens a window in the user's session, so it's per read.
- The client asks "Conductor wants to open X to read its values." and skips the ask when auto-run is on (user call, 10-19).

## Adding things

- **A tool:** add its schema and executor in `app/tools/`, register it in `executors.EXECUTORS`, and add a status line if it's slow. If it queues steps, add it to `tools.ACTION_TOOLS` plus an `endorse_key` case.
- **A rule about the user's message:** add it to `heuristics.py` with a unit test, then sweep the battery.
- **A tunable:** add it to `settings.py` and read it as `settings.X`.
