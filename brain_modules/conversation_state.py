"""
brain_modules/conversation_state.py

Working memory for ONE conversation: what is being talked about, which
entities are in play, what Seven last recalled, what it asked and is waiting
on, and what its last actions did.

It is keyed by "<speaker>#<conversation id>", so a new chat starts empty while
long-term facts stay available. Nothing here is a fact about the user; it only
helps Seven understand the next message ("I love that movie").
"""

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_KIND_WORDS = {
    "movie": "movie", "film": "movie", "song": "song", "track": "song", "book": "book", "novel": "book",
    "show": "show", "series": "show", "game": "game", "language": "language", "framework": "framework",
    "app": "app", "tool": "tool", "place": "place", "city": "place", "band": "band", "album": "album",
    "podcast": "podcast", "food": "food", "dish": "food", "editor": "editor",
}
_NOUNS = "|".join(_KIND_WORDS)
_NOT_ENTITY = {
    "I", "The", "A", "An", "What", "Who", "How", "Why", "When", "Where", "Which", "Do", "Does", "Is", "Are",
    "Can", "Could", "Would", "Should", "Tell", "Please", "Yes", "No", "Ok", "Okay", "Hey", "Hello", "Hi",
    "And", "But", "Or", "So", "It", "That", "This", "My", "Seven", "Remember", "Actually", "Also", "Sure",
    "Thanks", "Thank", "Today", "Tomorrow", "Yesterday", "Maybe", "Well", "Now", "Then", "Here", "There",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "AI", "OK", "If", "You",
    "All", "Just", "Everything", "Anything", "Something", "Nothing", "Some", "Any", "Every", "Each", "None",
    "Let", "Lets", "Let's", "Give", "Show", "Find", "Open", "Close", "Set", "Turn", "Make", "Put", "Add", "Remind",
    "Start", "Stop", "Go", "Get", "Not", "Very", "Really", "Great", "Good", "Nice", "Cool", "Wow", "Oh", "Hmm",
    "Sorry", "We", "They", "He", "She", "Our", "Your", "Their", "His", "Her", "Its", "These", "Those", "In", "On",
    "At", "For", "With", "From", "By", "Of", "To", "As", "Because", "Since", "While", "After", "Before", "Again",
    "More", "Most", "Less", "Still", "Even", "Only", "Also", "Too", "Why", "Was", "Were", "Will", "Did", "Have",
    "Has", "Had", "Am", "Be", "Being", "Lol", "Haha", "Ya", "Yeah", "Yep", "Nope", "Me", "Him", "Them", "Us",
    "Explain", "Describe", "Write", "Create", "Help", "Check", "Tell", "Think", "Know", "Want", "Need", "Like",
}
_LEAD_VERBS = {"compare", "tell", "show", "explain", "give", "find", "open", "play", "describe", "list", "write",
               "make", "create", "summarize", "recommend", "suggest", "watch", "read", "see", "check", "help"}
_PRONOUNS = {"it", "that", "this", "them", "you", "me", "him", "her", "us", "one", "something", "anything"}
_RE_REF = re.compile(rf"\b(?:that|this|the same|the)\s+(?P<noun>{_NOUNS})\b", re.IGNORECASE)
_RE_BARE = re.compile(r"\b(?P<lead>i\s+(?:really\s+|totally\s+)?(?:love|like|enjoy|hate|dislike|adore)|"
                      r"what about|tell me more about|more about)\s+(?P<pron>it|that|this)\b(?!\s+\w)", re.IGNORECASE)
_YES = ("yes", "yeah", "yep", "yup", "sure", "correct", "right", "exactly", "definitely", "absolutely",
        "of course", "please do", "go ahead", "do it", "that's right", "thats right")
_NO = ("no", "nope", "nah", "not really", "dont", "do not", "never mind", "nevermind", "no thanks", "not exactly")


@dataclass
class Entity:
    name: str
    kind: Optional[str]
    turn: int
    source: str


@dataclass
class Pending:
    type: str
    data: Dict[str, Any]
    turn: int
    ttl: int = 4


@dataclass
class Resolution:
    text: str
    original: str
    substitutions: List[Tuple[str, str]] = field(default_factory=list)
    kind: Optional[str] = None
    ambiguous: List[str] = field(default_factory=list)


@dataclass
class State:
    entities: List[Entity] = field(default_factory=list)
    topic: Optional[Entity] = None
    turn: int = 0
    pending: Optional[Pending] = None
    last_recalled: Optional[Dict[str, Any]] = None
    last_receipts: List[Dict[str, Any]] = field(default_factory=list)
    last_failed_open: Optional[Tuple[str, int]] = None
    ignored: int = 0
    last_question_turn: int = -100
    last_overview_turn: Optional[int] = None     # when Seven last listed its abilities in this chat
    last_adjustable: Optional[Dict[str, Any]] = None   # last action a bare number can adjust (followups.py)
    overview_count: int = 0                     # how many times it was asked, so repeats are worded differently
    trace: Dict[str, Any] = field(default_factory=dict)
    last_used: float = 0.0


_lock = threading.Lock()
_states: Dict[str, State] = {}
_MAX_STATES = 300


def get(key: str) -> State:
    with _lock:
        st = _states.get(key)
        if st is None:
            if len(_states) >= _MAX_STATES:
                oldest = min(_states, key=lambda k: _states[k].last_used)
                _states.pop(oldest, None)
            st = _states[key] = State()
        st.last_used = time.time()
        return st


def reset(key: Optional[str] = None) -> None:
    with _lock:
        if key is None:
            _states.clear()
        else:
            _states.pop(key, None)


def extract_entities(text: str) -> List[Tuple[str, Optional[str]]]:
    """Salient named things in a sentence: quoted, Title Case, or after 'about/called'."""
    found: List[Tuple[str, Optional[str]]] = []
    seen = set()

    def add(name: str, kind: Optional[str] = None):
        name = name.strip(" .,!?;:'\"")
        if len(name) < 2 or name in _NOT_ENTITY or name.lower() in _PRONOUNS or name.lower() in seen:
            return
        seen.add(name.lower())
        found.append((name, kind))

    for q in re.findall(r'["\u201c]([^"\u201d]{2,40})["\u201d]', text):
        add(q)
    for m in re.finditer(rf"\b(?:the\s+)?(?P<kind>{_NOUNS})\s+(?:called\s+|named\s+)?(?P<name>[A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*){{0,3}})",
                         text):
        add(m.group("name"), _KIND_WORDS[m.group("kind").lower()])
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9'\-]*(?:\s+[A-Z][A-Za-z0-9'\-]*){0,3}", text):
        words = m.group(0).split()
        while len(words) > 1 and (words[0].lower() in _LEAD_VERBS or words[0] in _NOT_ENTITY):
            words = words[1:]
        add(" ".join(words))
    for m in re.finditer(r"\b(?:about|called|named)\s+(?:the\s+)?([A-Za-z0-9][\w\-]*(?:\s[A-Za-z0-9][\w\-]*){0,2})", text):
        w = m.group(1)
        if w.split()[0].lower() not in _PRONOUNS | {"the", "a", "an", "my", "your", "how", "what", "why"}:
            add(w)
    return found


def observe_user(st: State, text: str) -> None:
    """Record entities from the user's message; the most salient becomes the topic."""
    st.turn += 1
    ents = extract_entities(text)
    for name, kind in ents:
        st.entities.append(Entity(name, kind, st.turn, "user"))
    st.entities = st.entities[-14:]
    distinct = list(dict.fromkeys(n.lower() for n, _k in ents))
    if len(distinct) == 1:
        name, kind = ents[0]
        st.topic = Entity(name, kind, st.turn, "user")
    elif len(distinct) > 1:
        st.topic = None          # several candidates: a later "that one" must be clarified


def observe_reply(st: State, text: str) -> None:
    """Seven's own words never replace the user's topic, but they do add candidates."""
    for name, kind in extract_entities(text)[:4]:
        st.entities.append(Entity(name, kind, st.turn, "seven"))
    st.entities = st.entities[-14:]


def resolve(text: str, st: State) -> Resolution:
    """Replace 'that movie' / 'it' with the entity being discussed, or flag ambiguity."""
    res = Resolution(text=text, original=text)

    def pick(kind: Optional[str]):
        topic = st.topic
        if topic and st.turn - topic.turn <= 4 and (topic.kind in (None, kind) or kind is None):
            return topic
        recent = [e for e in st.entities if e.source == "user" and st.turn - e.turn <= 4
                  and (kind is None or e.kind in (None, kind))]
        names = list(dict.fromkeys(e.name for e in recent))
        if len(names) == 1:
            return recent[-1]
        if len(names) > 1:
            res.ambiguous = names[:3]
        return None

    m = _RE_REF.search(text)
    if m:
        kind = _KIND_WORDS[m.group("noun").lower()]
        ent = pick(kind)
        if ent:
            res.text = text[:m.start()] + ent.name + text[m.end():]
            res.substitutions.append((m.group(0), ent.name))
            res.kind = kind
            if ent.kind is None:
                ent.kind = kind
        return res
    m = _RE_BARE.search(text)
    if m:
        ent = pick(None)
        if ent:
            res.text = text[:m.start("pron")] + ent.name + text[m.end("pron"):]
            res.substitutions.append((m.group("pron"), ent.name))
            res.kind = ent.kind
    return res


def set_pending(st: State, type_: str, data: Optional[dict] = None, ttl: int = 4) -> None:
    st.pending = Pending(type_, data or {}, st.turn, ttl)


def active_pending(st: State) -> Optional[Pending]:
    if st.pending and st.turn - st.pending.turn > st.pending.ttl:
        st.pending = None
    return st.pending


def classify_answer(text: str) -> str:
    t = re.sub(r"[^a-z' ]", "", (text or "").lower()).strip()
    if not t:
        return "other"
    for y in _YES:
        if t == y or t.startswith(y + " "):
            return "yes"
    for n in _NO:
        if t == n or t.startswith(n + " "):
            return "no"
    return "other"
