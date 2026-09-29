"""
brain_modules/dialogue_manager.py
Seven - Conversation State Machine for Disambiguation
Version: 1.0

Handles multi-turn conversations when Seven needs clarification.

CURRENT DIALOGUES:
    - close_confirm: "close chrome" with multiple windows
    - file_disambiguate: "open resume" with many matches (future)

PUBLIC API:
    set_pending(dialogue_type, data, timeout_sec) -> None
    check_pending(user_text) -> str or None
    clear_pending() -> None
    has_pending() -> bool
"""

import time
import threading
from colorama import Fore

_lock = threading.Lock()
_pending = None


def set_pending(dialogue_type: str, data: dict, timeout_sec: int = 30):
    """
    Store a pending dialogue that expects a follow-up response.

    Args:
        dialogue_type: "close_confirm", "file_disambiguate", etc.
        data: dict with context (app name, window count, file list, etc.)
        timeout_sec: seconds before auto-expiry
    """
    global _pending
    with _lock:
        _pending = {
            "type": dialogue_type,
            "data": data,
            "expires": time.time() + timeout_sec,
        }
    print(Fore.CYAN + f"[DIALOGUE] Pending: {dialogue_type} ({timeout_sec}s)")


def clear_pending():
    """Clear any pending dialogue."""
    global _pending
    with _lock:
        _pending = None


def has_pending() -> bool:
    """Check if there is an active pending dialogue."""
    with _lock:
        if _pending is None:
            return False
        if time.time() > _pending["expires"]:
            return False
        return True


def check_pending(user_text: str) -> str:
    """
    Check if user's response matches a pending dialogue.
    Returns speech string if handled, None if no match.
    """
    global _pending

    with _lock:
        if _pending is None:
            return None
        if time.time() > _pending["expires"]:
            _pending = None
            return None
        pending = _pending.copy()

    clean = user_text.lower().strip()
    dtype = pending["type"]
    data = pending["data"]

    if dtype == "close_confirm":
        return _handle_close_confirm(clean, data)

    # Unknown dialogue type
    clear_pending()
    return None


def _handle_close_confirm(clean: str, data: dict) -> str:
    """Handle close confirmation dialogue."""
    app = data.get("app", "app")
    count = data.get("count", 0)

    # Affirmative: close all
    if any(w in clean for w in [
        "all", "yes", "yeah", "yep", "sure", "ok", "okay",
        "close all", "close them", "kill all", "shut all",
        "every", "everything", "all of them", "do it"
    ]):
        clear_pending()
        try:
            from hands.app_closer import close_app
            close_app(app, close_all=True)
            import random
            return random.choice([
                f"Done, closed all {count} {app} windows.",
                f"Alright, all {app} windows are shut.",
                f"Got it, killed all {count} {app} instances.",
            ])
        except Exception as e:
            return f"Tried to close {app} but ran into an issue: {e}"

    # Negative: cancel
    if any(w in clean for w in [
        "no", "nope", "cancel", "never mind", "nevermind",
        "stop", "dont", "don't", "nah", "skip", "leave it",
        "keep it", "keep them"
    ]):
        clear_pending()
        import random
        return random.choice([
            f"Alright, leaving {app} open.",
            f"Okay, {app} stays running.",
            f"No problem, keeping {app} as is.",
        ])

    # Active window only
    if any(w in clean for w in [
        "active", "current", "this one", "just one",
        "the active", "the current", "foreground", "this",
        "one", "just the active", "only active"
    ]):
        clear_pending()
        try:
            from hands.app_closer import close_app
            close_app(app, close_all=False)
            return f"Closed the active {app} window. The rest are still open."
        except Exception as e:
            return f"Tried to close {app} but ran into an issue: {e}"

    # Unclear response: re-ask
    return f"I did not catch that. Close all {count} {app} windows, just the active one, or cancel?"