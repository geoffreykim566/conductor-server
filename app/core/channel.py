"""Where a visit or signup came from (its channel), and whether its user agent is a bot.

Channel precedence: a `utm_source` or referrer label the page passed, then the in-app browser
named in the user agent (Instagram and TikTok's in-app browsers usually send no referrer), else
"direct". README.md, Funnel."""
import re

# utm_source values and short-link tags → channel.
_UTM = {
    "ig": "instagram", "insta": "instagram", "instagram": "instagram",
    "tt": "tiktok", "tiktok": "tiktok",
    "yt": "youtube", "youtube": "youtube",
    "x": "x", "twitter": "x",
    "fb": "facebook", "facebook": "facebook",
    "th": "threads", "threads": "threads",
    "li": "linkedin", "linkedin": "linkedin",
    "rd": "reddit", "reddit": "reddit",
    "dc": "discord", "discord": "discord",
    "email": "email", "invite": "email", "newsletter": "email",
}

# Referrer host suffix → channel. A suffix match, so "l.instagram.com" and "m.youtube.com" hit.
_HOSTS = [
    ("instagram.com", "instagram"), ("facebook.com", "facebook"), ("fb.com", "facebook"),
    ("t.co", "x"), ("twitter.com", "x"), ("x.com", "x"),
    ("youtube.com", "youtube"), ("youtu.be", "youtube"),
    ("tiktok.com", "tiktok"), ("threads.net", "threads"), ("threads.com", "threads"),
    ("reddit.com", "reddit"), ("linkedin.com", "linkedin"), ("lnkd.in", "linkedin"),
    ("discord.com", "discord"), ("discord.gg", "discord"),
    ("news.ycombinator.com", "hackernews"),
    ("chatgpt.com", "ai"), ("openai.com", "ai"), ("perplexity.ai", "ai"),
    ("claude.ai", "ai"), ("gemini.google.com", "ai"),
    ("bing.com", "search"), ("duckduckgo.com", "search"), ("search.yahoo.com", "search"),
    ("ecosia.org", "search"), ("search.brave.com", "search"), ("kagi.com", "search"),
    ("mail.google.com", "email"),
]
# google.com, google.co.uk, google.de, ... (gemini.google.com is matched above, first).
_GOOGLE = re.compile(r"(^|\.)google\.[a-z.]+$")

# In-app browsers that name themselves in the user agent.
_IN_APP = [
    (re.compile(r"Instagram"), "instagram"),
    (re.compile(r"Barcelona"), "threads"),  # Threads' in-app browser
    (re.compile(r"FBAN|FBAV|FB_IAB|FBIOS"), "facebook"),
    (re.compile(r"musical_ly|Bytedance|TikTok", re.I), "tiktok"),
    (re.compile(r"LinkedInApp"), "linkedin"),
    (re.compile(r"Snapchat"), "snapchat"),
]

_BOT = re.compile(
    r"bot|crawl|spider|slurp|scrape|headless|lighthouse|pagespeed|gtmetrix|preview|"
    r"facebookexternalhit|embedly|curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|"
    r"phantom|selenium|puppeteer|playwright|monitor|uptime|pingdom",
    re.I,
)


def _label(raw: str) -> str | None:
    """A utm tag or referrer host as a channel; an unknown value is kept as itself."""
    s = raw.strip().lower()
    if not s:
        return None
    if s in _UTM:
        return _UTM[s]
    host = s.removeprefix("www.")
    for suffix, ch in _HOSTS:
        if host == suffix or host.endswith("." + suffix):
            return ch
    if _GOOGLE.search(host):
        return "search"
    return s[:60]


def channel(label: str | None, user_agent: str | None) -> str:
    """The channel from the page's label (utm_source or referrer host), else the user agent."""
    if label and (ch := _label(label)):
        return ch
    for pat, ch in _IN_APP:
        if pat.search(user_agent or ""):
            return ch
    return "direct"


def is_bot(user_agent: str | None) -> bool:
    """A bot, crawler, link-preview fetcher or headless browser. An empty agent counts as one."""
    return not user_agent or bool(_BOT.search(user_agent))


def device(user_agent: str | None) -> str:
    ua = user_agent or ""
    if re.search(r"iPad|Tablet", ua):
        return "tablet"
    if re.search(r"Mobi|iPhone|Android", ua):
        return "mobile"
    return "desktop"
