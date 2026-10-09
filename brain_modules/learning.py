"""
brain_modules/learning.py

How Seven adapts to a specific person, entirely locally.

WHAT IT LEARNS:
    - Facts the user states (via fact_extractor + memory/fact_service).
    - Corrections, which replace the old value rather than piling up.
    - How the user wants Seven to talk: shorter or more detailed answers,
      more or fewer jokes, casual or formal, and whether to use their name.

HOW STYLE IS LEARNED:
    Only from EXPLICIT feedback ("keep answers short", "stop joking"). It is
    stored per speaker in the facts store under category "style" and applied
    to the system prompt on the next turn. Nothing is inferred silently and
    nothing leaves the machine. Style rows are never indexed into the
    semantic store, so they cannot surface as "facts" in conversation.
"""

import logging
import re
import threading
import time
from typing import Dict, List, Tuple

_log = logging.getLogger("seven.learning")

DEFAULT_PROFILE = {"verbosity": "normal", "humor_bias": 0, "use_name": True, "formality": "casual"}

_PATTERNS: List[Tuple[str, str, str]] = [
    # (field, value, regex)
    ("verbosity", "brief", r"\b(?:be|keep (?:it|answers?|replies|responses))\s+(?:more\s+)?(?:brief|short|concise)\b"),
    ("verbosity", "brief", r"\bshorter (?:answers|replies|responses)\b"),
    ("verbosity", "brief", r"\b(?:too long|stop rambling|talk less|less talk(?:ing)?)\b"),
    ("verbosity", "brief", r"\bkeep it short\b|\bjust the answer\b"),
    ("verbosity", "detailed", r"\b(?:be )?more detailed\b|\blonger (?:answers|replies|responses)\b"),
    ("verbosity", "detailed", r"\bexplain (?:things )?in (?:more )?detail\b|\balways explain\b"),
    ("humor_delta", "-30", r"\b(?:stop|quit) (?:joking|the jokes|being funny|with the jokes)\b|\bno (?:more )?jokes\b"),
    ("humor_delta", "20", r"\b(?:be )?funnier\b|\bmore jokes\b|\bjoke more\b|\bmore humou?r\b"),
    ("formality", "casual", r"\b(?:be )?(?:more )?casual\b|\bless formal\b|\btalk (?:to me )?normally\b"),
    ("formality", "formal", r"\b(?:be )?more formal\b|\bbe professional\b"),
    ("use_name", "false", r"\b(?:stop|do not|dont|don't) (?:calling|call|using|use|saying) my name\b"),
    ("use_name", "true", r"\b(?:use|say|call me by) my name\b"),
]

_ACKS = {
    ("verbosity", "brief"): "Got it. Short and direct from now on.",
    ("verbosity", "detailed"): "Understood. I'll go deeper on answers.",
    ("humor_delta", "-30"): "Fine. Jokes off.",
    ("humor_delta", "20"): "Noted. More jokes. You asked for it.",
    ("formality", "casual"): "Okay. Keeping it relaxed.",
    ("formality", "formal"): "Understood. I'll keep it professional.",
    ("use_name", "false"): "Okay, no more names.",
    ("use_name", "true"): "Sure. I'll use your name.",
}

_cache: Dict[str, Tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_TTL_SECONDS = 30.0


def detect_style_feedback(text: str) -> List[Tuple[str, str]]:
    """Return [(field, value), ...] for every explicit style request in the text."""
    t = (text or "").lower()
    found = []
    for field, value, pattern in _PATTERNS:
        if re.search(pattern, t) and (field, value) not in found:
            found.append((field, value))
    return found


def acknowledgement(signals: List[Tuple[str, str]]) -> str:
    """Short natural confirmation for the first recognised signal."""
    for sig in signals:
        if sig in _ACKS:
            return _ACKS[sig]
    return "Got it."


def _key_for(field: str) -> str:
    return "style:humor_bias" if field == "humor_delta" else f"style:{field}"


def apply_style_signals(speaker_key: str, signals: List[Tuple[str, str]]) -> None:
    """Persist style signals for a speaker. Humor deltas accumulate within bounds."""
    from memory import facts_store
    current = get_profile(speaker_key, use_cache=False)
    for field, value in signals:
        if field == "humor_delta":
            new = max(-60, min(40, int(current["humor_bias"]) + int(value)))
            current["humor_bias"] = new
            stored = str(new)
        else:
            stored = value
            current[field] = (value == "true") if field == "use_name" else value
        facts_store.upsert_fact(speaker_key, _key_for(field), stored,
                                f"style {field}={stored}", category="style", confidence=0.9)
    with _cache_lock:
        _cache[speaker_key] = (time.time(), dict(current))


def get_profile(speaker_key: str, use_cache: bool = True) -> dict:
    """Return the speaker's learned style profile (defaults when nothing learned)."""
    now = time.time()
    if use_cache:
        with _cache_lock:
            hit = _cache.get(speaker_key)
            if hit and now - hit[0] < _TTL_SECONDS:
                return dict(hit[1])
    profile = dict(DEFAULT_PROFILE)
    try:
        from memory import facts_store
        for row in facts_store.get_facts(speaker_id=speaker_key, category="style", limit=50):
            key, val = row.get("key"), row.get("raw_value")
            if key == "style:verbosity" and val in ("brief", "normal", "detailed"):
                profile["verbosity"] = val
            elif key == "style:humor_bias":
                profile["humor_bias"] = int(val)
            elif key == "style:formality" and val in ("casual", "formal"):
                profile["formality"] = val
            elif key == "style:use_name":
                profile["use_name"] = (val == "true")
    except Exception as exc:
        _log.debug("style profile read failed: %s", exc)
    with _cache_lock:
        _cache[speaker_key] = (now, dict(profile))
    return profile


def clear_cache() -> None:
    """Drop cached profiles (session reset, tests)."""
    with _cache_lock:
        _cache.clear()
