"""
brain_modules/repetition_detector.py

Handles a user asking the same question again, the way a person would:
repeat the answer briefly, with a dry remark if it keeps happening.

BUGS FIXED IN THIS REWRITE:
    - The old version replied "I literally just answered that" WITHOUT the
      answer, so the user got nothing useful.
    - It contained a hardcoded test name ("Still 77").
    - It fired on commands and live-data questions ("what time is it")
      where asking again is perfectly reasonable.

Scope is deliberately narrow: only genuine questions of three or more words,
only when the previous turns were near-identical, never for live data.
Greetings are handled by social_engine, not here.
"""

import random
import re
from typing import Optional

from brain_modules import memory_gate, speech_acts

_SIMILARITY = 0.85
_INFO_REQUESTS = frozenset({"explain", "tell", "describe", "define"})
_FAILURE_MARKERS = ("hiccup", "can't reach", "took too long", "went wrong", "not running", "not installed")


def _first_sentences(text: str, limit: int = 180) -> str:
    """Return the opening sentence(s) of a prior answer, capped for speech."""
    t = re.sub(r"###\w+:\s*\S+", "", text or "").strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", t)
    out = parts[0]
    if len(out) < 60 and len(parts) > 1:
        out = f"{out} {parts[1]}"
    return out[:limit].rstrip()


def _looks_like_failure(answer: str) -> bool:
    low = answer.lower()
    return any(m in low for m in _FAILURE_MARKERS)


def detect_repetition(user_input: str, speaker_key: str) -> Optional[str]:
    """
    Return a repeat-aware reply, or None when the question is not a repeat.

    ARGS:
        user_input:  raw user text
        speaker_key: key from session.resolve_key()
    """
    from brain_modules.conversation_thread import ConversationThread

    norm = speech_acts.normalize(user_input)
    first = norm.split(" ", 1)[0] if norm else ""
    if len(norm.split()) < 3 or not (
            speech_acts.is_question(user_input, norm) or first in _INFO_REQUESTS):
        return None
    if memory_gate.live_topic(norm) or speech_acts.has_any_phrase(
            norm, ("what time", "what day", "what date", "battery", "volume")):
        return None

    turns = ConversationThread.get_turns(speaker_key, limit=6)
    if not turns:
        return None

    count, prior = 0, None
    for prior_user, prior_resp in reversed(turns):
        if speech_acts.jaccard(norm, speech_acts.normalize(prior_user)) >= _SIMILARITY:
            count += 1
            if prior is None:
                prior = prior_resp
        else:
            break
    if count == 0:
        return None

    answer = _first_sentences(prior)
    if not answer or _looks_like_failure(answer):
        return None

    if count == 1:
        pool = [f"Same answer as a moment ago: {answer}", f"Like I said: {answer}", f"As before: {answer}"]
    elif count == 2:
        pool = [f"Still the same: {answer}", f"Same question, same answer. {answer}"]
    else:
        pool = [f"{answer} Ask me something new and I'll have something new to say.",
                f"Still: {answer} Want to try a different question?"]
    return random.choice(pool)
