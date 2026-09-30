"""
brain_modules/dialogue_manager.py
Seven - Conversation State Machine + Working Memory
Version: 2.0

Two independent systems:

1. PENDING DIALOGUES (v1.x, preserved)
   - close_confirm: "close chrome" -> "close all or just active?"
   - Multi-turn Q&A with timeout expiry
   - API: set_pending, check_pending, clear_pending, has_pending

2. WORKING MEMORY (v2.0, new)
   - Stores last 3 actions with their results
   - Enables references: "open the last one", "the second file", "not that one"
   - Parses ordinals, negation, positional words
   - API: remember_action, resolve_reference, has_recent_action

Both systems are independent. Working memory does not block pipeline flow.
"""

import re
import time
import threading
from colorama import Fore

# ==============================================================
# CONFIG-DRIVEN TIMEOUTS
# ==============================================================

def _load_timeout():
    """Read follow-up timeout from config, fallback to 90s."""
    try:
        import config
        val = int(config.KEY.get("brain", {}).get("follow_up_timeout", 90))
        return max(15, min(300, val))
    except Exception:
        return 90


_MEMORY_TIMEOUT_SEC = _load_timeout()


def reload_timeout():
    """Called by config PATCH endpoint to refresh timeout live."""
    global _MEMORY_TIMEOUT_SEC
    _MEMORY_TIMEOUT_SEC = _load_timeout()
    print(Fore.CYAN + f"[DIALOGUE] Memory timeout refreshed: {_MEMORY_TIMEOUT_SEC}s")


# ==============================================================
# PENDING DIALOGUES (unchanged from v1.x)
# ==============================================================

_lock = threading.Lock()
_pending = None


def set_pending(dialogue_type: str, data: dict, timeout_sec: int = 30):
    """Store a pending dialogue that expects a follow-up response."""
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
    """Check if user's response matches a pending dialogue."""
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

    clear_pending()
    return None


def _handle_close_confirm(clean: str, data: dict) -> str:
    """Handle close confirmation dialogue."""
    app = data.get("app", "app")
    count = data.get("count", 0)

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

    return f"I did not catch that. Close all {count} {app} windows, just the active one, or cancel?"


# ==============================================================
# WORKING MEMORY (v2.1 - production grade reference resolution)
# ==============================================================
#
# Design principles:
# 1. Reference detection is generous - if in doubt, treat as reference
#    and let resolver decide. False positives are cheap (LLM handles them).
#    False negatives are expensive (user gets fresh unwanted search).
#
# 2. Resolver is deterministic and logged. Every decision prints its
#    reasoning so bugs are traceable.
#
# 3. "last" always means results[-1]. "first" always means results[0].
#    Ordinals 1-10 map cleanly. "again", "same", "it" repeat last action.
#
# 4. Type filters ("the pdf", "the video") narrow previous results
#    without triggering a new search.

_memory_lock = threading.Lock()
WORKING_MEMORY = {
    "actions": [],       # list of recent actions, newest last
    "last_opened": None, # dict with path, name, ext of last opened item
}

_MAX_ACTIONS = 3


def remember_action(action_type: str, query: str, results: list,
                    opened_index: int = None):
    """Store an action in working memory. Called by layers after execution.

    action_type: 'file_search', 'app_disambiguate', 'task_list', etc.
    query: the user's original phrasing
    results: list of dicts with at least 'name' and 'path' keys
    opened_index: which result was auto-opened, if any (0-based)
    """
    with _memory_lock:
        entry = {
            "type": action_type,
            "query": query,
            "results": list(results) if results else [],
            "opened_index": opened_index,
            "timestamp": time.time(),
        }
        WORKING_MEMORY["actions"].append(entry)
        if len(WORKING_MEMORY["actions"]) > _MAX_ACTIONS:
            WORKING_MEMORY["actions"] = WORKING_MEMORY["actions"][-_MAX_ACTIONS:]

        if opened_index is not None and results and 0 <= opened_index < len(results):
            WORKING_MEMORY["last_opened"] = results[opened_index]

    print(Fore.CYAN + f"[MEMORY] Remembered {action_type}: '{query}' "
          f"({len(results)} results, opened idx {opened_index})")


def get_last_action():
    """Return the most recent action within timeout window, or None."""
    with _memory_lock:
        if not WORKING_MEMORY["actions"]:
            return None
        last = WORKING_MEMORY["actions"][-1]
        age = time.time() - last["timestamp"]
        if age > _MEMORY_TIMEOUT_SEC:
            return None
        return last


def has_recent_action() -> bool:
    return get_last_action() is not None


# -- Reference patterns (generous, catches natural human phrasing) --

_REFERENCE_ORDINALS = {
    "first": 0, "1st": 0, "one": 0,
    "second": 1, "2nd": 1, "two": 1,
    "third": 2, "3rd": 2, "three": 2,
    "fourth": 3, "4th": 3, "four": 3,
    "fifth": 4, "5th": 4, "five": 4,
    "sixth": 5, "6th": 5, "six": 5,
    "seventh": 6, "7th": 6, "seven": 6,
    "eighth": 7, "8th": 7, "eight": 7,
    "ninth": 8, "9th": 8, "nine": 8,
    "tenth": 9, "10th": 9, "ten": 9,
}

_REFERENCE_LAST = {"last", "final", "bottom", "latest", "newest"}
_REFERENCE_FIRST = {"first", "top", "beginning"}

_REFERENCE_REPEAT = {
    "again", "same", "once more", "one more time", "redo",
    "reopen", "re-open", "that same", "same one", "same thing",
    "same file", "same video", "again please",
}

_REFERENCE_PRONOUNS = {
    "it", "that", "this", "them", "those", "these",
    "that one", "this one", "the one",
}

_REFERENCE_NEGATION = {
    "not that", "not this", "other one", "different one",
    "another one", "the other", "nope", "not the",
}

_TYPE_FILTERS = {
    "pdf": [".pdf"],
    "doc": [".docx", ".doc"],
    "docx": [".docx"],
    "video": [".mp4", ".mov", ".avi", ".mkv", ".wmv"],
    "mp4": [".mp4"],
    "photo": [".jpg", ".jpeg", ".png", ".heic"],
    "image": [".jpg", ".jpeg", ".png", ".svg"],
    "song": [".mp3", ".wav", ".flac", ".m4a"],
    "audio": [".mp3", ".wav", ".flac"],
    "folder": ["folder"],
}


def looks_like_reference(user_text: str) -> bool:
    """Generous detection - if any signal present, treat as reference."""
    if not has_recent_action():
        return False

    clean = user_text.lower().strip()
    if not clean:
        return False

    words = re.findall(r"[a-z0-9]+", clean)
    word_set = set(words)

    # Signal 1: ordinal words
    if word_set & set(_REFERENCE_ORDINALS.keys()):
        return True

    # Signal 2: last/first/final
    if word_set & _REFERENCE_LAST or word_set & _REFERENCE_FIRST:
        return True

    # Signal 3: numeric reference like "open 2" or "the 3rd"
    if re.search(r"\b(?:number\s+)?(\d+)(?:st|nd|rd|th)?\b", clean):
        # Only if command is short - "open 2" yes, "essay on 2024" no
        if len(words) <= 5:
            return True

    # Signal 4: repeat words
    for phrase in _REFERENCE_REPEAT:
        if phrase in clean:
            return True

    # Signal 5: negation of last choice
    for phrase in _REFERENCE_NEGATION:
        if phrase in clean:
            return True

    # Signal 6: bare pronouns with action verb
    action_verbs = {"open", "show", "play", "run", "launch", "start",
                    "close", "delete", "remove"}
    if word_set & action_verbs and word_set & _REFERENCE_PRONOUNS:
        return True

    # Signal 7: "the X" where X is a type filter and only recent search matches
    if "the " in clean:
        for type_word in _TYPE_FILTERS:
            if f"the {type_word}" in clean:
                return True

    return False


def resolve_reference(user_text: str) -> dict:
    """Resolve a reference to an actual action.

    Returns dict:
        {"action": "open", "target": {...}, "reason": "..."}
        {"action": "repeat", "reason": "..."}
        {"action": "ambiguous", "reason": "...", "options": [...]}
        {"action": "none", "reason": "..."}
    """
    last = get_last_action()
    if not last:
        return {"action": "none", "reason": "no recent action in memory"}

    clean = user_text.lower().strip()
    words = re.findall(r"[a-z0-9]+", clean)
    word_set = set(words)
    results = last.get("results", [])

    print(Fore.CYAN + f"[MEMORY] Resolving '{user_text}' against "
          f"{len(results)} results from '{last['query']}'")

    # -- REPEAT / SAME --
    for phrase in _REFERENCE_REPEAT:
        if phrase in clean:
            opened_idx = last.get("opened_index")
            if opened_idx is not None and 0 <= opened_idx < len(results):
                target = results[opened_idx]
                print(Fore.GREEN + f"[MEMORY] Repeat -> re-open previously opened: {target.get('name')}")
                return {"action": "open", "target": target,
                        "reason": f"repeating last opened item"}
            if results:
                print(Fore.GREEN + f"[MEMORY] Repeat -> top result: {results[0].get('name')}")
                return {"action": "open", "target": results[0],
                        "reason": "repeating with top match"}
            return {"action": "none", "reason": "no results to repeat"}

    # -- LAST / FINAL --
    if word_set & _REFERENCE_LAST:
        if results:
            target = results[-1]
            print(Fore.GREEN + f"[MEMORY] Last -> results[-1]: {target.get('name')}")
            return {"action": "open", "target": target,
                    "reason": "user requested last item"}
        return {"action": "none", "reason": "no results for 'last'"}

    # -- FIRST / TOP --
    if word_set & _REFERENCE_FIRST and not (word_set & set(_REFERENCE_ORDINALS.keys()) - _REFERENCE_FIRST):
        if results:
            target = results[0]
            print(Fore.GREEN + f"[MEMORY] First -> results[0]: {target.get('name')}")
            return {"action": "open", "target": target,
                    "reason": "user requested first item"}
        return {"action": "none", "reason": "no results for 'first'"}

    # -- ORDINAL WORDS (second, third, etc.) --
    for word in words:
        if word in _REFERENCE_ORDINALS:
            idx = _REFERENCE_ORDINALS[word]
            if 0 <= idx < len(results):
                target = results[idx]
                print(Fore.GREEN + f"[MEMORY] Ordinal '{word}' -> results[{idx}]: {target.get('name')}")
                return {"action": "open", "target": target,
                        "reason": f"user requested item {idx + 1}"}
            return {"action": "none",
                    "reason": f"only {len(results)} results, cannot open #{idx + 1}"}

    # -- NUMERIC (open 2, the 3rd) --
    num_match = re.search(r"\b(?:number\s+)?(\d+)(?:st|nd|rd|th)?\b", clean)
    if num_match and len(words) <= 6:
        n = int(num_match.group(1))
        idx = n - 1
        if 0 <= idx < len(results):
            target = results[idx]
            print(Fore.GREEN + f"[MEMORY] Number {n} -> results[{idx}]: {target.get('name')}")
            return {"action": "open", "target": target,
                    "reason": f"user requested item {n}"}
        return {"action": "none",
                "reason": f"only {len(results)} results, cannot open #{n}"}

    # -- TYPE FILTER (the pdf, the video) --
    for type_word, exts in _TYPE_FILTERS.items():
        if f"the {type_word}" in clean or f"that {type_word}" in clean:
            filtered = []
            for r in results:
                r_ext = (r.get("ext") or "").lower()
                if type_word == "folder":
                    if r_ext == "folder":
                        filtered.append(r)
                elif r_ext in exts:
                    filtered.append(r)
            if len(filtered) == 1:
                target = filtered[0]
                print(Fore.GREEN + f"[MEMORY] Type filter '{type_word}' -> unique: {target.get('name')}")
                return {"action": "open", "target": target,
                        "reason": f"only one {type_word} in results"}
            if len(filtered) > 1:
                print(Fore.YELLOW + f"[MEMORY] Type filter '{type_word}' -> {len(filtered)} matches, ambiguous")
                return {"action": "ambiguous",
                        "reason": f"{len(filtered)} {type_word} files match",
                        "options": filtered}
            return {"action": "none",
                    "reason": f"no {type_word} files in last results"}

    # -- NEGATION (not that, other one) --
    for phrase in _REFERENCE_NEGATION:
        if phrase in clean:
            opened_idx = last.get("opened_index")
            if opened_idx is not None and len(results) > 1:
                # Return next unopened result
                for i, r in enumerate(results):
                    if i != opened_idx:
                        print(Fore.GREEN + f"[MEMORY] Negation -> next option: {r.get('name')}")
                        return {"action": "open", "target": r,
                                "reason": "user rejected previous, trying next"}
            if len(results) >= 2:
                print(Fore.GREEN + f"[MEMORY] Negation -> results[1]: {results[1].get('name')}")
                return {"action": "open", "target": results[1],
                        "reason": "user wants a different option"}
            return {"action": "none", "reason": "no alternatives available"}

    # -- BARE PRONOUN (open it, show that) --
    action_verbs = {"open", "show", "play", "run", "launch", "start"}
    if word_set & action_verbs and word_set & _REFERENCE_PRONOUNS:
        opened_idx = last.get("opened_index")
        if opened_idx is not None and 0 <= opened_idx < len(results):
            target = results[opened_idx]
            print(Fore.GREEN + f"[MEMORY] Pronoun -> last opened: {target.get('name')}")
            return {"action": "open", "target": target,
                    "reason": "pronoun refers to last opened"}
        if results:
            print(Fore.GREEN + f"[MEMORY] Pronoun -> top result: {results[0].get('name')}")
            return {"action": "open", "target": results[0],
                    "reason": "pronoun refers to top match"}

    return {"action": "none", "reason": "could not resolve reference"}


def format_memory_hint() -> str:
    """Human-readable summary of working memory for LLM context."""
    last = get_last_action()
    if not last:
        return ""

    results = last.get("results", [])
    lines = [f"Recent action: {last['type']} for '{last['query']}' "
             f"({len(results)} results)"]

    for i, r in enumerate(results[:5]):
        name = r.get("name", "unknown")
        marker = " [opened]" if i == last.get("opened_index") else ""
        lines.append(f"  {i + 1}. {name}{marker}")

    if len(results) > 5:
        lines.append(f"  ... and {len(results) - 5} more")

    return "\n".join(lines)


def clear_memory():
    """Clear working memory. Called on explicit cancel or restart."""
    with _memory_lock:
        WORKING_MEMORY["actions"].clear()
        WORKING_MEMORY["last_opened"] = None
    print(Fore.CYAN + "[MEMORY] Cleared")