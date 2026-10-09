"""
brain_modules/memory_gate.py

Decides WHETHER Seven should touch memory at all, and parses direct recall
questions ("what is my favorite framework") into structured lookups.

WHY A GATE:
    Retrieval on every message is what made "Hey" recite stored facts. Most
    turns (general questions, chit-chat, commands) need no memory. Skipping
    retrieval is also the cheapest latency win available.
"""

import re
from dataclasses import dataclass
from typing import Optional

from brain_modules import fact_extractor, speech_acts


@dataclass(frozen=True)
class RecallQuery:
    """A direct question about something the user told Seven."""
    kind: str                 # "attr" | "likes" | "dislikes"
    attr: str                 # human phrase, e.g. "favorite framework"
    key: str                  # fact slot, e.g. "favorite_framework"
    aliases: tuple = ()       # alternative slots to try


_ATTR_ALIASES = {
    "job": ("job_title", "role", "workplace"),
    "work": ("workplace", "job_title"),
    "occupation": ("job_title", "role"),
    "profession": ("job_title", "role"),
    "school": ("school",), "college": ("school",), "university": ("school",),
    "location": ("city", "hometown"), "home": ("hometown", "city"),
    "age": ("age",), "birthday": ("birthday", "birthdate"), "birthdate": ("birthdate", "birthday"),
}

_TRAILING_NOISE = frozenset({"again", "now", "today", "please", "right", "currently"})

_RE_ATTR = re.compile(
    r"^(?:(?:do you (?:know|remember)|can you (?:tell me|remember)|tell me|remind me)\s+)?"
    r"(?:what|which|who|where|when) (?:is|are|was) my (?P<attr>[a-z][a-z ]{1,40})$"
)
_RE_ATTR2 = re.compile(r"^(?:do you (?:know|remember)|can you remember) my (?P<attr>[a-z][a-z ]{1,40})$")
_RE_LIKES = re.compile(r"^what do i (?P<verb>like|love|enjoy|prefer|hate|dislike)$")
_RE_WHERE = re.compile(r"^where do i (?P<w>live|work|study)$")
_RE_AGE = re.compile(r"^how old am i$")
_RE_JOB = re.compile(r"^what do i do(?: for (?:a )?(?:living|work))?$")

_SELF_REF = frozenset({
    "my", "mine", "myself", "our", "ours", "remember", "recall", "told",
    "earlier", "previously", "before",
})
_PERSONAL_PHRASES = (
    "last time", "you know", "about me", "for me", "i like", "i prefer",
    "should i", "what should i", "recommend", "suggest", "favorite",
)

_LIVE_NEWS_CTX = frozenset({"today", "latest", "breaking", "now", "tonight", "current", "this"})
_PRICE_ASSETS = frozenset({"stock", "stocks", "bitcoin", "crypto", "ethereum", "nasdaq", "sensex", "nifty"})
_PRICE_CTX = frozenset({"price", "prices", "today", "now", "current", "trading", "worth", "rate"})


def _clean_attr(attr: str) -> Optional[str]:
    toks = [t for t in attr.split() if t]
    while toks and toks[-1] in _TRAILING_NOISE:
        toks.pop()
    toks = ["favorite" if t == "favourite" else t for t in toks]
    if not toks or len(toks) > 4:
        return None
    if any(t in ("you", "your", "i", "me") for t in toks) or toks == ["name"]:
        return None
    return " ".join(toks)


def _attr_query(attr_phrase: str) -> Optional[RecallQuery]:
    attr = _clean_attr(attr_phrase)
    if not attr:
        return None
    key = fact_extractor.slug(attr)
    last = attr.split()[-1]
    aliases = _ATTR_ALIASES.get(last, ()) or _ATTR_ALIASES.get(key, ())
    return RecallQuery("attr", attr, key, tuple(aliases))


def parse_recall_query(norm: str) -> Optional[RecallQuery]:
    """
    Parse a normalised question into a RecallQuery, or None.
    "what is my favorite framework" -> attr slot favorite_framework
    "what do i like"                -> every stored 'likes:*' fact
    """
    if not norm:
        return None
    m = _RE_ATTR.match(norm) or _RE_ATTR2.match(norm)
    if m:
        return _attr_query(m.group("attr"))
    m = _RE_LIKES.match(norm)
    if m:
        verb = m.group("verb")
        kind = "dislikes" if verb in ("hate", "dislike") else "likes"
        return RecallQuery(kind, f"things you {verb}", kind)
    m = _RE_WHERE.match(norm)
    if m:
        target = {"live": "city", "work": "workplace", "study": "school"}[m.group("w")]
        return RecallQuery("attr", target.replace("_", " "), target)
    if _RE_AGE.match(norm):
        return RecallQuery("attr", "age", "age", ("age",))
    if _RE_JOB.match(norm):
        return RecallQuery("attr", "job", "job_title", ("role", "workplace"))
    return None


def live_topic(norm: str) -> Optional[str]:
    """
    Detect questions that need LIVE data Seven cannot know offline.
    Returns "weather", "news", "prices", "scores" or None. Whole-word matching,
    so "train" never matches "rain" and "boiling temperature of water" is not weather.
    """
    toks = set(norm.split())
    if toks & {"weather", "forecast"}:
        return "weather"
    if "temperature" in toks and toks & {"outside", "today", "tomorrow", "tonight", "now", "currently"}:
        return "weather"
    if toks & {"news", "headlines"}:
        return "news"
    if toks & _PRICE_ASSETS and toks & _PRICE_CTX:
        return "prices"
    if "who won" in norm or ("score" in toks or "scores" in toks) and toks & {"live", "match", "game", "today", "vs"}:
        return "scores"
    return None


def should_search_memory(norm: str, raw: str = None) -> bool:
    """
    Gate for semantic retrieval. True only when the message plausibly depends
    on something the user told Seven earlier.
    """
    if not norm:
        return False
    if speech_acts.is_greeting(norm) or len(norm.split()) < 3:
        return False
    if live_topic(norm):
        return False
    if raw and fact_extractor.looks_like_statement(raw):
        return False
    toks = set(norm.split())
    if toks & _SELF_REF:
        return True
    return any(speech_acts.has_phrase(norm, p) for p in _PERSONAL_PHRASES)
