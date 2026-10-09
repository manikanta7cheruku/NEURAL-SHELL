"""
brain_modules/session.py

Single source of truth for "who is talking" inside the brain.

WHY THIS EXISTS:
    Before this module, three different files each had their own copy of the
    logic that maps a speaker id to a storage key. The copies disagreed, so a
    turn was saved under one key and looked up under another. That is how
    repetition detection, follow-up hints and facts silently stopped working.
    Every component now calls resolve_key() and gets the same answer.
"""

import json
import logging
import os
import threading

_log = logging.getLogger("seven.session")

# Ids that mean "the person at this machine" rather than a distinct person.
SYSTEM_IDS = frozenset({
    "", "default", "unknown", "voice_user", "speaker", "user", "admin", "there",
})

_lock = threading.Lock()
_cache = {"mtime": None, "name": ""}


def _config_path() -> str:
    """Path of the per-user config file (never the repo copy)."""
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "SEVEN", "config.json")


def is_placeholder_name(name) -> bool:
    """True when the name is a system placeholder, not a real person's name."""
    return (name or "").strip().lower() in SYSTEM_IDS


def _from_live_config() -> str:
    """Fallback: read the in-process config when the file is unavailable."""
    try:
        import config
        name = str(config.KEY.get("identity", {}).get("user_name", "") or "").strip()
        return "" if is_placeholder_name(name) else name
    except Exception:
        return ""


def get_user_name() -> str:
    """
    Return the configured display name of the owner, or "" when unset.

    The result is cached against the config file mtime so the hot path does
    one stat() call instead of parsing JSON on every message.
    """
    path = _config_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _from_live_config()

    with _lock:
        if _cache["mtime"] == mtime:
            return _cache["name"]

    name = ""
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        name = str(data.get("identity", {}).get("user_name", "") or "").strip()
    except Exception as exc:
        _log.debug("config name read failed: %s", exc)
        return _cache["name"]

    if is_placeholder_name(name):
        name = ""
    with _lock:
        _cache["mtime"] = mtime
        _cache["name"] = name
    return name


def resolve_key(speaker_id, user_name=None) -> str:
    """
    Map a raw speaker id to the stable key used for ALL per-person storage:
    conversation threads, chat history, facts and style preferences.

    Generic ids (default, voice_user, ...) collapse to the owner's lowercase
    name so typed chat and voice share one memory. Enrolled voice profiles
    keep their own id.
    """
    sid = (speaker_id or "").strip().lower()
    if sid not in SYSTEM_IDS:
        return sid
    name = (user_name or "").strip()
    if is_placeholder_name(name):
        name = get_user_name()
    name = name.strip().lower()
    return name if name and name not in SYSTEM_IDS else "default"


def display_name(speaker_id, user_name=None) -> str:
    """Human-facing name for prompts. Returns "" when there is no real name."""
    sid = (speaker_id or "").strip()
    if sid.lower() not in SYSTEM_IDS:
        return sid.title()
    name = (user_name or "").strip()
    if is_placeholder_name(name):
        name = get_user_name()
    return "" if is_placeholder_name(name) else name
