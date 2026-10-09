"""
brain_modules/chat_history.py

The conversation window sent to the model, in /api/chat message format.

DESIGN:
    - Written ONLY by the LLM layer, after a reply completes. Commands,
      greetings and instant answers never enter it, so the model is not
      taught patterns like "open chrome" -> "Opening chrome".
    - Messages carry timestamps. get_messages() drops anything older than
      max_age_s, so coming back an hour later starts a clean context. Old
      context leaking into "Hey" was a direct cause of the context bleed.
    - Keyed by session.resolve_key(), the same key used everywhere else.

ConversationThread (all turns, used for repetition and follow-ups) remains a
separate store with a different purpose.
"""

import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional

MAX_TURNS = 8
DEFAULT_MAX_AGE_SECONDS = 1800

_lock = threading.Lock()
_history: Dict[str, List[dict]] = defaultdict(list)


def add_exchange(key: str, user_text: str, assistant_text: str) -> None:
    """Record a completed user/assistant exchange."""
    u, a = (user_text or "").strip(), (assistant_text or "").strip()
    if not u or not a:
        return
    now = time.time()
    with _lock:
        msgs = _history[key]
        msgs.append({"role": "user", "content": u, "ts": now})
        msgs.append({"role": "assistant", "content": a, "ts": now})
        limit = MAX_TURNS * 2
        if len(msgs) > limit:
            _history[key] = msgs[-limit:]


def get_messages(key: str, max_age_s: Optional[float] = DEFAULT_MAX_AGE_SECONDS) -> List[dict]:
    """Messages for the model: role and content only, newest window, no stale turns."""
    cutoff = time.time() - max_age_s if max_age_s else 0
    with _lock:
        return [{"role": m["role"], "content": m["content"]}
                for m in _history.get(key, []) if m["ts"] >= cutoff]


def last_assistant(key: str) -> str:
    """Most recent assistant reply, or ''."""
    with _lock:
        for m in reversed(_history.get(key, [])):
            if m["role"] == "assistant":
                return m["content"]
    return ""


def clear(key: Optional[str] = None) -> None:
    """Forget one speaker's window, or everyone's."""
    with _lock:
        if key:
            _history.pop(key, None)
        else:
            _history.clear()


# Backward-compatible names from the previous version of this module.
def add_user_message(speaker_id: str, content: str) -> None:
    """Deprecated: use add_exchange."""


def add_assistant_message(speaker_id: str, content: str) -> None:
    """Deprecated: use add_exchange."""
