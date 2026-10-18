"""Pulls the confidence line, findings text and cited sources out of a research response
(OpenAI Responses output with the built-in web_search tool)."""
import re

CONFIDENCE_TO_TIER: dict[str, str] = {
    "confirmed": "confirmed-research",
    "commonly_believed": "community-research",
    "genre_inferred": "genre-inference",
}

# OpenAI appends ?utm_source=openai (or &utm_source=openai) to every cited URL.
_UTM = re.compile(r"[?&]utm_source=openai\b")


def clean_url(url: str) -> str:
    return _UTM.sub("", url)


def parse_confidence(text: str) -> str:
    m = re.search(
        r"^\**CONFIDENCE:?\**:?\s*(confirmed|commonly_believed|genre_inferred)",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    return m.group(1).lower() if m else "commonly_believed"


def strip_meta(text: str) -> str:
    text = re.sub(r"^\**CONFIDENCE\b.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"^\**CHARACTERISTICS\b.*$", "", text, flags=re.MULTILINE)
    return _UTM.sub("", text).strip()


def response_text(output: list[dict]) -> str:
    return "".join(p.get("text", "") for o in output if o.get("type") == "message"
                   for p in o.get("content") or [] if p.get("type") == "output_text")


def extract_sources(output: list[dict], confidence: str) -> list[dict]:
    """Cited sources: the text's url_citation annotations (preferred), else every source the
    search calls returned. De-duplicated by URL, utm tag stripped."""
    cited = [(a.get("url"), a.get("title")) for o in output if o.get("type") == "message"
             for p in o.get("content") or [] for a in p.get("annotations") or [] if a.get("type") == "url_citation"]
    if not cited:
        cited = [(s.get("url"), s.get("title")) for o in output if o.get("type") == "web_search_call"
                 for s in (o.get("action") or {}).get("sources") or []]
    sources: list[dict] = []
    seen: set[str] = set()
    for url, title in cited:
        url = clean_url(url or "")
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"title": title or url, "url": url, "type": confidence})
    return sources


def extract_sources_from_text(text: str, confidence: str) -> list[dict]:
    """Fallback: bare URLs from response text when no structured citation came back."""
    sources: list[dict] = []
    seen: set[str] = set()
    for url in re.findall(r"https?://[^\s\)\]\>\"']+", text):
        url = clean_url(url.rstrip(".,;:"))
        if url and url not in seen:
            seen.add(url)
            sources.append({"title": url, "url": url, "type": confidence})
    return sources
