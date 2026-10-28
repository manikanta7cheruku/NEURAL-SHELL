"""
main_modules/startup/greeting.py
Seven's greeting when it starts: one greeting per launch, said by one place.

Before, the voice loop spoke a morning brief at startup and the setup screen asked for a welcome at the same moment,
so a new user heard two greetings. Now greet() is the only thing that greets, and only once per launch, whoever
asks first.

    First launch after setup   the spoken welcome tour (main_modules/startup/tour.py): it makes sure you can hear it,
                               introduces Seven and walks through the home screen, then a welcome card opens.
    Every launch after that    a greeting and the single most useful thing right now, in this order:
                               overdue tasks, what's due today, the next reminder today, pending tasks, a clear day.
                               Low battery is added only when it matters. Two sentences at most.
"""
import json
import os
import threading
from datetime import datetime

_lock = threading.Lock()
_said = False


def _state_path() -> str:
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "greeting.json")


def _load() -> dict:
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_state_path()), exist_ok=True)
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def welcome_state() -> dict:
    """What the welcome card and its hint need: the tour ran, the hint was hidden."""
    s = _load()
    return {"tour_done": bool(s.get("tour_done")), "hint_dismissed": bool(s.get("hint_dismissed"))}


def update_welcome(**changes) -> dict:
    """Save welcome flags and tell the app."""
    s = _load()
    s.update(changes)
    _save(s)
    w = welcome_state()
    try:
        from backend.api_server import set_state
        set_state("welcome", w)
    except Exception:
        pass
    return w


def _name(config) -> str:
    try:
        n = (config.KEY.get("identity", {}).get("user_name", "") or "").strip()
        return "" if n.lower() in ("admin", "there", "user") else n
    except Exception:
        return ""


def _hello(name: str, now: datetime) -> str:
    h = now.hour
    word = "Good morning" if 5 <= h < 12 else "Good afternoon" if 12 <= h < 17 else "Good evening"
    return f"{word}, {name}." if name else f"{word}."


def _most_useful(ctx, now: datetime) -> str:
    """The one thing worth saying now, or a short all-clear."""
    try:
        from backend.routes.tasks import db_get_due_today, db_get_overdue, db_get_stats
        overdue, today, pending = db_get_overdue(), db_get_due_today(), db_get_stats().get("pending", 0)
    except Exception:
        overdue, today, pending = [], [], 0
    if overdue:
        top = overdue[0].get("text", "").strip().rstrip(".")
        if len(overdue) == 1:
            return f"One task is overdue: {top}."
        return f"{len(overdue)} tasks are overdue, starting with {top}."
    if today:
        rank = {"high": 3, "medium": 2, "low": 1}
        top = max(today, key=lambda t: rank.get(t.get("priority", "medium"), 2)).get("text", "").strip().rstrip(".")
        return f"Today you have {top}." if len(today) == 1 else f"{len(today)} tasks are due today, most important: {top}."
    reminder = _next_reminder(ctx, now)
    if reminder:
        return reminder
    if pending:
        return f"Nothing is due today; {pending} task{'s are' if pending != 1 else ' is'} waiting when you're ready."
    return "Nothing is due today, so it's a clear day."


def _next_reminder(ctx, now: datetime) -> str:
    try:
        upcoming = []
        for s in ctx.scheduler_mod.get_all_schedules() or []:
            if s.get("status") != "active":
                continue
            try:
                at = datetime.fromisoformat(s["time"])
            except Exception:
                continue
            if now <= at and at.date() == now.date():
                upcoming.append((at, s.get("message", "a reminder")))
        if upcoming:
            at, msg = min(upcoming)
            when = at.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")
            return f"Your next reminder is at {when}: {msg.rstrip('.')}."
    except Exception:
        pass
    return ""


def _battery() -> str:
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is not None and not b.power_plugged and b.percent <= 20:
            return f" Battery is at {int(b.percent)} percent, so plug in soon."
    except Exception:
        pass
    return ""


def message(ctx, config, now: datetime = None) -> tuple:
    """(kind, text): 'welcome' the first time after setup, else 'daily'."""
    now = now or datetime.now()
    name = _name(config)
    if not _load().get("welcomed"):
        who = f" {name}" if name else " there"
        return "welcome", (f"Hi{who}, I'm Seven. Whenever you need me, just say \"Hey Seven\" and ask, "
                           "like \"Hey Seven, open Chrome\". You can also type to me any time.")
    return "daily", f"{_hello(name, now)} {_most_useful(ctx, now)}{_battery()}"


def greet(ctx, config, speak=None) -> str:
    """Say the greeting once per launch. Returns what was said ('' if it was already said)."""
    global _said
    with _lock:
        if _said:
            return ""
        if not config.KEY.get("setup_complete", False):
            return ""
        _said = True
        kind, text = message(ctx, config)
        state = _load()
        state["welcomed"] = True
        state["last"] = datetime.now().isoformat(timespec="seconds")
        _save(state)
    try:
        from backend.api_server import set_state
        set_state("seven_text", text)
    except Exception:
        pass
    print(f"[GREETING] {kind}: {text}")
    if kind == "welcome":
        from main_modules.startup import tour
        tour.run(ctx, config, speak=speak)
        return text
    try:
        (speak or ctx.mouth.speak)(text)
    except Exception as e:
        print(f"[GREETING] could not speak: {e}")
    return text
