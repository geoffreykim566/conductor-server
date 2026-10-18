"""web_research: one nested Sol call with OpenAI's built-in web_search tool that returns
findings and sources. Executor for tools.WEB_RESEARCH_SCHEMA. See README.md."""
from __future__ import annotations

import asyncio
import logging
import time as _time

from app.core import config
from app.pipeline import openai_io
from app.research.parse import (
    CONFIDENCE_TO_TIER,
    extract_sources,
    extract_sources_from_text,
    parse_confidence,
    response_text,
    strip_meta,
)

log = logging.getLogger(__name__)

# Extraction only: the decider, not this call, turns findings into the answer.
_RESEARCH_SYSTEM = (
    "You are a music production researcher. Search the web for accurate information.\n"
    "Report what you find: specific techniques, gear, signal chains, processing details.\n"
    "Name exactly what sources describe -- include third-party plugins and gear as mentioned.\n\n"
    "After your main answer, output exactly two lines:\n"
    "CONFIDENCE: confirmed | commonly_believed | genre_inferred\n"
    "CHARACTERISTICS: [2-5 word sonic/technical description, for future KB matching]\n\n"
    "Confidence guide:\n"
    "  confirmed -- direct evidence (interviews, official sources, documented gear lists)\n"
    "  commonly_believed -- multiple reliable sources agree, not directly verified\n"
    "  genre_inferred -- only general genre/technique knowledge found, nothing specific"
)


# The tool_result stays in round-tripped history, so it must be capped (an uncapped
# result 422'd every later request in that conversation).
_MAX_FINDINGS_CHARS = 6_000
_MAX_SOURCES = 10


def _usage_dict(u: dict | None) -> dict:
    # pipeline's usage shape: Responses counts cached tokens inside input_tokens.
    u = u or {}
    cached = (u.get("input_tokens_details") or {}).get("cached_tokens") or 0
    return {
        "input_tokens": (u.get("input_tokens") or 0) - cached,
        "output_tokens": u.get("output_tokens") or 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": cached,
    }


async def web_research(query: str) -> dict:
    """The returned "_usage" key is popped by pipeline/dispatch.py so the spend is counted
    but never shown to the model. OpenAI runs the search loop inside the one call."""
    body = {
        "model": config.SOL_MODEL,
        "instructions": _RESEARCH_SYSTEM,
        "input": query,
        "tools": [{"type": "web_search"}],
        "reasoning": {"effort": config.RESEARCH_EFFORT},
        "max_output_tokens": config.SOL_MAX_OUTPUT_TOKENS,
        "store": False,
        "include": ["web_search_call.action.sources"],
    }
    call_start = _time.monotonic()
    try:
        j = await asyncio.wait_for(openai_io.post(body), timeout=config.RESEARCH_CALL_TIMEOUT_S)
    except asyncio.TimeoutError:
        log.warning("[web_research_timing] TIMEOUT after %.1fs (query=%r)", _time.monotonic() - call_start, query)
        return {"error": "web research timed out", "_usage": _usage_dict(None)}
    except Exception:
        log.exception("[web_research_timing] FAILED after %.1fs (query=%r)", _time.monotonic() - call_start, query)
        return {"error": "web research failed", "_usage": _usage_dict(None)}

    output = j.get("output") or []
    text = response_text(output)
    confidence = parse_confidence(text)
    findings = strip_meta(text)
    source_tier = CONFIDENCE_TO_TIER.get(confidence, "community-research")

    sources = extract_sources(output, confidence)
    if not sources and findings:
        sources = extract_sources_from_text(findings, confidence)

    if len(findings) > _MAX_FINDINGS_CHARS:
        findings = findings[:_MAX_FINDINGS_CHARS] + "\n\n... (truncated)"
    sources = sources[:_MAX_SOURCES]

    searches = sum(1 for o in output if o.get("type") == "web_search_call")
    log.warning(
        "[web_research_timing] SUCCESS after %.1fs (%d search call(s), %d sources, query=%r)",
        _time.monotonic() - call_start, searches, len(sources), query,
    )

    result: dict = {
        "findings": findings,
        "source_tier": source_tier,
        "sources": sources,
        "_usage": _usage_dict(j.get("usage")),
    }
    if not findings:
        result["note"] = "no findings returned -- tell the user you couldn't find reliable information"
    return result
