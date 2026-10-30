"""
companion/settings.py

What the person chose in Seven's chat settings, and the maths that follows from it. Stored in config.json under
"companion". Nothing else decides how often Seven reaches out.

    pace     auto      a different number each day: 3, 5 or 7 messages, 7 to 17 minutes apart (like a friend, not a timer)
             calm      3 a day, 14 to 30 minutes apart
             lively    7 a day, 7 to 12 minutes apart
    quiet    no messages and no voice between two times (default 22:00 to 08:00), set only in the chat settings
    voice    say messages aloud when you are idle (they are always written in the chat as well)
    topics   about you, about Seven, did you know
"""
import copy
import datetime
import random
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "pace": "auto",
    "voice": True,
    "quiet": {"enabled": True, "start": "22:00", "end": "08:00"},
    "topics": {"you": True, "seven": True, "facts": True},
}

PACES = ("auto", "calm", "lively")
_GAP = {"auto": (7, 17), "calm": (14, 30), "lively": (7, 12)}
_AUTO_DAYS = (3, 5, 5, 7)               # 3 and 7 are rarer than 5, so most days feel ordinary and some feel quiet or busy


def _time(value, fallback: str) -> str:
    try:
        h, m = str(value).split(":")
        h, m = int(h), int(m)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except (ValueError, AttributeError):
        pass
    return fallback


def normalize(raw: Any) -> Dict[str, Any]:
    """The settings with every value valid; anything missing or wrong falls back to the default."""
    raw = raw if isinstance(raw, dict) else {}
    out = copy.deepcopy(DEFAULTS)
    out["enabled"] = bool(raw.get("enabled", out["enabled"]))
    out["voice"] = bool(raw.get("voice", out["voice"]))
    out["pace"] = raw.get("pace") if raw.get("pace") in PACES else out["pace"]
    quiet = raw.get("quiet") if isinstance(raw.get("quiet"), dict) else {}
    out["quiet"] = {"enabled": bool(quiet.get("enabled", out["quiet"]["enabled"])),
                    "start": _time(quiet.get("start"), out["quiet"]["start"]),
                    "end": _time(quiet.get("end"), out["quiet"]["end"])}
    topics = raw.get("topics") if isinstance(raw.get("topics"), dict) else {}
    out["topics"] = {k: bool(topics.get(k, v)) for k, v in out["topics"].items()}
    return out


def get(config=None) -> Dict[str, Any]:
    try:
        if config is None:
            import config as config
        return normalize(config.KEY.get("companion"))
    except Exception:
        return normalize(None)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def in_quiet_hours(settings: Dict[str, Any], now: datetime.datetime) -> bool:
    q = settings["quiet"]
    if not q["enabled"]:
        return False
    start, end, here = _minutes(q["start"]), _minutes(q["end"]), now.hour * 60 + now.minute
    if start == end:
        return False
    return start <= here < end if start < end else (here >= start or here < end)       # 22:00 to 08:00 wraps midnight


def daily_target(settings: Dict[str, Any], day: datetime.date) -> int:
    """How many messages today. Fixed by the date, so restarting Seven never changes today's number."""
    if settings["pace"] == "calm":
        return 3
    if settings["pace"] == "lively":
        return 7
    return random.Random(day.toordinal()).choice(_AUTO_DAYS)


def gap_minutes(settings: Dict[str, Any], rng: random.Random = None) -> float:
    low, high = _GAP[settings["pace"]]
    return (rng or random).uniform(low, high)
