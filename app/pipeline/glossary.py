"""Finds glossary terms in a reply, so the client can underline them and show a set
definition on click. Loaded once from seed/glossary.json at import. Why code, not Sol: README.md (Glossary)."""
import json
import re
from pathlib import Path

ENTRIES: list[dict] = json.loads(
    (Path(__file__).parents[2] / "seed" / "glossary.json").read_text())["terms"]


def _index(entries: list[dict]):
    """(pattern, form -> entry). Longest spelling first, so "i/o buffer size" wins over "buffer size"."""
    forms = sorted(((f.lower(), e) for e in entries for f in e["match"]), key=lambda fe: len(fe[0]), reverse=True)
    if not forms:
        return None, {}
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(f) for f, _ in forms) + r")(?![\w-])", re.IGNORECASE)
    return pattern, dict(forms)


_PATTERN, _BY_FORM = _index(ENTRIES)


def find_terms(text: str, user_text: str = "") -> list[dict]:
    """The first mention of each entry in `text`, in reading order:
    {start, end, term, definition, url?, source?}. Offsets are str indices into `text`.
    Entries the user's own message names are left out: the reply is already about them."""
    if not _PATTERN or not text:
        return []
    found = []
    seen = {_BY_FORM[m.group(1).lower()]["term"] for m in _PATTERN.finditer(user_text or "")}
    for m in _PATTERN.finditer(text):
        entry = _BY_FORM[m.group(1).lower()]
        if entry["term"] in seen:
            continue
        seen.add(entry["term"])
        hit = {"start": m.start(), "end": m.end(), "term": entry["term"], "definition": entry["definition"]}
        for key in ("url", "source"):
            if entry.get(key):
                hit[key] = entry[key]
        found.append(hit)
    return found
