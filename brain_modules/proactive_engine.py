"""
=============================================================================
brain_modules/proactive_engine.py

Proactive Intent Detection Engine.

Analyzes user input for latent action intents that Seven could offer to
handle without being explicitly asked. Detected categories:

  - Reminder intent    ("I need to call mom tomorrow")
  - Task intent        ("I should finish the report by Friday")
  - Schedule intent    ("meeting with the team at 3pm")
  - Follow-up intent   ("remind me later about this")

Returns a suggestion struct that Layer 075 injects as ctx.proactive_hint.

DESIGN PRINCIPLES:
    - Positive framing only. Never emits negative meta-instructions.
    - Low false-positive rate. Only fires on clear intent markers.
    - Cooldown per speaker to prevent suggestion fatigue.
    - Fully local. No LLM calls. Sub-2ms detection latency.
=============================================================================
"""

import re
import time
import threading
from typing import Optional, Dict


# -- Intent signal lexicons ------------------------------------------------

_REMINDER_VERBS = {
    "call", "email", "text", "message", "contact", "reply", "respond",
    "visit", "meet", "pick", "grab", "buy", "pay", "renew", "cancel",
    "book", "schedule", "confirm", "check", "review", "send",
}

_TASK_VERBS = {
    "finish", "complete", "write", "build", "fix", "update", "prepare",
    "draft", "submit", "deliver", "ship", "deploy", "test", "refactor",
    "clean", "organize", "sort", "file", "print", "backup",
}

_INTENT_MARKERS = {
    "i need to", "i have to", "i must", "i should", "i want to",
    "i gotta", "i've got to", "i ought to", "gotta", "need to",
    "have to", "supposed to", "planning to", "going to",
    "remind me to", "remind me about", "dont let me forget",
    "don't let me forget", "make sure i", "help me remember",
}

_TIME_HINTS = {
    "today", "tomorrow", "tonight", "morning", "afternoon", "evening",
    "later", "soon", "next week", "next month", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday",
    "am", "pm", "oclock", "o'clock", "hour", "minute", "hours", "minutes",
    "week", "month", "eod", "eow", "asap", "by",
}

_TIME_PATTERNS = [
    re.compile(r'\b\d{1,2}:\d{2}\s*(?:am|pm)?\b', re.IGNORECASE),
    re.compile(r'\b\d{1,2}\s*(?:am|pm)\b', re.IGNORECASE),
    re.compile(r'\bin\s+\d+\s+(?:minute|hour|day|week|month)s?\b', re.IGNORECASE),
    re.compile(r'\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|tonight|noon|eod)\b', re.IGNORECASE),
]

_SCHEDULE_KEYWORDS = {
    "meeting", "appointment", "call", "interview", "lunch", "dinner",
    "coffee", "session", "standup", "sync", "review", "demo",
    "presentation", "conference", "flight", "train",
}

_QUESTION_MARKERS = {
    "what", "when", "where", "who", "why", "how", "which", "can you",
    "could you", "would you", "do you", "does", "is it", "are you",
    "?",
}

# -- Suggestion templates (LLM will paraphrase, not emit verbatim) --------

_HINT_REMINDER = (
    "The user mentioned something that sounds like a personal reminder. "
    "If it feels natural in your reply, briefly offer to set a reminder. "
    "Do not force the offer. Do not create anything automatically. "
    "One short sentence at the end is enough."
)

_HINT_TASK = (
    "The user described work they need to complete. "
    "If it fits the tone, briefly offer to add it as a task. "
    "Do not create anything automatically. Keep the offer to one short sentence."
)

_HINT_SCHEDULE = (
    "The user mentioned a scheduled event. "
    "If it feels natural, briefly offer to add it to their schedule. "
    "Do not create anything automatically. One short sentence at most."
)


# -- Cooldown state --------------------------------------------------------

_COOLDOWN_SECONDS = 90
_last_suggestion: Dict[str, float] = {}
_lock = threading.Lock()


def _is_on_cooldown(speaker_id: str) -> bool:
    """Return True if we suggested to this speaker within the cooldown window."""
    with _lock:
        last = _last_suggestion.get(speaker_id, 0.0)
        return (time.time() - last) < _COOLDOWN_SECONDS


def _mark_suggested(speaker_id: str) -> None:
    """Record that a suggestion was emitted for this speaker."""
    with _lock:
        _last_suggestion[speaker_id] = time.time()


def _tokens(text: str) -> set:
    """Cheap token set for lexicon matching."""
    return set(re.sub(r'[^\w\s]', ' ', text.lower()).split())


def _has_time_hint(text_lower: str, token_set: set) -> bool:
    """Check for any time-related signal."""
    if token_set & _TIME_HINTS:
        return True
    for pattern in _TIME_PATTERNS:
        if pattern.search(text_lower):
            return True
    return False


def _has_intent_marker(text_lower: str) -> bool:
    """Check for phrase-level intent markers."""
    for marker in _INTENT_MARKERS:
        if marker in text_lower:
            return True
    return False


def _is_question(text_lower: str, token_set: set) -> bool:
    """Skip suggestions on questions - user is asking, not planning."""
    if text_lower.endswith("?"):
        return True
    first_two = " ".join(text_lower.split()[:2])
    for marker in _QUESTION_MARKERS:
        if first_two.startswith(marker):
            return True
    return False


def detect_intent(user_input: str, speaker_id: str = "default") -> Optional[Dict]:
    """
    Analyze user input for proactive suggestion opportunities.

    Returns:
        None if no suggestion should be offered.
        Dict with keys {"category", "hint", "matched_phrase"} otherwise.

    Categories: "reminder", "task", "schedule"
    """
    if not user_input or not isinstance(user_input, str):
        return None

    text = user_input.strip()
    if len(text) < 8 or len(text) > 400:
        return None

    text_lower = text.lower()
    token_set = _tokens(text_lower)

    # Skip questions entirely - user is inquiring, not planning
    if _is_question(text_lower, token_set):
        return None

    # Skip if speaker is on cooldown
    if _is_on_cooldown(speaker_id):
        return None

    has_intent = _has_intent_marker(text_lower)
    has_time = _has_time_hint(text_lower, token_set)
    has_reminder_verb = bool(token_set & _REMINDER_VERBS)
    has_task_verb = bool(token_set & _TASK_VERBS)
    has_schedule_kw = bool(token_set & _SCHEDULE_KEYWORDS)

    # -- Reminder intent: "I need to call mom tomorrow" ------------------
    # Requires: intent marker + reminder verb + (time hint OR schedule keyword)
    if has_intent and has_reminder_verb and (has_time or has_schedule_kw):
        return {
            "category": "reminder",
            "hint": _HINT_REMINDER,
            "matched_phrase": text[:80],
        }

    # -- Task intent: "I should finish the report by Friday" -------------
    # Requires: intent marker + task verb (time hint optional but preferred)
    if has_intent and has_task_verb:
        return {
            "category": "task",
            "hint": _HINT_TASK,
            "matched_phrase": text[:80],
        }

    # -- Schedule intent: "meeting with the team at 3pm" -----------------
    # Requires: schedule keyword + explicit time pattern (stricter, no intent marker needed)
    if has_schedule_kw and has_time:
        # But skip if it looks like recap ("had a meeting", "was at lunch")
        past_markers = {"had", "was", "were", "attended", "went"}
        if not (token_set & past_markers):
            return {
                "category": "schedule",
                "hint": _HINT_SCHEDULE,
                "matched_phrase": text[:80],
            }

    return None


def mark_suggestion_sent(speaker_id: str) -> None:
    """
    Called by the pipeline layer after a suggestion has been injected.
    Starts the cooldown timer for this speaker.
    """
    _mark_suggested(speaker_id)


def reset_cooldown(speaker_id: Optional[str] = None) -> None:
    """
    Clear cooldown state. If speaker_id is None, clears all.
    Used by session reset flows.
    """
    with _lock:
        if speaker_id is None:
            _last_suggestion.clear()
        else:
            _last_suggestion.pop(speaker_id, None)