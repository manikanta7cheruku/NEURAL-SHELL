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
    target: str = ""          # extra: verb (typed_likes) or the thing asked about (reason)


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


_KINDS = {"movie": "movie", "film": "movie", "song": "song", "book": "book", "show": "show",
          "series": "show", "game": "game", "food": "food", "band": "band", "album": "album",
          "podcast": "podcast", "sport": "sport"}
_HIST_RE = re.compile(r"\b(?:before|previously|earlier|originally|formerly|used to|previous|former|original)\b")
_CUR_RE = re.compile(r"\b(?:now|currently|current|these days)\b")
_RE_PROV = re.compile(
    r"^(?:and )?(?:how do you know|where did you (?:get|learn|hear)|when did i (?:tell|say|mention)|"
    r"when was that|did i (?:tell|say)|how did you learn)\b.*$")
_BAD_ATTR_WORDS = {"is", "are", "and", "how", "what", "why", "who", "when", "where", "was", "were", "does", "do"}
_RE_WHICH = re.compile(
    r"^(?:which|what) (?P<attr>[a-z ]{2,40}?) (?:do|did) i (?P<verb>prefer|like|love|use|choose|favor|enjoy)\b.*$")
_RE_WHAT_DID = re.compile(r"^what (?:did|do) i (?:prefer|like|love|use|choose)(?: (?P<attr>[a-z ]{2,40}?))?"
                          r"(?: (?:before|previously|earlier|originally))?(?: now)?$")
_RE_WAS_MY = re.compile(r"^what (?:was|were) my (?:(?:previous|former|old|earlier|original|last) )?"
                        r"(?P<attr>[a-z ]{2,40}?)(?: (?:before|previously|earlier|originally))?$")
_RE_WHY = re.compile(r"^why (?:did|do|would) i (?:choose|pick|prefer|like|love|use|switch to|go with|select|"
                     r"change|switch)(?: (?P<target>.+))?$|^why is (?P<target2>.+) my (?:favorite|preferred)\b.*$|"
                     r"^what(?: is|was)? the reason (?:i|for)\b.*$")


def _clean_attr_words(attr: str) -> str:
    drop = {"the", "most", "now", "currently", "and", "what", "did", "i", "that", "this", "those", "these",
            "my", "before", "previously", "earlier", "originally", "formerly", "used", "to", "for", "about", "of"}
    words = [w for w in attr.split() if w not in drop]
    return " ".join(words[:4])


def _parse_extended(norm: str) -> Optional[RecallQuery]:
    """History, provenance, reason and typed-preference questions."""
    if _RE_PROV.match(norm) and len(norm.split()) <= 16 and (
            {"that", "this", "it", "me"} & set(norm.split())):
        return RecallQuery("provenance", "", "")
    m = _RE_WHY.match(norm)
    if m:
        target = m.group("target") or m.group("target2") or ""
        return RecallQuery("reason", _clean_attr_words(target), fact_extractor.slug(_clean_attr_words(target)),
                           target=target)
    m = _RE_WHICH.match(norm)
    if m and set(m.group("attr").split()) & _BAD_ATTR_WORDS:
        m = None
    if m:
        attr, verb = _clean_attr_words(m.group("attr")), m.group("verb")
        if attr in _KINDS and verb in ("like", "love", "enjoy") and not _HIST_RE.search(norm):
            kind = _KINDS[attr]
            return RecallQuery("typed_likes", kind, f"likes:{kind}:", target=verb)
        if _HIST_RE.search(norm):
            return RecallQuery("timeline" if _CUR_RE.search(norm) else "history", attr, fact_extractor.slug(attr))
        return _attr_query(attr)
    m = _RE_WHAT_DID.match(norm)
    if m and _HIST_RE.search(norm) and not set((m.group("attr") or "").split()) & _BAD_ATTR_WORDS:
        attr = _clean_attr_words(m.group("attr") or "")
        return RecallQuery("history", attr, fact_extractor.slug(attr))
    m = _RE_WAS_MY.match(norm)
    if m and not set(m.group("attr").split()) & _BAD_ATTR_WORDS:
        attr = _clean_attr_words(m.group("attr"))
        return RecallQuery("history", attr, fact_extractor.slug(attr))
    return None


_LEAD = r"^(?:(?:so|and|ok|okay|just|please|then|well|now|hey seven|seven)\s+)*(?:can you |could you |would you )?"
_RE_PROFILE = re.compile(
    _LEAD + r"(?:"
    r"what (?:else )?(?:do|did) you (?:know|remember|have) (?:about|on|of) (?:me|myself)"
    r"|what (?:all |exactly )?(?:do|did) you know about me"
    r"|how much do you know about me"
    r"|what have you (?:learned|learnt|remembered|saved|stored) about me"
    r"|what (?:have|did) i (?:told|tell) you(?: about (?:me|myself))?(?: so far)?"
    r"|what information do you have (?:on|about) me"
    r"|tell me (?:about me|about myself|what you know about me|everything you know(?: about me)?|everything about me|everything)"
    r"|describe me|who am i to you|what do you think you know about me"
    r")(?: please| so far| then| now)?$")
_RE_PROFILE_SOURCE = re.compile(
    _LEAD + r"(?:how (?:do|did|can) you know|where did you (?:get|learn|find)|how did you (?:learn|find out|get))\s+"
    r"(?:all |so much |that much )?(?:of )?(?:these|those|this|that|so much|everything|all this|all that|all of (?:this|that)|it all)"
    r"(?: things| stuff| info| information| facts| details)?(?: about me| on me)?$")


def parse_profile(norm: str) -> Optional[str]:
    """
    "what do you know about me", "tell me about me", "just tell me everything" -> "profile";
    "how do you know all these things about me" -> "profile_source". None otherwise.
    Answered from stored evidence; the model never describes the user.
    """
    if not norm:
        return None
    if _RE_PROFILE.match(norm):
        return "profile"
    if _RE_PROFILE_SOURCE.match(norm) and (norm.endswith(("about me", "on me")) or
                                            any(w in norm.split() for w in ("these", "those", "everything", "all"))):
        return "profile_source"
    return None


def time_sensitive(norm: str) -> bool:
    """True when stale knowledge would be misleading (live topics, 'latest', 'today')."""
    toks = set(norm.split())
    return bool(live_topic(norm)) or bool(toks & {"latest", "current", "currently", "today", "tonight",
                                                   "breaking", "recent", "recently", "now"})


def parse_recall_query(norm: str) -> Optional[RecallQuery]:
    """
    Parse a normalised question into a RecallQuery, or None.
    "what is my favorite framework" -> attr slot favorite_framework
    "what do i like"                -> every stored 'likes:*' fact
    """
    if not norm:
        return None
    ext = _parse_extended(norm)
    if ext is not None:
        return ext
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
