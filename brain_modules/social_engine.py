"""
brain_modules/social_engine.py

Instant, context-aware replies for purely social input: greetings, "how are
you", thanks, goodbyes, "are you there" and plain pushback ("that's wrong").

WHY THIS IS NOT THE LLM:
    A greeting must come back in microseconds and must never drag stored
    facts or old conversation into the reply. Routing "Hey" through a small
    model is what caused the Rio de Janeiro / port 7777 context bleed.

WHY THIS IS NOT A FIXED SCRIPT:
    Replies depend on time of day, how many greetings in a row the user has
    sent (the streak), and whether it is natural to use the user's name. A
    reply is never repeated twice in a row. By the fourth "hello" Seven dryly
    asks for a real topic, the way a person would.
"""

import random
import threading
import time
from datetime import datetime
from typing import Optional

from brain_modules import speech_acts

STREAK_RESET_SECONDS = 600

_lock = threading.Lock()
_state = {}   # speaker key -> {"streak": int, "last_ts": float, "last_reply": str}
_rng = random.Random()

_CHECKIN = frozenset({
    "how are you", "how are you doing", "how is it going", "how you doing",
    "how have you been", "what is up", "you good", "you okay", "how are things",
    "how is everything",
})
_THANKS = frozenset({
    "thanks", "thank you", "thank you so much", "thanks a lot", "thx", "ty",
    "cheers", "appreciate it", "much appreciated", "many thanks",
})
_FAREWELL = frozenset({
    "bye", "goodbye", "see you", "see you later", "see ya", "later", "cya",
    "good night", "goodnight", "night", "gotta go", "i have to go", "i am off",
    "talk to you later", "ttyl",
})
_PRESENCE = frozenset({
    "you there", "are you there", "are you still there", "seven",
    "anyone there", "are you awake",
})
_PUSHBACK = frozenset({
    "that is wrong", "that is not right", "you are wrong", "wrong", "incorrect",
    "that is incorrect", "that is not correct", "not what i asked",
    "that is not what i asked", "you got that wrong", "no that is wrong",
})

_GREET_PREFIX = ("hey seven ", "hi seven ", "hello seven ", "hey ", "hi ", "hello ", "yo ")


def seed(value) -> None:
    """Seed the internal RNG. Used by tests for deterministic output."""
    _rng.seed(value)


def reset(key: str = None) -> None:
    """Forget greeting streaks for one speaker, or for everyone."""
    with _lock:
        if key is None:
            _state.clear()
        else:
            _state.pop(key, None)


def _strip_seven(norm: str) -> str:
    """Drop a trailing address to Seven: 'thanks seven' -> 'thanks'."""
    if norm.endswith(" seven"):
        return norm[: -len(" seven")]
    return norm


def classify(norm: str) -> Optional[str]:
    """Return the social category of an utterance, or None if it is substantive."""
    if not norm or len(norm.split()) > 8:
        return None
    if speech_acts.is_greeting(norm):
        return "greeting"
    base = _strip_seven(norm)
    for prefix in _GREET_PREFIX:
        if base.startswith(prefix):
            rest = base[len(prefix):].strip()
            if rest in _CHECKIN:
                return "checkin"
    if base in _CHECKIN:
        return "checkin"
    if base in _THANKS:
        return "thanks"
    if base in _FAREWELL:
        return "farewell"
    if norm in _PRESENCE or base in _PRESENCE:
        return "presence"
    if norm in _PUSHBACK:
        return "pushback"
    return None


def _entry(key: str) -> dict:
    return _state.setdefault(key, {"streak": 0, "last_ts": 0.0, "last_reply": ""})


def _pick(pool: list, st: dict) -> str:
    """Random choice that never repeats the previous reply."""
    options = [p for p in pool if p != st["last_reply"]] or pool
    choice = _rng.choice(options)
    st["last_reply"] = choice
    return choice


def _greeting_pool(streak: int, norm: str, name: str, hour: int) -> list:
    """Replies get shorter and drier as the streak grows; the 4th asks for a topic."""
    if streak <= 1:
        pool = ["Hey. What's up?", "Hey. What are we doing?",
                "Hey, what do you need?", "Yo. What's going on?"]
        if norm.startswith("good morning"):
            pool = ["Morning. What's the plan?", "Morning. What's up?"]
        elif norm.startswith("good afternoon"):
            pool = ["Afternoon. What's up?", "Afternoon. What are we doing?"]
        elif norm.startswith("good evening"):
            pool = ["Evening. What's up?", "Evening. What are we doing?"]
        elif hour < 5:
            pool.append("Still up? What's going on?")
        elif hour < 12:
            pool.append("Morning. What's up?")
        elif hour >= 18:
            pool.append("Evening. What's up?")
        if name:
            pool += [f"Hey {name}. What's up?", f"Hey {name}. What do you need?"]
        return pool
    if streak == 2:
        return ["Hey again.", "Hi again.", "Yes?", "Hey. Still here."]
    if streak == 3:
        return ["Yep.", "Hello.", "I'm listening.", "Mm-hm."]
    if streak == 4:
        return [
            "That's four hellos. Give me something real to work on.",
            "Four. I'm flattered, but what do you actually need?",
            "Okay, four times. What's the real topic?",
        ]
    return [
        "Pick a topic whenever you're ready.",
        "I'm here. Say something and I'll respond.",
        "Whenever you have an actual question, go ahead.",
    ]


def respond(key: str, norm: str, user_name: str = "", now: float = None,
            hour: int = None) -> Optional[str]:
    """
    Produce a social reply, or None when the input is not purely social.
    A non-social input resets the greeting streak so the next "hey" starts fresh.
    """
    kind = classify(norm)
    ts = time.time() if now is None else now
    h = datetime.now().hour if hour is None else hour
    name = (user_name or "").strip()
    if name.lower() in ("there", "admin", "default", "unknown"):
        name = ""

    with _lock:
        st = _entry(key)
        if kind is None:
            st["streak"] = 0
            return None

        if kind == "greeting":
            if ts - st["last_ts"] > STREAK_RESET_SECONDS:
                st["streak"] = 0
            st["streak"] += 1
            st["last_ts"] = ts
            return _pick(_greeting_pool(st["streak"], norm, name, h), st)

        st["last_ts"] = ts
        if kind == "checkin":
            pool = ["Running smooth. You?", "Good. What's going on with you?",
                    "Can't complain. What's up?", "All systems fine. How about you?"]
        elif kind == "thanks":
            pool = ["Anytime.", "You got it.", "No problem.", "Yep."]
        elif kind == "farewell":
            if "night" in norm:
                pool = ["Night.", "Sleep well.", "Night. I'll be here."]
            else:
                pool = ["Later.", "See you.", "Catch you later.", "Take it easy."]
            if name:
                pool.append(f"Later, {name}.")
        elif kind == "presence":
            pool = ["Here.", "Right here.", "Still here."]
        else:  # pushback
            pool = ["Fair. What did you actually need?",
                    "My mistake. Say it again and I'll get it right.",
                    "Noted. Give me the right version.",
                    "Okay. Where did I go wrong?"]
        return _pick(pool, st)
