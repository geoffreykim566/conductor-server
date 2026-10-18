# research

`web_research(query)`: the executor for the `web_research` tool. It's one nested Sol call on OpenAI's Responses API with the built-in `web_search` tool (OpenAI runs the search loop inside the call) that returns `findings`, `sources`, `source_tier`, and `_usage`.

| File | What |
|---|---|
| `search.py` | The call, timeout, caps, timing logs (`[web_research_timing]`) |
| `parse.py` | Confidence line, findings text, and sources out of the response |

## How it's wired

- **The decider decides when to research.** The tool description is the only trigger. Firing it on every miss was rejected as the costlier, more eager option.
- **Research when Sol has no answer of its own is the intended fallback** (user call), so a turn that escalates to research isn't graded as a failure.
- **A function tool, not Sol's own `web_search`.** Giving the decider the built-in tool would search without asking; the nested call keeps `research_confirm` working: the turn parks for user approval before this runs (`pipeline/README.md`, Research approval).
- **Effort is low** (`config.RESEARCH_EFFORT`): the call only extracts findings; the decider turns them into the answer.
- **The HTTP call is `openai_io.post`**, so it shares the decider's retries (429 / 5xx).
- **`_usage`** is popped by `pipeline/dispatch.py`. It counts toward the turn's spend but never reaches the model.
- **The "research" tier:** a successful call earns it (`pipeline/confidence.py`), trusted like "strong". A timed-out or empty call doesn't. Sources reach the client as chips.

## Quirks & known gaps

- **Sources** come from the text's `url_citation` annotations, else the search calls' own source lists (`include: web_search_call.action.sources`), else bare URLs in the text. OpenAI tags every URL `?utm_source=openai`; it's stripped from sources and findings.
- **Results are capped** (6,000 chars of findings, 10 sources). The tool_result stays in round-tripped history, and an uncapped one 422'd every later request in that conversation.
- **Timeout is 150s** (`RESEARCH_CALL_TIMEOUT_S`, a Claude-era ceiling: 90 s timed out every real call then). There's no retry on timeout, so one slow call just fails.
- **`source_tier` is computed but unused.** The fine-grained tier (confirmed / community / genre-inference) never reaches the confidence tier. The confidence line is read plain or bold.
- **Mixed turns:** a turn with a card and research can state web-sourced specifics under a "strong" tier inherited from the card. Not fixed.
- **History:** the Claude version (Sonnet 5.5 + Anthropic's `web_search`, up to 2 `pause_turn` continuations) is in tag `archive/v042-sonnet-kb`; ported 10-18 (feature log).
