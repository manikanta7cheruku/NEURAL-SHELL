"""
memory/limits.py

Single source of truth for plan limits and storage safety.

PRODUCT DECISION: conversation history and stored facts are unlimited on every
plan. They live on the user's own disk, cost nothing to keep, and a small cap
makes Seven forget the person it is supposed to know. Other limits (schedules,
triggers, knowledge files) still come from license.TIER_FEATURES.

Unlimited does not mean careless: can_write() refuses to pretend a message was
saved when the disk is nearly full or a user-set budget is reached.
"""

import logging
import os
import shutil
import time
from typing import Optional, Tuple

_log = logging.getLogger("seven.limits")

UNLIMITED_FEATURES = frozenset({"conversation_history", "facts_limit"})
_MIN_FREE_MB_DEFAULT = 200
_cache = {"ts": 0.0, "result": (True, "")}


def tier() -> str:
    try:
        import voice_limits
        return voice_limits.get_tier()
    except Exception:
        pass
    try:
        import config
        return config.KEY.get("license", {}).get("tier", "free")
    except Exception:
        return "free"


def limit(feature: str, default: int = 0) -> int:
    """-1 means unlimited. Conversation history and facts are always unlimited."""
    if feature in UNLIMITED_FEATURES:
        return -1
    try:
        import license as license_module
        feats = license_module.TIER_FEATURES.get(tier(), license_module.TIER_FEATURES["free"])
        return int(feats.get(feature, default))
    except Exception:
        return default


def fact_limit() -> int:
    return limit("facts_limit")


def conversation_limit() -> int:
    return limit("conversation_history")


def _storage_cfg() -> dict:
    try:
        import config
        return config.KEY.get("storage", {}) or {}
    except Exception:
        return {}


def can_write(path: Optional[str] = None, force: bool = False) -> Tuple[bool, str]:
    """
    (ok, message). False when free disk space is below the minimum or the
    user-configured budget (storage.max_mb) is exhausted. Cached for 5 seconds.
    """
    now = time.time()
    if not force and now - _cache["ts"] < 5.0:
        return _cache["result"]
    cfg = _storage_cfg()
    min_free = int(cfg.get("min_free_mb", _MIN_FREE_MB_DEFAULT)) * 1024 * 1024
    max_mb = int(cfg.get("max_mb", 0) or 0)
    result: Tuple[bool, str] = (True, "")
    try:
        target = path or os.environ.get("APPDATA", os.path.expanduser("~"))
        target = target if os.path.isdir(target) else os.path.dirname(target) or "."
        free = shutil.disk_usage(target).free
        if free < min_free:
            result = (False, f"Disk space is almost full ({free // (1024 * 1024)} MB free). "
                             "I can't save new messages until space is freed.")
        elif max_mb and path and os.path.exists(path) and os.path.getsize(path) > max_mb * 1024 * 1024:
            result = (False, f"The conversation storage budget of {max_mb} MB is full. "
                             "Raise it in Settings or delete old conversations.")
    except Exception as exc:
        _log.debug("storage check skipped: %s", exc)
    _cache["ts"], _cache["result"] = now, result
    return result


def reset_cache() -> None:
    _cache["ts"] = 0.0
