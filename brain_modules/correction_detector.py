"""
brain_modules/correction_detector.py

Detects when the user corrects a fact ("actually it's Vue, not React").

BUGS FIXED IN THIS REWRITE:
    1. Reversed values. "I meant Chrome, not Firefox" was parsed as
       old=Chrome, new=Firefox, so the WRONG value overwrote the right one.
    2. Loose pattern. The old "X not Y" pattern matched ordinary sentences
       such as "I do not like pizza" (old="I do", new="like pizza"), and the
       idle worker then superseded any stored fact containing "i do" with
       that garbage. This was a direct source of memory poisoning.
    3. A leading "actually," or "sorry," on a QUESTION counted as a correction
       and shifted Seven's tone. Questions are never corrections now.

A correction needs either an explicit contrast ("not X, it's Y"), a
"from X to Y" change, or a correction starter. Values are validated.
"""

import re
from typing import Any, Dict, Optional

from brain_modules import fact_extractor, speech_acts

_STARTERS = re.compile(
    r"^(?:actually|correction|sorry|i meant|i mean|no wait|wait no|no i said|"
    r"scratch that|let me correct(?: that)?|to clarify|no it'?s|no its|no that'?s)\b[,:\s]*",
    re.IGNORECASE,
)

_VAL = r"[\w][\w .+#/\-]{0,38}?"
_P_NOT_ITS = re.compile(
    rf"\bnot\s+(?P<old>{_VAL})\s*[,;]\s*(?:it'?s|its|it is|that'?s|i meant|i said|actually)\s+(?P<new>{_VAL})\s*$",
    re.IGNORECASE)
_P_MEANT = re.compile(
    rf"\bi\s+(?:meant|mean)\s+(?P<new>{_VAL})\s*[,;]?\s*not\s+(?P<old>{_VAL})\s*$",
    re.IGNORECASE)
_P_ITS_NOT = re.compile(
    rf"\b(?:it'?s|its|it is|that'?s)\s+(?P<new>{_VAL})\s*[,;]?\s*(?:not|rather than|instead of)\s+(?P<old>{_VAL})\s*$",
    re.IGNORECASE)
_P_FROM_TO = re.compile(
    rf"\b(?:changed|switched|moved)\s+from\s+(?P<old>{_VAL})\s+to\s+(?P<new>{_VAL})\s*$",
    re.IGNORECASE)
_P_NO_LONGER = re.compile(
    rf"\bno\s+longer\s+(?P<old>{_VAL})\s*[,;]\s*now\s+(?P<new>{_VAL})\s*$",
    re.IGNORECASE)

# Patterns explicit enough to count without a starter word.
_EXPLICIT = (_P_NOT_ITS, _P_MEANT, _P_FROM_TO, _P_NO_LONGER)


def detect_correction(text: str) -> Optional[Dict[str, Any]]:
    """
    Analyse text for correction intent.

    Returns None, or a dict with:
        is_correction : True
        starter       : matched starter phrase or None
        old_value     : the value being replaced, or None
        new_value     : the replacement, or None
        raw_text      : original input
    """
    raw = (text or "").strip()
    if not raw:
        return None

    body = raw.rstrip(" .!?")
    starter_match = _STARTERS.match(body)
    starter = starter_match.group(0).strip(" ,:").lower() if starter_match else None
    rest = body[starter_match.end():] if starter_match else body

    if starter and speech_acts.is_question(rest):
        return None

    candidates = list(_EXPLICIT)
    if starter:
        candidates.append(_P_ITS_NOT)
    for pattern in candidates:
        m = pattern.search(body)
        if not m:
            continue
        old = fact_extractor.clean_value(m.group("old"))
        new = fact_extractor.clean_value(m.group("new"))
        if old and new and old.lower() != new.lower() and len(old) >= 2:
            return {"is_correction": True, "starter": starter, "old_value": old,
                    "new_value": new, "raw_text": raw}

    if starter:
        return {"is_correction": True, "starter": starter, "old_value": None,
                "new_value": None, "raw_text": raw}
    return None


def is_correction(text: str) -> bool:
    """Quick boolean check for correction intent."""
    return detect_correction(text) is not None
