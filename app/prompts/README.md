# prompts

The decider's system prompt: one string constant, re-exported by `__init__.py`.

| File | Constant | Used by |
|---|---|---|
| `decider.py` | `SYSTEM_PROMPT` | `pipeline/context.py`: Sol's prompt. No KB; its own grounding rules and a short "Logic facts" list |

## Quirks & why

- **It's the exact tested text** (`solj_facts2`, 10-15). The 10-17 refactor checked it byte for byte. It still lists "cite_kb", "KB" among words never to say, from the Sonnet era; harmless, left so the tested text stays identical until the next prompt change re-runs the battery anyway.
- **Prompt-only rules are requests, not guarantees.** If something must hold every time (a cap, a refusal, the undo decline), enforce it in `pipeline/` code and keep the prompt line as guidance only. Prompt-only versions have held roughly 40–50% of the time.
- **Live AX state is authoritative only for what it lists; the screenshot is evidence for the rest.** Calling AX "ground truth that outranks screenshots" made the model defer to an incomplete dump and say it couldn't see the screen.
- **Keep the prompt byte-identical across turns.** Anything per-turn goes in its own system block (`pipeline/context.py`) so the prefix still caches.
- **Plug-in settings (10-19):** a `position=` is knob travel, never a setting; when an answer depends on a value the live state doesn't give in real units, Sol calls `read_plugin_values`. From the 10-12 Compressor reply that quoted raw slider numbers and read Attack off the knob image.
- **Mastering Assistant (v043):** a plug-in in its own Stereo Out slot, so Sol uses `open_plugin` / `set_param` / `read_plugin_values` for it rather than a route. The prompt says how the live state shows the empty slot (`AXButton 'mastering assistant'`) versus the loaded one, since the empty button's name reads like it's on.
- **Stem Splitter (v043):** the `stem splitter` route. Sol passes `target` when the user names or points to a region (live 10-23: without it the card made the user select SICKO MODE although they'd named it), `value` only for named stems, and asks which region when several exist and none is named or selected. It says Apply is the user's step.
- **Logic facts:** add one when a miss repeats, worded as a plain fact, not a symptom match.

## Changing a prompt

Edit, rebuild, then run the full battery and read the answers, not just the pass count. Prompt changes move unrelated scenarios.
