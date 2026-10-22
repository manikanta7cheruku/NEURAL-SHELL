"""
brain_modules/goals.py

Goal understanding: what the user is trying to ACHIEVE, not only what they
literally asked. Explicit goal statements ("I'm building a personal AI
assistant", "I want to learn Rust", "I need to finish the report by Friday")
become tracked goals. Relevant active goals are given to the model so it can
serve the purpose behind a request, and they feed Seven's questions.

Goals are never inferred silently: a goal exists only because the user said it.
"""

import re
from typing import List, Optional

from brain_modules import fact_extractor, speech_acts
from memory import learning_store

_GOAL_VERBS = {
    "build", "make", "create", "develop", "learn", "study", "finish", "complete", "write", "launch", "ship",
    "prepare", "improve", "start", "master", "pass", "apply", "lose", "save", "publish", "design", "plan",
    "become", "reach", "train", "practice", "get", "run", "release", "deliver", "submit", "read",
}
GOAL_VERBS = _GOAL_VERBS
_RE_PROJECT = re.compile(
    r"^i\s*(?:am|'m|\u2019m)\s+(?:currently\s+)?(?P<v>building|making|creating|developing|writing|designing|"
    r"launching|working on)\s+(?P<what>.+)$", re.IGNORECASE)
_RE_WANT = re.compile(
    r"^(?:i\s+(?:really\s+)?(?:want|need|have|plan|hope|wish|aim)\s+to|i'd\s+like\s+to|i\s+would\s+like\s+to|"
    r"my\s+goal\s+is\s+to|i\s*(?:am|'m)\s+trying\s+to|i\s*(?:am|'m)\s+going\s+to)\s+(?P<verb>[a-z]+)\s+(?P<what>.+)$",
    re.IGNORECASE)
_RE_LEARN = re.compile(
    r"^i\s*(?:am|'m|\u2019m)\s+(?:currently\s+)?(?P<v>learning|studying|preparing for|training for|practicing)\s+(?P<what>.+)$",
    re.IGNORECASE)
_RE_DONE = re.compile(r"^i\s+(?:just\s+)?(?:finished|completed|shipped|launched|published|passed)\s+(?P<what>.+)$", re.IGNORECASE)
_RE_DROP = re.compile(r"^(?:forget|drop|cancel)\s+(?:about\s+)?(?:my\s+)?(?:goal\s+)?(?:of\s+)?(?P<what>.+)$|"
                      r"^i\s+(?:gave up on|am no longer|'m no longer|quit)\s+(?P<what2>.+)$", re.IGNORECASE)
_RE_DEADLINE = re.compile(r"\s+(?:by|before|until)\s+(?P<d>[A-Za-z0-9 ,]{2,24})$", re.IGNORECASE)
_Q_GOALS = ("what am i working on", "what are my goals", "what is my goal", "what projects am i building",
            "what am i building", "what am i trying to do", "what are my projects", "what are my current goals")
_VERB_PREFIX = {"building": "build", "making": "make", "creating": "create", "developing": "develop",
                "writing": "write", "designing": "design", "launching": "launch", "working on": "work on",
                "learning": "learn", "studying": "study", "preparing for": "prepare for",
                "training for": "train for", "practicing": "practice"}


class GoalCandidate:
    def __init__(self, title: str, deadline: Optional[str] = None):
        self.title, self.deadline = title, deadline
        self.key = fact_extractor.slug(title)


def extract_goals(text: str) -> List[GoalCandidate]:
    out: List[GoalCandidate] = []
    for sentence in fact_extractor.split_sentences(text):
        s = sentence.strip().rstrip(".!;")
        if not s or speech_acts.is_question(s) or len(s.split()) > 26:
            continue
        s = re.sub(r"^(?:remember that|also|and|actually)\s+", "", s, flags=re.IGNORECASE)
        title = None
        m = _RE_PROJECT.match(s) or _RE_LEARN.match(s)
        if m:
            title = f"{_VERB_PREFIX[m.group('v').lower()]} {m.group('what')}"
        else:
            m = _RE_WANT.match(s)
            if m and m.group("verb").lower() in _GOAL_VERBS:
                title = f"{m.group('verb').lower()} {m.group('what')}"
        if not title:
            continue
        deadline = None
        d = _RE_DEADLINE.search(title)
        if d:
            deadline, title = d.group("d").strip(), title[:d.start()]
        title = title.strip(" ,")
        if 2 <= len(title.split()) <= 18 and fact_extractor.clean_value(title):
            out.append(GoalCandidate(title, deadline))
    return out


def learn(speaker_key: str, text: str, source_msg_id: Optional[int] = None) -> List[dict]:
    """Store explicit goals from a message. Returns what was created or refreshed."""
    results = []
    for g in extract_goals(text):
        gid, status = learning_store.upsert_goal(speaker_key, g.key, g.title, deadline_text=g.deadline,
                                                 source_msg_id=source_msg_id)
        results.append({"id": gid, "title": g.title, "status": status, "deadline": g.deadline})
    return results


def handle_lifecycle(speaker_key: str, text: str) -> Optional[str]:
    """'What am I working on' / 'what are my goals'. Returns a reply or None."""
    s = (text or "").strip().rstrip(".!?")
    low = speech_acts.normalize(s)
    if any(low == q or low.startswith(q) for q in _Q_GOALS):
        goals = learning_store.list_goals(speaker_key)
        if not goals:
            return "You haven't told me about any goals yet. What are you working on?"
        titles = [g["title"] + (f" (by {g['deadline_text']})" if g.get("deadline_text") else "") for g in goals[:5]]
        return "You're working on: " + "; ".join(titles) + "."
    return None      # completing / dropping goals is brain_modules/lifecycle.py's job


def relevant(speaker_key: str, text: str, k: int = 2) -> List[dict]:
    """Active goals worth giving the model for this message."""
    goals = learning_store.list_goals(speaker_key)
    if not goals:
        return []
    wanted = learning_store._tokens(text)
    scored = []
    for g in goals:
        have = learning_store._tokens(g["title"])
        inter = wanted & have
        sim = len(inter) / max(1, min(len(wanted), len(have))) if inter and any(len(t) > 3 for t in inter) else 0.0
        scored.append((sim, g))
    hits = [g for sim, g in sorted(scored, key=lambda x: -x[0]) if sim >= 0.2][:k]
    if not hits and len(goals) <= 2 and re.search(r"\b(my|the)\s+(project|app|goal|plan|work)\b|\bit\b", text.lower()):
        hits = goals[:1]
    return hits
