"""The decider call when DECIDER=sol: GPT-6.1 Sol on OpenAI's Responses API. Translates the
Anthropic-shaped request (system blocks, messages, tools) to Responses input items and the
reply back into Anthropic-shaped blocks, so respond.py and the history format are unchanged.
Why Responses, the Sol-only args and the stash: README.md (Sol decider)."""
import asyncio
import contextvars
import json
import logging
import time
from types import SimpleNamespace

import httpx

from app.core import config
from app.pipeline import settings
from app.pipeline.transcript import last_user_text_index
from app.tools.schemas_sol import SOL_ONLY_ARGS, SOL_TOOLS

log = logging.getLogger(__name__)

URL = "https://api.openai.com/v1/responses"
RETRY_DELAYS_S = (1, 2, 4, 8)
_client = httpx.AsyncClient(timeout=180)  # tests patch _client.post

# What this turn's earlier calls carried that history doesn't, keyed by call_id: the Sol-only
# args stripped before execution ("args"), and on a response's first call its encrypted
# reasoning items and the text synthesized from `answer` ("synth_text"). Replayed so Sol sees
# its own calls as it made them, plan included; OpenAI recommends replaying reasoning. Never
# in history: the client round-trips history, and only this turn's entries are kept.
_STASH: contextvars.ContextVar[dict | None] = contextvars.ContextVar("sol_stash", default=None)


class Retryable(Exception):
    pass


def _tools(ts: list[dict]) -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": t["input_schema"], "strict": False} for t in ts]


def _tool_choice(tc: dict | None):
    if tc is None:
        return "auto"
    return {"any": "required", "none": "none", "auto": "auto"}.get(tc.get("type")) or {
        "type": "function", "name": tc["name"]}


def _input(system: list[dict], msgs: list[dict], stash: dict) -> tuple[str, list[dict]]:
    """Static prompt -> instructions; later system blocks (live state, nudges) -> developer
    messages ahead of the history, so the instructions + tools prefix stays cacheable."""
    instructions = system[0]["text"]
    items = [{"role": "developer", "content": b["text"]} for b in system[1:] if b.get("text")]
    for m in msgs:
        c = m["content"]
        if isinstance(c, str):
            items.append({"role": m["role"], "content": c})
            continue
        if m["role"] == "assistant":
            text = "".join(b["text"] for b in c if b["type"] == "text")
            calls = [b for b in c if b["type"] == "tool_use"]
            first = stash.get(calls[0]["id"], {}) if calls else {}
            if text and text != first.get("synth_text"):  # synthesized text is already in `answer`
                items.append({"role": "assistant", "content": text})
            items += first.get("reasoning", [])
            items += [{"type": "function_call", "call_id": b["id"], "name": b["name"],
                       "arguments": json.dumps({**b["input"], **stash.get(b["id"], {}).get("args", {})})}
                      for b in calls]
            continue
        parts = []
        for b in c:
            if b["type"] == "tool_result":
                body = b.get("content")
                if isinstance(body, list):
                    body = "".join(x.get("text", "") for x in body)
                items.append({"type": "function_call_output", "call_id": b["tool_use_id"], "output": body or ""})
            elif b["type"] == "text":
                parts.append({"type": "input_text", "text": b["text"]})
            elif b["type"] == "image":
                s = b["source"]
                parts.append({"type": "input_image", "image_url": f"data:{s['media_type']};base64,{s['data']}"})
        if parts:
            items.append({"role": "user", "content": parts})
    return instructions, items


def _blocks(j: dict) -> tuple[list, list[str], list[dict], dict, bool]:
    """Response output -> (blocks, remaining actions, reasoning items, stripped Sol-only args by
    call_id, whether the text came from `answer`). `answer` becomes the text block (Sol writes
    none beside a tool call); the last call's `remaining_actions` says what the turn still owes.
    Empty args are dropped (Sol sends value: "" for an omitted optional one)."""
    text, calls, reasoning, answers, remaining, sol_args = [], [], [], [], [], {}
    for o in j.get("output") or []:
        if o["type"] == "reasoning":
            reasoning.append(o)
        elif o["type"] == "message":
            text += [p["text"] for p in o.get("content") or [] if p.get("type") == "output_text" and p.get("text")]
        elif o["type"] == "function_call":
            try:
                inp = json.loads(o.get("arguments") or "{}")
            except json.JSONDecodeError as e:  # Sol once sent truncated arguments
                raise Retryable(f"malformed tool arguments: {e}") from e
            sol_args[o["call_id"]] = {k: inp.pop(k) for k in SOL_ONLY_ARGS if k in inp}
            remaining = [str(r) for r in sol_args[o["call_id"]].get("remaining_actions") or [] if str(r).strip()]
            ans = str(sol_args[o["call_id"]].get("answer") or "").strip()
            if ans and ans not in answers:
                answers.append(ans)
            calls.append(SimpleNamespace(type="tool_use", id=o["call_id"], name=o["name"],
                                         input={k: v for k, v in inp.items() if v not in ("", None)}))
    real = "\n\n".join(t for t in text if t.strip())
    written = real or "\n\n".join(answers)
    blocks = ([SimpleNamespace(type="text", text=written)] if written else []) + calls
    return blocks, remaining, reasoning, sol_args, bool(written and not real)


async def _post(body: dict) -> dict:
    headers = {"Authorization": "Bearer " + config.OPENAI_API_KEY}
    for attempt, delay in enumerate((*RETRY_DELAYS_S, None)):
        try:
            r = await _client.post(URL, json=body, headers=headers)
            if r.status_code == 429 or r.status_code >= 500:
                raise Retryable(f"HTTP {r.status_code}: {r.text[:200]}")
            r.raise_for_status()
            j = r.json()
            if j.get("error"):
                raise Retryable(str(j["error"])[:200])
            _blocks(j)  # malformed tool JSON raises Retryable here, inside the retry loop
            return j
        except (Retryable, httpx.TimeoutException, httpx.TransportError) as e:
            if delay is None:
                raise
            log.warning("[sol_retry] attempt %d: %s: %s", attempt + 1, type(e).__name__, str(e)[:200])
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def call_decider(system: list[dict], tools_param: list[dict] | None, msgs: list[dict],
                       tool_choice: dict | None = None):
    """One decider call. tools_param=None is the tools-off final call: the tools still go
    (history may hold function calls) with tool_choice none."""
    if not config.OPENAI_API_KEY:
        raise RuntimeError("DECIDER=sol needs OPENAI_API_KEY")
    stash = _STASH.get()
    if stash is None:
        stash = {}
        _STASH.set(stash)
    start = last_user_text_index(msgs) or 0
    this_turn = {b["id"] for m in msgs[start:] if isinstance(m["content"], list) for b in m["content"]
                 if b.get("type") == "tool_use"}
    for k in [k for k in stash if k not in this_turn]:
        del stash[k]
    instructions, items = _input(system, msgs, stash)
    body = {"model": config.SOL_MODEL, "instructions": instructions, "input": items,
            "tools": _tools(tools_param if tools_param is not None else SOL_TOOLS),
            "tool_choice": "none" if tools_param is None else _tool_choice(tool_choice),
            "reasoning": {"effort": settings.DECIDER_EFFORT or "medium"},
            "max_output_tokens": config.SOL_MAX_OUTPUT_TOKENS,
            "store": False, "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": "conductor-decider-sol"}
    t0 = time.monotonic()
    j = await _post(body)
    blocks, remaining, reasoning, sol_args, synth = _blocks(j)
    calls = [b for b in blocks if b.type == "tool_use"]
    for b in calls:
        stash[b.id] = {"args": sol_args.get(b.id, {})}
    if calls:
        stash[calls[0].id].update(reasoning=reasoning, **({"synth_text": blocks[0].text} if synth else {}))
    u = j.get("usage") or {}
    cached = (u.get("input_tokens_details") or {}).get("cached_tokens") or 0
    usage = SimpleNamespace(input_tokens=u.get("input_tokens", 0) - cached, output_tokens=u.get("output_tokens", 0),
                            cache_read_input_tokens=cached, cache_creation_input_tokens=0)
    incomplete = (j.get("incomplete_details") or {}).get("reason")
    stop = "max_tokens" if incomplete == "max_output_tokens" else ("tool_use" if calls else "end_turn")
    log.warning("[model_call] %s %.1fs in=%s cache_read=%s out=%s reasoning=%s calls=%s remaining=%s stop=%s",
                j.get("model", config.SOL_MODEL), time.monotonic() - t0, usage.input_tokens, cached,
                usage.output_tokens, (u.get("output_tokens_details") or {}).get("reasoning_tokens"),
                [f"{b.name}({json.dumps(b.input)})" for b in calls], remaining, stop)
    # more_actions: the turn still owes an action, so early exit waits (respond._can_exit_early).
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage, model=j.get("model", config.SOL_MODEL),
                           more_actions=bool(remaining))
