"""
brain_modules/speech_acts.py

Text normalisation and light speech-act classification shared by the brain.

WHY THIS EXISTS:
    The old code matched triggers with `"hi" in text`, which fires on
    "history" and "this". Everything here works on whole words so that
    "what is a business model" is never mistaken for a question about
    Seven's own model, and "how do I stop a process" is never mistaken for
    a command to stop listening.
"""

import re

_CONTRACTIONS = {
    "what's": "what is", "whats": "what is", "who's": "who is", "whos": "who is",
    "where's": "where is", "wheres": "where is", "how's": "how is", "hows": "how is",
    "when's": "when is", "whens": "when is", "that's": "that is", "thats": "that is",
    "it's": "it is", "i'm": "i am", "im": "i am", "you're": "you are",
    "youre": "you are", "we're": "we are", "they're": "they are",
    "don't": "do not", "dont": "do not", "doesn't": "does not", "doesnt": "does not",
    "didn't": "did not", "didnt": "did not", "can't": "can not", "cant": "can not",
    "won't": "will not", "wont": "will not", "isn't": "is not", "isnt": "is not",
    "aren't": "are not", "arent": "are not", "i've": "i have", "i'll": "i will",
    "let's": "let us",
}

_QUESTION_STARTERS = frozenset({
    "what", "who", "whom", "whose", "which", "when", "where", "why", "how",
    "is", "are", "am", "was", "were", "do", "does", "did", "can", "could",
    "will", "would", "should", "shall", "may", "might", "have", "has", "had",
})

# Imperatives: requests, never declarative statements about the user.
_REQUEST_STARTERS = frozenset({
    "tell", "explain", "define", "describe", "list", "show", "give", "open",
    "close", "play", "set", "turn", "find", "search", "write", "make", "create",
})

_GREETING_RE = re.compile(
    r"(?:h+e+y+|h+i+|h+e+l+l*o+|h+o+l+a+|y+o+|s+u+p+|howdy|hiya|heya|greetings|"
    r"good (?:morning|afternoon|evening))"
    r"(?: (?:there|seven|you|everyone|buddy|friend|man|bro))?"
)


def normalize(text) -> str:
    """
    Lowercase, expand contractions, drop punctuation, collapse whitespace.
    "What's the time?" -> "what is the time"
    """
    t = (text or "").lower()
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    out = []
    for tok in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", t):
        mapped = _CONTRACTIONS.get(tok)
        if mapped:
            out.extend(mapped.split())
        else:
            out.append(tok.replace("'", ""))
    return " ".join(out)


def words(norm: str) -> list:
    """Split a normalised string into words."""
    return norm.split() if norm else []


def has_phrase(norm: str, phrase: str) -> bool:
    """Whole-word phrase containment: has_phrase('a hi there', 'hi') is True,
    has_phrase('history', 'hi') is False."""
    return f" {phrase} " in f" {norm} "


def has_any_phrase(norm: str, phrases) -> bool:
    """True when any phrase occurs as whole words."""
    return any(has_phrase(norm, p) for p in phrases)


def is_question(raw: str, norm: str = None) -> bool:
    """True for interrogatives, including ones without a question mark."""
    raw = (raw or "").strip()
    if raw.endswith("?"):
        return True
    n = norm if norm is not None else normalize(raw)
    first = n.split(" ", 1)[0] if n else ""
    return first in _QUESTION_STARTERS


def is_declarative(raw: str) -> bool:
    """True only for statements: not a question and not an imperative request."""
    if not (raw or "").strip():
        return False
    n = normalize(raw)
    first = n.split(" ", 1)[0] if n else ""
    if is_question(raw, n) or first in _REQUEST_STARTERS:
        return False
    return True


def is_greeting(norm: str) -> bool:
    """True when the whole utterance is a greeting ("hey", "hello there")."""
    return bool(norm) and _GREETING_RE.fullmatch(norm) is not None


def jaccard(a: str, b: str) -> float:
    """Token Jaccard similarity of two normalised strings."""
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
