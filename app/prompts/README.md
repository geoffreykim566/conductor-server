# prompts

The decider's system prompt and the Explain block, re-exported by `__init__.py`.

| File | Constant | Used by |
|---|---|---|
| `decider.py` | `SYSTEM_PROMPT` | `pipeline/context.py`: Sol's prompt. No KB; its own grounding rules and a short "Logic facts" list |
| `explain.py` | `EXPLAIN_BLOCK` | `pipeline/context.py`: its own system block after the prompt, only when the client's Explain toggle is on |

## Quirks & why

- **It's the tested text:** `solj_facts2` (10-15) plus the 10-24 teaching edits, each run through the battery. It still lists "cite_kb", "KB" among words never to say, from the Sonnet era; harmless, drop them in a prompt change that re-runs the battery anyway.
- **Teaching is in scope (10-24).** The scope line names explaining concepts and how to use Logic's tools, and conceptual questions ("what is a compressor") get more length than how-tos ("how do I open it"). From prod 10-18: the old three-item scope line plus "don't explain the theory" made Sol turn a day-one beginner away. Side effect: Sol asks more before acting on a loose option name ("smart tempo to beats").
- **Prompt-only rules are requests, not guarantees.** If something must hold every time (a cap, a refusal, the undo decline), enforce it in `pipeline/` code and keep the prompt line as guidance only. Prompt-only versions have held roughly 40–50% of the time.
- **Live AX state is authoritative only for what it lists; the screenshot is evidence for the rest.** Calling AX "ground truth that outranks screenshots" made the model defer to an incomplete dump and say it couldn't see the screen.
- **Keep the prompt byte-identical across turns.** Anything per-turn goes in its own system block (`pipeline/context.py`) so the prefix still caches.
- **Plug-in settings (10-19):** a `position=` is knob travel, never a setting; when an answer depends on a value the live state doesn't give in real units, Sol calls `read_plugin_values`. From the 10-12 Compressor reply that quoted raw slider numbers and read Attack off the knob image.
- **Mastering Assistant (v043):** a plug-in in its own Stereo Out slot, so Sol uses `open_plugin` / `set_param` / `read_plugin_values` for it rather than a route. The prompt says how the live state shows the empty slot (`AXButton 'mastering assistant'`) versus the loaded one, since the empty button's name reads like it's on.
- **Stem Splitter (v043):** the `stem splitter` route. Sol passes `target` when the user names or points to a region (live 10-23: without it the card made the user select SICKO MODE although they'd named it), `value` only for named stems, and asks which region when several exist and none is named or selected. It says Apply is the user's step.
- **Format and length (rewritten 11-06, user call):** a card already shows its steps and a Run button, so a card reply says what the action does for the user ("cuts the delay between singing and hearing yourself"), not the steps or "this turns on X". Numbered steps only when nothing is queued. One plain-words paragraph for everyone: standard terms, never a phrase of Sol's own ("backing loop", a friend's confusion). The old "lead with the action" line went; its no-preamble half stayed.
- **How-to questions with a card (11-06, user call):** queue it, then give the manual way in one line and a line on what it does. The manual way comes only from a route's path or the Logic facts (the plug-in fact: Audio FX slot first, since that's how most people add one, then Control-Command-P search). Sol still added "Dynamics > Compressor" from memory in some runs; the category goes in the fact once confirmed in Logic.
- **Partial cards:** when the card covers only part of the request, the rest goes in the reply as numbered steps, and only what the user can do now is queued. Sol had written "follow the steps below" and stopped, and once queued the Bounce dialog before anything was recorded.
- **Loose plug-in names:** "put valhalla on the vocal" queues the likeliest Valhalla and names it. After the card-reply rewrite Sol asked which one 4/5 (Explain off) vs 0/5 on `main`; with the line, 10/10 queued.
- **Explain is a separate block, not a second prompt (11-06).** On asks Sol to weave in a brief plain explanation of technical terms and, when something is still assumed, end with a one-line offer naming it. Two full prompt versions (Explain/brief) were tried first and read nearly the same; the base prompt stays byte-identical either way, so both settings cache. Glossary terms are underlined in both modes (`pipeline/README.md`, Glossary); they're not shown inline in Explain, where Sol's own sentence would define the word twice.
- **Logic facts:** add one when a miss repeats, worded as a plain fact, not a symptom match.

## Changing a prompt

Edit, rebuild, then run the full battery and read the answers, not just the pass count. Prompt changes move unrelated scenarios.
