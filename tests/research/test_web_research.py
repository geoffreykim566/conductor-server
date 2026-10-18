"""web_research on OpenAI: findings, cited sources, caps, spend, and its failure results."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core import config
from app.pipeline import openai_io
from app.research import parse, search

URL_A = "https://www.fabfilter.com/help/pro-c/support/externalsidechaining"


def _http(body: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", openai_io.URL), json=body)


def _output(text: str, citations: list[tuple[str, str]], searched: list[tuple[str, str]] = ()) -> dict:
    return {"output": [
        {"type": "web_search_call", "action": {"type": "search", "query": "q",
                                              "sources": [{"type": "url", "url": u, "title": t} for u, t in searched]}},
        {"type": "message", "content": [{"type": "output_text", "text": text, "annotations": [
            {"type": "url_citation", "url": u, "title": t} for u, t in citations]}]},
    ], "usage": {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 400}, "output_tokens": 50}}


@pytest.fixture
def post():
    mock = AsyncMock()
    with patch.object(config, "OPENAI_API_KEY", "test"), patch.object(openai_io._client, "post", new=mock), \
            patch.object(openai_io.asyncio, "sleep", new=AsyncMock()):
        yield mock


async def test_findings_sources_and_spend(post) -> None:
    """Text minus the meta lines is the findings; citations are de-duplicated with the utm tag stripped;
    spend is split into uncached input and cache reads."""
    post.side_effect = [_http(_output(
        f"Enable External in Pro-C 3. ([fabfilter.com]({URL_A}?utm_source=openai))\n\n**CONFIDENCE:** confirmed\nCHARACTERISTICS: sidechain ducking",
        [(URL_A + "?utm_source=openai", "External side chaining"), (URL_A + "?utm_source=openai", "dup")]))]
    out = await search.web_research("pro-c 3 sidechain")
    assert out["findings"] == f"Enable External in Pro-C 3. ([fabfilter.com]({URL_A}))", out["findings"]
    assert out["sources"] == [{"title": "External side chaining", "url": URL_A, "type": "confirmed"}], out["sources"]
    assert out["source_tier"] == "confirmed-research", out["source_tier"]
    assert out["_usage"] == {"input_tokens": 600, "output_tokens": 50, "cache_creation_input_tokens": 0,
                             "cache_read_input_tokens": 400}, out["_usage"]
    body = post.call_args.kwargs["json"]
    assert body["tools"] == [{"type": "web_search"}] and body["model"] == config.SOL_MODEL, body


async def test_search_sources_when_nothing_cited(post) -> None:
    """No url_citation in the text: the search call's own sources are used."""
    post.side_effect = [_http(_output("Some findings.", [], searched=[(URL_A + "?utm_source=openai", "Help")]))]
    out = await search.web_research("q")
    assert [s["url"] for s in out["sources"]] == [URL_A], out["sources"]


async def test_caps(post) -> None:
    """Findings and sources are capped: the result rides in round-tripped history."""
    many = [(f"https://example.com/{i}", str(i)) for i in range(15)]
    post.side_effect = [_http(_output("x" * 7000, many))]
    out = await search.web_research("q")
    assert len(out["sources"]) == 10 and out["findings"].endswith("(truncated)"), (len(out["sources"]), out["findings"][-20:])


async def test_timeout_and_failure_return_errors(post) -> None:
    """A timeout or a failed call is an error result, never a raised exception."""
    async def slow(*a, **k):
        await asyncio.Event().wait()  # never set; asyncio.sleep is patched out by the fixture
    with patch.object(config, "RESEARCH_CALL_TIMEOUT_S", 0.01):
        post.side_effect = slow
        out = await search.web_research("q")
    assert out["error"] == "web research timed out", out
    post.side_effect = [_http({"error": {"message": "bad key"}}, status=401)]
    out = await search.web_research("q")
    assert out["error"] == "web research failed", out


def test_confidence_reads_bold_and_plain_lines() -> None:
    """The confidence line is read bold or plain, and defaults to commonly_believed."""
    assert parse.parse_confidence("x\n**CONFIDENCE:** genre_inferred") == "genre_inferred"
    assert parse.parse_confidence("x\nCONFIDENCE: confirmed") == "confirmed"
    assert parse.parse_confidence("no line") == "commonly_believed"
