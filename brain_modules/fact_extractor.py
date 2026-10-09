"""
brain_modules/fact_extractor.py

Turns what the user SAYS about themselves into clean, validated facts.

ROOT CAUSE THIS FIXES:
    The old extractor stored the raw sentence ("User said: ...") for anything
    that matched a loose pattern, and never checked whether the sentence was a
    question. Questions and fragments became "facts" such as
    "User's name is What You", and every later retrieval was contaminated.

RULES:
    1. A question or an imperative request NEVER produces a fact.
    2. Every extracted value is validated (no pronouns, interrogatives,
       filler words or empty values).
    3. Implicit statements are only stored for stable attributes ("my job is",
       "my favorite X is", "I live in"), never for passing states like
       "my code is broken".
    4. Explicit directives ("remember that ...") are always honoured.
    5. Output is a clean third-person sentence: "User's favorite framework
       is React", never "User said: remember that ...".
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from brain_modules import speech_acts


@dataclass(frozen=True)
class ExtractedFact:
    """One validated fact. `key` is the slot, so a new value replaces the old."""
    key: str
    value: str
    text: str
    category: str
    confidence: float
    explicit: bool = False


_INTERROGATIVES = frozenset({
    "what", "who", "whom", "whose", "which", "where", "when", "why", "how",
})
_PRONOUNS = frozenset({
    "i", "me", "my", "mine", "you", "your", "yours", "he", "she", "it", "we",
    "they", "them", "this", "that", "these", "those", "something", "anything",
    "nothing", "everything", "someone", "anyone", "none",
})
_FILLER = frozenset({
    "um", "uh", "like", "well", "so", "just", "really", "very", "actually",
    "basically", "literally", "okay", "ok", "yeah", "yes", "no", "hmm",
})
_STOPWORDS = frozenset({"a", "an", "the", "of", "to", "and", "or", "is", "are", "in", "on", "at", "for", "with"})
_BAD_VALUES = _PRONOUNS | _FILLER | frozenset({
    "idk", "unknown", "here", "there", "true", "false", "maybe",
    "not sure", "dont know", "do not know",
})
_BAD_LIKE_START = frozenset({
    "how", "when", "that", "it", "this", "what", "the way", "being", "talking",
    "when you", "if",
})

# Attributes stable enough to store from an implicit "my X is Y" statement.
_STABLE_ATTRS = frozenset({
    "name", "age", "birthday", "birthdate", "job", "occupation", "profession",
    "role", "title", "company", "employer", "school", "college", "university",
    "major", "degree", "city", "town", "country", "hometown", "timezone",
    "language", "editor", "ide", "os", "browser", "email", "phone", "address",
    "dog", "cat", "pet", "brother", "sister", "mother", "mom", "father", "dad",
    "wife", "husband", "girlfriend", "boyfriend", "partner", "boss", "manager",
    "team", "hobby", "hobbies", "goal", "goals", "dream", "stack", "framework",
})
_ATTR_PREFIXES = frozenset({"favorite", "preferred", "primary", "main", "default"})

_ROLE_WORDS = frozenset({
    "student", "developer", "engineer", "designer", "teacher", "doctor", "nurse",
    "writer", "artist", "musician", "manager", "founder", "freelancer",
    "programmer", "photographer", "filmmaker", "director", "analyst",
    "scientist", "researcher", "lawyer", "accountant", "consultant", "intern",
    "professor", "architect", "entrepreneur", "editor", "producer", "gamer",
})
_TECH_WORDS = frozenset({
    "python", "java", "javascript", "typescript", "react", "vue", "angular",
    "linux", "windows", "macos", "mac", "vscode", "vim", "neovim", "emacs",
    "git", "docker", "kubernetes", "rust", "go", "golang", "cpp", "csharp",
    "node", "nodejs", "django", "flask", "fastapi", "pytorch", "tensorflow",
})
_PLAYABLES = frozenset({
    "chess", "guitar", "piano", "football", "soccer", "cricket", "basketball",
    "tennis", "badminton", "violin", "drums", "volleyball", "hockey", "golf",
    "valorant", "minecraft", "fifa", "poker", "carrom",
})

_RE_EXPLICIT = re.compile(
    r"^(?:(?:please|pls|hey|ok|okay)[,\s]+)*"
    r"(?:(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to|can\s+you|could\s+you|would\s+you|"
    r"you\s+(?:should|must|need\s+to))\s+)?(?:please\s+)?"
    r"(?:remember|memorize|keep\s+in\s+mind|don'?t\s+forget|do\s+not\s+forget|note\s+that)"
    r"(?:\s+that)?[,:\s]+(?P<body>.+)$",
    re.IGNORECASE,
)
_RE_MY_ATTR = re.compile(
    r"^my\s+(?P<attr>[a-z][a-z' \-]{1,40}?)\s+(?:is|are|was|were)\s+(?P<val>.+)$",
    re.IGNORECASE,
)
_RE_LIKE = re.compile(
    r"^i\s+(?:really\s+|absolutely\s+|do\s+)?"
    r"(?P<verb>love|like|enjoy|adore|prefer|hate|dislike)\s+(?P<val>.+)$",
    re.IGNORECASE,
)
_RE_WORK_AT = re.compile(r"^i\s+(?:currently\s+)?work\s+(?:at|for)\s+(?P<val>.+)$", re.IGNORECASE)
_RE_WORK_AS = re.compile(r"^i\s+(?:currently\s+)?work\s+as\s+(?:an?\s+)?(?P<val>.+)$", re.IGNORECASE)
_RE_ROLE = re.compile(r"^i\s*(?:am|'m)\s+an?\s+(?P<val>[a-z][a-z \-]{2,40})$", re.IGNORECASE)
_RE_STUDY_AT = re.compile(r"^i\s+(?:study|am\s+studying|'m\s+studying)\s+at\s+(?P<val>.+)$", re.IGNORECASE)
_RE_STUDY = re.compile(r"^i\s+(?:study|am\s+studying|'m\s+studying)\s+(?P<val>.+)$", re.IGNORECASE)
_RE_LIVE = re.compile(r"^i\s+(?:live|stay)\s+in\s+(?P<val>.+)$", re.IGNORECASE)
_RE_FROM = re.compile(r"^i\s*(?:am|'m)\s+from\s+(?P<val>.+)$|^i\s+come\s+from\s+(?P<val2>.+)$", re.IGNORECASE)
_RE_AGE = re.compile(r"^i\s*(?:am|'m)\s+(?P<val>\d{1,3})(?:\s+years?\s+old)?$", re.IGNORECASE)
_RE_CODE_IN = re.compile(r"^i\s+(?:code|program|develop)\s+in\s+(?P<val>.+)$", re.IGNORECASE)
_RE_USE = re.compile(r"^i\s+(?:mostly\s+|usually\s+|mainly\s+)?use\s+(?P<val>.+)$", re.IGNORECASE)
_RE_PLAY = re.compile(r"^i\s+play\s+(?P<val>[a-z]{3,20})$", re.IGNORECASE)

_RE_LEADING_FILLER = re.compile(
    r"^(?:(?:hey|hi|hello)\s+seven[,\s]+|seven[,\s]+|ok(?:ay)?[,\s]+|also[,\s]+|and[,\s]+|"
    r"by\s+the\s+way[,\s]+|btw[,\s]+|just\s+so\s+you\s+know[,\s]+|fyi[,\s]+|so[,\s]+|"
    r"well[,\s]+|actually[,\s]+)+",
    re.IGNORECASE,
)
_RE_SPLIT = re.compile(r"(?<=[.!;])\s+|\s+(?:and|but)\s+(?=my\s|i\s)", re.IGNORECASE)


def slug(text: str) -> str:
    """Stable key fragment: 'My Favourite Framework' -> 'favorite_framework'."""
    t = (text or "").lower().replace("favourite", "favorite").replace("'", "")
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t


def clean_value(value: str) -> Optional[str]:
    """
    Validate and tidy a candidate value. Returns None for anything that is not
    a plausible entity: empty, question-like, pronoun-only, interrogative-led.
    """
    if value is None or "?" in value:
        return None
    v = value.strip().strip(" \t.,;:!\"'()[]")
    if not v or len(v) > 80 or not re.search(r"[A-Za-z0-9]", v):
        return None
    toks = re.findall(r"[A-Za-z0-9+#.'\-]+", v)
    if not toks or len(toks) > 10:
        return None
    low = [t.lower().strip(".'") for t in toks]
    if low[0] in _INTERROGATIVES or low[0] in _FILLER:
        return None
    if all(t in _BAD_VALUES or t in _STOPWORDS for t in low):
        return None
    if v.lower() in _BAD_VALUES:
        return None
    return v


def valid_name(name: str) -> Optional[str]:
    """Validate a person's name. Rejects 'What You', 'You', 'Called Max' etc."""
    n = (name or "").strip().strip(".,!?\"'")
    toks = n.split()
    if not 1 <= len(toks) <= 3:
        return None
    for t in toks:
        if not re.fullmatch(r"[A-Za-z][A-Za-z'\-]+", t) or len(t) < 2:
            return None
        if t.lower() in _INTERROGATIVES | _PRONOUNS | _FILLER | {"called", "named", "name", "is"}:
            return None
    return " ".join(t[:1].upper() + t[1:] for t in toks)


def _valid_attr(attr: str) -> Optional[str]:
    toks = attr.lower().replace("favourite", "favorite").split()
    if not 1 <= len(toks) <= 4:
        return None
    if any(t in _INTERROGATIVES or t in _PRONOUNS for t in toks):
        return None
    return " ".join(toks)


def _attr_is_stable(attr: str) -> bool:
    toks = attr.split()
    return toks[0] in _ATTR_PREFIXES or toks[-1] in _STABLE_ATTRS


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _third_person(body: str) -> str:
    """Rewrite a first-person sentence as a third-person note about the user."""
    b = body.strip().rstrip(".!;")
    b = re.sub(r"^my\s+", "User's ", b, flags=re.IGNORECASE)
    b = re.sub(r"^i\s*(?:am|'m)\s+", "User is ", b, flags=re.IGNORECASE)
    b = re.sub(r"^i\s+", "User ", b, flags=re.IGNORECASE)
    b = re.sub(r"\bmy\b", "their", b, flags=re.IGNORECASE)
    return b[:1].upper() + b[1:]


def _fact(key, value, text, category, confidence, explicit=False) -> Optional[ExtractedFact]:
    if not key or not value or not text:
        return None
    return ExtractedFact(key, value, text, category, confidence, explicit)


def _parse_statement(sentence: str, explicit: bool) -> Optional[ExtractedFact]:
    """Parse one declarative sentence into at most one fact."""
    s = sentence.strip().rstrip(".!;")
    conf_hi = 0.95 if explicit else 0.85

    m = _RE_MY_ATTR.match(s)
    if m:
        attr = _valid_attr(m.group("attr"))
        val = clean_value(m.group("val"))
        if attr and val and attr != "name" and (explicit or _attr_is_stable(attr)):
            verb = "are" if m.group(0).lower().find(" are ") > 0 and attr.endswith("s") else "is"
            return _fact(slug(attr), val, f"User's {attr} {verb} {val}", "preference", conf_hi, explicit)
        return None

    m = _RE_LIKE.match(s)
    if m:
        val = clean_value(m.group("val"))
        if not val or re.search(r"\byou\b", val, re.IGNORECASE):
            return None
        first = val.lower().split()[0]
        if first in _BAD_LIKE_START or val.lower().startswith("the way"):
            return None
        verb = m.group("verb").lower()
        negative = verb in ("hate", "dislike")
        cls = "dislikes" if negative else "likes"
        verb_s = {"love": "loves", "like": "likes", "enjoy": "enjoys", "adore": "adores",
                  "prefer": "prefers", "hate": "hates", "dislike": "dislikes"}[verb]
        return _fact(f"{cls}:{slug(val)}", val, f"User {verb_s} {val}", "preference", 0.8, explicit)

    m = _RE_WORK_AT.match(s)
    if m and clean_value(m.group("val")):
        v = clean_value(m.group("val"))
        return _fact("workplace", v, f"User works at {v}", "personal", conf_hi, explicit)
    m = _RE_WORK_AS.match(s)
    if m and clean_value(m.group("val")):
        v = clean_value(m.group("val"))
        return _fact("job_title", v, f"User works as {_article(v)} {v}", "personal", conf_hi, explicit)

    m = _RE_ROLE.match(s)
    if m:
        v = clean_value(m.group("val"))
        if v and v.lower().split()[-1] in _ROLE_WORDS:
            return _fact("role", v, f"User is {_article(v)} {v}", "personal", 0.8, explicit)
        return None

    m = _RE_STUDY_AT.match(s)
    if m and clean_value(m.group("val")):
        v = clean_value(m.group("val"))
        return _fact("school", v, f"User studies at {v}", "personal", conf_hi, explicit)
    m = _RE_STUDY.match(s)
    if m and clean_value(m.group("val")):
        v = clean_value(m.group("val"))
        return _fact("studies", v, f"User studies {v}", "personal", 0.8, explicit)

    m = _RE_LIVE.match(s)
    if m and clean_value(m.group("val")):
        v = clean_value(m.group("val"))
        return _fact("city", v, f"User lives in {v}", "personal", conf_hi, explicit)
    m = _RE_FROM.match(s)
    if m:
        v = clean_value(m.group("val") or m.group("val2"))
        if v:
            return _fact("hometown", v, f"User is from {v}", "personal", 0.8, explicit)
        return None

    m = _RE_AGE.match(s)
    if m and 3 <= int(m.group("val")) <= 110:
        v = m.group("val")
        return _fact("age", v, f"User is {v} years old", "personal", 0.8, explicit)

    m = _RE_CODE_IN.match(s)
    if m and clean_value(m.group("val")):
        v = clean_value(m.group("val"))
        return _fact(f"uses:{slug(v)}", v, f"User codes in {v}", "skills", 0.8, explicit)
    m = _RE_USE.match(s)
    if m:
        v = clean_value(m.group("val"))
        if v and slug(v).split("_")[0] in _TECH_WORDS:
            return _fact(f"uses:{slug(v)}", v, f"User uses {v}", "skills", 0.75, explicit)
        return None
    m = _RE_PLAY.match(s)
    if m and m.group("val").lower() in _PLAYABLES:
        v = m.group("val").lower()
        return _fact(f"plays:{v}", v, f"User plays {v}", "personal", 0.75, explicit)

    return None


def extract_facts(text: str) -> List[ExtractedFact]:
    """
    Extract zero or more validated facts from one user utterance.
    Questions, imperatives and over-long inputs always return [].
    """
    raw = (text or "").strip()
    if not raw or len(raw) > 400:
        return []

    m = _RE_EXPLICIT.match(raw)
    if m:
        # A trailing "?" is fine for polite requests ("can you remember that I ...?");
        # the payload itself must still be a statement, not a question.
        body = m.group("body").strip().rstrip(".!;?")
        if speech_acts.is_question(body) or re.match(
                r"^(?:to|about|when|what|where|who|how|why|if|me)\b", body, re.IGNORECASE):
            return []
        facts = []
        for sentence in _RE_SPLIT.split(body):
            f = _parse_statement(_RE_LEADING_FILLER.sub("", sentence.strip()), explicit=True)
            if f:
                facts.append(f)
        if facts:
            return _dedupe(facts)
        if len(body.split()) < 2 or not clean_value(body):
            return []
        text3 = _third_person(body)
        return [ExtractedFact(f"note:{slug(' '.join(body.split()[:6]))}", body, text3,
                              "explicit", 0.9, True)]

    if not speech_acts.is_declarative(raw):
        return []

    facts = []
    for sentence in _RE_SPLIT.split(raw):
        s = _RE_LEADING_FILLER.sub("", sentence.strip())
        if not s or speech_acts.is_question(s):
            continue
        f = _parse_statement(s, explicit=False)
        if f:
            facts.append(f)
    return _dedupe(facts)


def _dedupe(facts: List[ExtractedFact]) -> List[ExtractedFact]:
    seen, out = set(), []
    for f in facts:
        if f.key not in seen:
            seen.add(f.key)
            out.append(f)
    return out


def looks_like_statement(text: str) -> bool:
    """True when the utterance is a fact-bearing statement (so no retrieval is needed)."""
    return bool(extract_facts(text))


def is_clean_fact_text(text: str) -> bool:
    """
    Validity check for stored fact text. Used when reading legacy memory so
    poisoned entries ("User said: ...", "User's name is What You") are never
    shown to the model.
    """
    t = (text or "").strip()
    if not t or "?" in t:
        return False
    low = t.lower()
    if low.startswith(("user said:", "user asked to remember:", "user asked:")):
        return False
    m = re.match(r"^user'?s name is (.+)$", t, re.IGNORECASE)
    if m and valid_name(m.group(1)) is None:
        return False
    m = re.match(r"^user wants to be called (.+)$", t, re.IGNORECASE)
    if m and valid_name(m.group(1)) is None:
        return False
    return True


def rewrite_legacy(text: str) -> Optional[str]:
    """Recover the original utterance from a legacy 'User said: ...' fact."""
    t = (text or "").strip()
    for prefix in ("User said:", "User asked to remember:"):
        if t.lower().startswith(prefix.lower()):
            inner = t[len(prefix):].strip()
            return inner if prefix.startswith("User said") else f"remember that {inner}"
    return None
