"""The decider call when DECIDER=sol: GPT-6.1 Sol on OpenAI's Responses API. Translates the
Anthropic-shaped request (system blocks, messages, tools) to Responses input items and the
reply back into Anthropic-shaped blocks, so respond.py and the history format are unchanged.
Why Responses, the Sol-only args and the reasoning stash: README.md (Sol decider)."""
import asyncio
import contextvars
import json
import logging
import time
from types import SimpleNamespace

import httpx

from app.core import config
from app.pipeline import settings
from app.tools.schemas_sol import SOL_TOOLS

log = logging.getLogger(__name__)

URL = "https://api.openai.com/v1/responses"
RETRY_DELAYS_S = (1, 2, 4, 8)
_client = httpx.AsyncClient(timeout=180)  # tests patch _client.post

# Sol's encrypted reasoning items, keyed by the call_ids of the function calls they came
# with, replayed before those calls on the turn's next decider call (OpenAI recommends it).
# Never in history: the client round-trips history and the next turn starts fresh.
_REASONING: contextvars.ContextVar[dict | None] = contextvars.ContextVar("sol_reasoning", default=None)


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


def _input(system: list[dict], msgs: list[dict], reasoning: dict) -> tuple[str, list[dict]]:
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
            if text:
                items.append({"role": "assistant", "content": text})
            calls = [b for b in c if b["type"] == "tool_use"]
            if calls:
                items += reasoning.get(calls[0]["id"], [])
            items += [{"type": "function_call", "call_id": b["id"], "name": b["name"],
                       "arguments": json.dumps(b["input"])} for b in calls]
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


def _blocks(j: dict) -> tuple[list, bool, list[dict]]:
    """Response output -> Anthropic-shaped blocks. Strips the Sol-only args: `answer` becomes
    the text block (Sol writes none beside a tool call), `more_actions` the returned flag.
    Empty args are dropped (Sol sends value: "" for an omitted optional one)."""
    text, calls, reasoning, answers, more = [], [], [], [], False
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
            more = bool(inp.pop("more_actions", False)) or more
            ans = str(inp.pop("answer", "") or "").strip()
            if ans and ans not in answers:
                answers.append(ans)
            calls.append(SimpleNamespace(type="tool_use", id=o["call_id"], name=o["name"],
                                         input={k: v for k, v in inp.items() if v not in ("", None)}))
    written = "\n\n".join(t for t in text if t.strip()) or "\n\n".join(answers)
    blocks = ([SimpleNamespace(type="text", text=written)] if written else []) + calls
    return blocks, more, reasoning


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
    stash = _REASONING.get()
    if stash is None:
        stash = {}
        _REASONING.set(stash)
    in_history = {b["id"] for m in msgs if isinstance(m["content"], list) for b in m["content"]
                  if b.get("type") == "tool_use"}
    for k in [k for k in stash if k not in in_history]:
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
    blocks, more, reasoning = _blocks(j)
    calls = [b for b in blocks if b.type == "tool_use"]
    if calls and reasoning:
        stash[calls[0].id] = reasoning
    u = j.get("usage") or {}
    cached = (u.get("input_tokens_details") or {}).get("cached_tokens") or 0
    usage = SimpleNamespace(input_tokens=u.get("input_tokens", 0) - cached, output_tokens=u.get("output_tokens", 0),
                            cache_read_input_tokens=cached, cache_creation_input_tokens=0)
    incomplete = (j.get("incomplete_details") or {}).get("reason")
    stop = "max_tokens" if incomplete == "max_output_tokens" else ("tool_use" if calls else "end_turn")
    log.warning("[model_call] %s %.1fs in=%s cache_read=%s out=%s reasoning=%s more_actions=%s stop=%s",
                j.get("model", config.SOL_MODEL), time.monotonic() - t0, usage.input_tokens, cached,
                usage.output_tokens, (u.get("output_tokens_details") or {}).get("reasoning_tokens"), more, stop)
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage, model=j.get("model", config.SOL_MODEL),
                           more_actions=more)
