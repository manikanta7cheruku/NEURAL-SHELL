"""
brain_modules/productivity.py

Seven's access to the user's tasks, schedules, triggers and workspaces, so
these work the same by chat and by voice:

    "show my tasks" / "what's overdue" / "what do I have to do today"
    "add a task to call mom tomorrow" / "add buy milk to my list"
    "what are my reminders" / "what's scheduled"
    "what triggers do I have" / "run my focus trigger"
    "list my workspaces" / "open my coding workspace"

Lists are answered from the real data, never from the model. Actions are
emitted as ###TASK / ###TRIGGER / ###WORKSPACE tags, which the console
(backend/routes/chat.py) and the voice loop (main_modules/handlers) execute
and verify. Anything that isn't one of these passes through untouched.
"""

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


class DataSource:
    """Reads the real stores. Tests replace this with a fake."""

    def tasks(self) -> List[Dict[str, Any]]:
        from backend.routes.tasks import db_get_pending_list
        return db_get_pending_list()

    def schedules(self, speaker_id: Optional[str]) -> str:
        import hands.scheduler as sched
        return sched.list_schedules(speaker_id=speaker_id)[1]

    def triggers(self) -> List[Dict[str, Any]]:
        from backend.routes.triggers import _get_conn, _row_to_dict
        with _get_conn() as conn:
            return [_row_to_dict(r) for r in conn.execute("SELECT * FROM triggers ORDER BY name").fetchall()]

    def workspaces(self) -> List[Dict[str, Any]]:
        from backend.routes.workspaces import _get_conn, _row_to_dict
        with _get_conn() as conn:
            return [_row_to_dict(r) for r in conn.execute(
                "SELECT * FROM workspaces ORDER BY last_used DESC NULLS LAST, created_at DESC").fetchall()]


_source: DataSource = DataSource()


def set_source(source: Optional[DataSource]) -> None:
    global _source
    _source = source or DataSource()


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

_ACTION_VERBS = r"(?:add|create|make|complete|finish|delete|remove|cancel|mark|set|edit|rename|change|snooze)"
_ASK = r"(?:show|list|tell|read|what|whats|which|any|do i have|have i got|how many|give me|see)"

_TASK_LIST = re.compile(rf"\b{_ASK}\b.*\b(?:tasks?|to ?dos?|todo list|to do list|my list)\b|"
                        r"\bwhat (?:do|should) i (?:have to|need to) do\b|\bwhat(?:s| is) (?:overdue|due)\b")
_TASK_CREATE = re.compile(
    r"^(?:can you |could you |please )?(?:add|create|make|put|new)\s+(?:a\s+)?(?:new\s+)?(?:task|to ?do)\s*"
    r"(?:to|for|that|called|named|:)?\s+(?P<text>.+)$|"
    r"^(?:can you |could you |please )?(?:add|put)\s+(?P<text2>.+?)\s+(?:to|on|in)\s+my\s+"
    r"(?:tasks?|to ?do(?: list)?|task list|list)$")
_SCHEDULE_LIST = re.compile(rf"\b{_ASK}\b.*\b(?:reminders?|alarms?|schedules?|timers?|scheduled|events?)\b|"
                            r"\bwhat(?:s| is) (?:on my calendar|coming up|scheduled)\b")
_TRIGGER_LIST = re.compile(rf"\b{_ASK}\b.*\b(?:triggers?|hotkeys?|shortcuts?)\b")
_WORKSPACE_LIST = re.compile(rf"\b{_ASK}\b.*\bworkspaces?\b|^(?:my )?workspaces$")
_TRIGGER_FIRE = re.compile(r"^(?:run|fire|start|activate|launch|trigger|do|use)\s+(?:my\s+|the\s+)?"
                           r"(?:trigger\s+(?:called\s+|named\s+)?(?P<a>.+)|(?P<b>.+?)\s+trigger)$")
_WORKSPACE_OPEN = re.compile(r"^(?:open|restore|launch|load|start|switch to|bring up)\s+(?:my\s+|the\s+)?"
                             r"(?:workspace\s+(?:called\s+|named\s+)?(?P<a>.+)|(?P<b>.+?)\s+workspace)$")
_DUE = [
    (re.compile(r"\s+(?:by |due |for |on )?(today|tonight)$"), lambda m: date.today()),
    (re.compile(r"\s+(?:by |due |for |on )?tomorrow$"), lambda m: date.today() + timedelta(days=1)),
    (re.compile(r"\s+(?:by |due |for |on )?(?:next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$"),
     lambda m: _next_weekday(m.group(1))),
]
_PRIORITY = re.compile(r"\s*(?:,\s*)?(?:with\s+)?(high|low|urgent)\s+priority$|^(?:urgent|important)\s+")


_MINE = re.compile(r"\b(?:my|i|me|mine|im|ive)\b|^(?:show|list)\b|^whats (?:overdue|due|scheduled|coming up)\b")


def _clean(text: str) -> str:
    t = (text or "").lower().strip().replace("’", "'")
    t = re.sub(r"[?!.]+$", "", t)
    t = t.replace("what's", "whats").replace("what is", "whats").replace("to-do", "todo")
    t = re.sub(r"^(?:hey seven|seven)[, ]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _next_weekday(name: str) -> date:
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    ahead = (days.index(name) - date.today().weekday()) % 7 or 7
    return date.today() + timedelta(days=ahead)


def _find(items: List[Dict[str, Any]], name: str, fields=("name",)) -> Optional[Dict[str, Any]]:
    """Exact, then whole-word, then substring match on the given fields."""
    n = name.strip().lower()
    for test in (lambda v: v == n, lambda v: re.search(rf"\b{re.escape(n)}\b", v), lambda v: n in v or v in n):
        for item in items:
            if any(test((item.get(f) or "").lower()) for f in fields if item.get(f)):
                return item
    return None


def _names(items, key="name", limit=8) -> str:
    names = [i.get(key, "") for i in items[:limit]]
    more = f" and {len(items) - limit} more" if len(items) > limit else ""
    if len(names) == 1:
        return names[0] + more
    return ", ".join(names[:-1]) + f" and {names[-1]}" + more if not more else ", ".join(names) + more


def _due_label(d: Optional[str]) -> str:
    if not d:
        return ""
    try:
        when = date.fromisoformat(d[:10])
    except ValueError:
        return ""
    delta = (when - date.today()).days
    if delta < 0:
        return " (overdue)"
    if delta == 0:
        return " (due today)"
    if delta == 1:
        return " (due tomorrow)"
    return f" (due {when.strftime('%a %b')} {when.day})"


# --------------------------------------------------------------------------
# Answers
# --------------------------------------------------------------------------

def _tasks_answer(t: str) -> str:
    tasks = _source.tasks()
    kind = "pending"
    if "overdue" in t:
        kind = "overdue"
        tasks = [x for x in tasks if _due_label(x.get("due_date")) == " (overdue)"]
        if not tasks:
            return "Nothing is overdue."
    elif "today" in t:
        kind = "today"
        tasks = [x for x in tasks if _due_label(x.get("due_date")) in (" (due today)", " (overdue)")]
        if not tasks:
            return "Nothing is due today."
    if not tasks:
        return "You have no pending tasks."
    noun = f"task{'s' if len(tasks) != 1 else ''}"
    head = f"You have {len(tasks)} {noun} due today" if kind == "today" else f"You have {len(tasks)} {kind} {noun}"
    items = [f"{x.get('text', '').strip()}{_due_label(x.get('due_date'))}" for x in tasks[:8]]
    more = f", and {len(tasks) - 8} more" if len(tasks) > 8 else ""
    return f"{head}: " + "; ".join(items) + more + "."


def _task_create(text: str) -> str:
    body, due, priority = text.strip(), None, "medium"
    pm = _PRIORITY.search(body)
    if pm:
        priority = "high" if (pm.group(1) or "") in ("high", "urgent") or body.startswith(("urgent", "important")) else "low"
        body = _PRIORITY.sub("", body).strip()
    for rx, fn in _DUE:
        m = rx.search(body)
        if m:
            due = fn(m)
            body = body[:m.start()].strip()
            break
    body = re.sub(r"^(?:to|that i need to|that i have to|i need to|i have to)\s+", "", body).strip(" ,")
    if len(body) < 2:
        return "What should the task say?"
    tag = f"###TASK: action=create text={body.replace(' ', '|||')} priority={priority}"
    if due:
        tag += f" due={due.isoformat()}"
    when = f", due {_due_label(due.isoformat())[6:-1]}" if due else ""
    return f'Added "{body}" to your tasks{when}. {tag}'


def _schedules_answer(speaker_id: Optional[str]) -> str:
    text = _source.schedules(speaker_id)
    return text.replace(" — ", ", ").replace("No active schedules.", "You have no reminders, alarms or timers set.")


def _triggers_answer() -> str:
    triggers = _source.triggers()
    if not triggers:
        return "You don't have any triggers yet. You can create them on the Triggers page."
    on = [t for t in triggers if t.get("enabled", True)]
    parts = []
    for t in on[:8]:
        how = [h for h in (t.get("hotkey"), f'say "{t["voice_phrase"]}"' if t.get("voice_phrase") else None) if h]
        parts.append(t["name"] + (f" ({', '.join(how)})" if how else ""))
    off = len(triggers) - len(on)
    tail = f" {off} more {'is' if off == 1 else 'are'} turned off." if off else ""
    return f"You have {len(on)} active trigger{'s' if len(on) != 1 else ''}: " + "; ".join(parts) + "." + tail


def _workspaces_answer() -> str:
    spaces = _source.workspaces()
    if not spaces:
        return "You don't have any saved workspaces. Say \"save this workspace as\" and a name to create one."
    return f"You have {len(spaces)} workspace{'s' if len(spaces) != 1 else ''}: {_names(spaces)}."


def _fire(name: str) -> str:
    triggers = _source.triggers()
    match = _find(triggers, name, ("name", "voice_phrase"))
    if not match:
        names = _names(triggers) if triggers else "none yet"
        return f"I can't find a trigger called {name}. Your triggers: {names}."
    if not match.get("enabled", True):
        return f"{match['name']} is turned off. Turn it on in Triggers first."
    return f"Running {match['name']}. ###TRIGGER: action=fire id={match['id']} phrase={match['name'].replace(' ', '|||')}"


def _open_workspace(name: str) -> str:
    spaces = _source.workspaces()
    match = _find(spaces, name)
    if not match:
        names = _names(spaces) if spaces else "none yet"
        return f"I can't find a workspace called {name}. Your workspaces: {names}."
    return f"Opening {match['name']}. ###WORKSPACE: action=restore id={match['id']} name={match['name'].replace(' ', '|||')}"


def handle(text: str, speaker_id: Optional[str] = None) -> Optional[str]:
    """A reply for a tasks/schedules/triggers/workspaces request, or None."""
    t = _clean(text)
    if not t:
        return None
    m = _TASK_CREATE.match(t)
    if m:
        return _task_create(m.group("text") or m.group("text2"))
    m = _TRIGGER_FIRE.match(t)
    if m and not _TRIGGER_LIST.search(t):
        return _fire(m.group("a") or m.group("b"))
    m = _WORKSPACE_OPEN.match(t)
    if m and not _WORKSPACE_LIST.search(t):
        return _open_workspace(m.group("a") or m.group("b"))
    if re.search(rf"^{_ACTION_VERBS}\b", t):
        return None                                   # complete/delete/cancel are handled by their own layers
    if not _MINE.search(t):
        return None                                   # "what is a task scheduler" is general knowledge
    if _WORKSPACE_LIST.search(t):
        return _workspaces_answer()
    if _TRIGGER_LIST.search(t):
        return _triggers_answer()
    if _TASK_LIST.search(t):
        return _tasks_answer(t)
    if _SCHEDULE_LIST.search(t) and not t.startswith(("remind", "set", "wake")):
        return _schedules_answer(speaker_id)
    return None
