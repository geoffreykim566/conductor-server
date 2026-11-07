"""The Explain toggle adds the Explain block; glossary terms ride on the result, minus ones the user named."""
from unittest.mock import patch

from app.api.schemas import ChatRequest
from app.pipeline import glossary
from app.prompts import EXPLAIN_BLOCK, SYSTEM_PROMPT
from conftest import resp, text_block

ENTRIES = [
    {"term": "Buffer size", "match": ["i/o buffer size", "buffer size"], "definition": "d1"},
    {"term": "Latency", "match": ["latency"], "definition": "d2", "url": "https://x", "source": "S"},
]


def test_older_client_gets_explain_off() -> None:
    assert ChatRequest(message="hi").explain is False


async def test_explain_adds_block_after_prompt(run) -> None:
    _, calls = await run([resp(text_block("ok"))], explain=True)
    assert [b["text"] for b in calls[0]["system"][:2]] == [SYSTEM_PROMPT, EXPLAIN_BLOCK]
    _, calls = await run([resp(text_block("ok"))])
    assert [b["text"] for b in calls[0]["system"]] == [SYSTEM_PROMPT], calls[0]["system"]


def _patched(entries):
    """find_terms over `entries` instead of seed/glossary.json."""
    pattern, by_form = glossary._index(entries)
    return patch.multiple(glossary, _PATTERN=pattern, _BY_FORM=by_form)


def test_find_terms_first_mention_longest_form_word_bounds() -> None:
    text = "Set the I/O Buffer Size lower. Latency drops; buffer size again. latencyX isn't one."
    with _patched(ENTRIES):
        hits = glossary.find_terms(text)
    assert [(text[h["start"]:h["end"]], h["term"]) for h in hits] == [("I/O Buffer Size", "Buffer size"),
                                                                      ("Latency", "Latency")]
    assert "url" not in hits[0] and hits[1]["url"] == "https://x" and hits[1]["source"] == "S"


async def test_terms_on_result_skip_ones_the_user_named(run) -> None:
    reply = "Latency is the delay; lower the buffer size."
    with _patched(ENTRIES):
        result, _ = await run([resp(text_block(reply))], messages=[{"role": "user", "content": "what is latency?"}])
    assert [h["term"] for h in result.terms] == ["Buffer size"], result.terms


def test_seed_glossary_loads_and_every_entry_matches_itself() -> None:
    for e in glossary.ENTRIES:
        assert e["term"] and e["match"] and e["definition"], e
        assert any(h["term"] == e["term"] for h in glossary.find_terms(e["match"][0])), e
