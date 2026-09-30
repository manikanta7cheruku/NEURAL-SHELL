"""
=============================================================================
brain_modules/correction_detector.py

Detects correction intents in user input.
    "actually, it's PostgreSQL"           -> correction
    "I meant Chrome, not Firefox"         -> correction with old and new values
    "sorry, my name is really Alex"       -> correction
    "not X, it's Y"                       -> correction
    "correction: use port 8080"           -> explicit correction

Returns structured payload used by idle_worker to update the SQLite fact store
and mark the old ChromaDB entry as superseded.
=============================================================================
"""

import re
from typing import Optional, Dict, Any


_CORRECTION_STARTERS = [
    "actually",
    "correction",
    "sorry",
    "i meant",
    "i actually meant",
    "no wait",
    "wait no",
    "let me correct",
    "let me clarify",
    "to clarify",
    "scratch that",
    "forget that",
    "no i said",
    "no its",
    "no it is",
    "no its actually",
]

_REPLACEMENT_PATTERNS = [
    # "not X, it's Y"
    re.compile(r"\bnot\s+([\w\s]+?)[,.]?\s+(?:it'?s|its|it is|actually)\s+([\w\s]+)", re.IGNORECASE),
    # "X, not Y"
    re.compile(r"\b([\w\s]+?)[,.]?\s+not\s+([\w\s]+)", re.IGNORECASE),
    # "changed from X to Y"
    re.compile(r"\bchanged from\s+([\w\s]+?)\s+to\s+([\w\s]+)", re.IGNORECASE),
    # "switched from X to Y"
    re.compile(r"\bswitched from\s+([\w\s]+?)\s+to\s+([\w\s]+)", re.IGNORECASE),
    # "no longer X, now Y"
    re.compile(r"\bno longer\s+([\w\s]+?)[,.]?\s+now\s+([\w\s]+)", re.IGNORECASE),
]


def is_correction(text: str) -> bool:
    """Quick boolean check for correction intent."""
    if not text:
        return False
    lowered = text.lower().strip()
    for starter in _CORRECTION_STARTERS:
        if lowered.startswith(starter):
            return True
    if "not" in lowered and any(w in lowered for w in ("it's", "its", "actually", "instead")):
        return True
    return False


def detect_correction(text: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes text for correction intent and extracts old/new values if present.

    Returns:
        None if no correction detected.
        Dict with keys:
            is_correction : True
            starter       : matched starter phrase or None
            old_value     : detected prior value or None
            new_value     : detected new value or None
            raw_text      : original input
    """
    if not text or not text.strip():
        return None

    lowered = text.lower().strip()
    matched_starter = None
    for starter in _CORRECTION_STARTERS:
        if lowered.startswith(starter):
            matched_starter = starter
            break

    old_value = None
    new_value = None
    for pattern in _REPLACEMENT_PATTERNS:
        m = pattern.search(text)
        if m:
            old_value = m.group(1).strip().rstrip(".,!?")
            new_value = m.group(2).strip().rstrip(".,!?")
            break

    if not matched_starter and not old_value:
        return None

    return {
        "is_correction": True,
        "starter": matched_starter,
        "old_value": old_value,
        "new_value": new_value,
        "raw_text": text.strip(),
    }