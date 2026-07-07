"""
=============================================================================
LAYER 4.5a: TASK DETECTION

Detects voice/text intents for task management:
    create → "add task X" / "remind me to finish X"
    list   → "show my tasks" / "what are my tasks"
    done   → "mark X as done" / "i finished X"
    delete → "remove task X" / "delete task X"

Emits ###TASK: tag for main.py handler to execute.

Tag format:
    ###TASK: action=create text=X priority=Y due=Z
    ###TASK: action=list filter=today
    ###TASK: action=complete search=X
    ###TASK: action=delete search=X

Uses pipe delimiter (|||) instead of underscore for multi-word text.
This prevents the space-based tag parser in main.py from splitting text.
=============================================================================
"""

import re
from colorama import Fore
from brain_modules.layer_result import LayerResult


_TASK_CREATE_TRIGGERS = [
    "add to my tasks", "add task", "add to tasks", "create task",
    "make a task", "note this as task", "task:", "todo:",
    "remind me to finish", "add to my todo", "add to todo",
    "new task", "create a task", "make task", "log task",
    "put on my tasks", "put on my list", "add it to my tasks",
]

_TASK_LIST_TRIGGERS = [
    "what are my tasks", "show my tasks", "list tasks", "list my tasks",
    "what do i have to do", "show todo", "show my todo",
    "my tasks today", "tasks today", "what tasks", "my pending tasks",
    "show all tasks", "what's on my list", "whats on my list",
    "show task list", "my task list",
]

_TASK_DONE_TRIGGERS = [
    "mark as done", "mark done", "complete task", "finished with",
    "done with", "mark complete", "check off", "completed",
    "i finished", "i completed", "i'm done with", "im done with",
    "task done", "mark task done", "mark it done",
]

_TASK_DELETE_TRIGGERS = [
    "remove task", "delete task", "cancel task", "remove from tasks",
    "delete from tasks", "remove from my tasks", "drop task",
    "clear task", "remove it from tasks",
]

_DUE_PATTERNS = [
    (r'\bby\s+(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', True),
    (r'\bby\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+)\b', True),
    (r'\b(tomorrow|today|tonight)\b', True),
    (r'\bdue\s+(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', True),
    (r'\btill\s+(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', True),
    (r'\bby\s+(\d+(?:am|pm))\b', True),
]

_PRIORITY_PATTERNS = [
    (["high priority", "urgent", "important", "critical"], "high"),
    (["low priority", "whenever", "not urgent"], "low"),
]


def process(ctx, deps):
    clean_in = ctx.clean_in

    _has_task_create = any(t in clean_in for t in _TASK_CREATE_TRIGGERS)
    _has_task_list   = any(t in clean_in for t in _TASK_LIST_TRIGGERS)
    _has_task_done   = any(t in clean_in for t in _TASK_DONE_TRIGGERS)
    _has_task_delete = any(t in clean_in for t in _TASK_DELETE_TRIGGERS)

    if not (_has_task_create or _has_task_list or _has_task_done or _has_task_delete):
        return LayerResult.pass_through()

    try:
        if _has_task_create:
            return _handle_create(ctx, clean_in)
        elif _has_task_list:
            return _handle_list(ctx, clean_in)
        elif _has_task_done:
            return _handle_done(ctx, clean_in)
        elif _has_task_delete:
            return _handle_delete(ctx, clean_in)
    except Exception as _e:
        print(Fore.YELLOW + f"[BRAIN] Task detection error: {_e}")
        return LayerResult.pass_through()

    return LayerResult.pass_through()


def _handle_create(ctx, clean_in):
    _task_text = clean_in
    for _trigger in sorted(_TASK_CREATE_TRIGGERS, key=len, reverse=True):
        if _trigger in _task_text:
            _task_text = _task_text.replace(_trigger, "").strip()
            break

    # Strip leading filler words
    _strip_again = True
    while _strip_again:
        _strip_again = False
        for _art in ["to ", "a ", "an ", "the ", "- ", ": "]:
            if _task_text.startswith(_art):
                _task_text = _task_text[len(_art):].strip()
                _strip_again = True
                break

    # Extract due date BEFORE mangling text
    _due_raw = ""
    for _dp, _has_group in _DUE_PATTERNS:
        _dm = re.search(_dp, _task_text, re.IGNORECASE)
        if _dm:
            _due_raw = _dm.group(1) if _dm.lastindex and _has_group else _dm.group(0)
            _task_text = re.sub(_dp, "", _task_text, flags=re.IGNORECASE).strip()
            break

    # Extract priority
    _priority = "medium"
    for _phrases, _pri_val in _PRIORITY_PATTERNS:
        if any(p in clean_in for p in _phrases):
            _priority = _pri_val
            for _pp in _phrases:
                _task_text = _task_text.replace(_pp, "").strip()
            break

    # Clean up whitespace and punctuation
    _task_text = re.sub(r'\s+', ' ', _task_text).strip()
    _task_text = _task_text.strip('.,!-:;')

    if not _task_text:
        _task_text = "task"

    # Pipe delimiter for multi-word text (prevents space-split in tag parser)
    _task_text_safe = _task_text.replace(" ", "|||")
    _due_safe       = _due_raw.replace(" ", "|||") if _due_raw else ""

    _tag = f"action=create text={_task_text_safe} priority={_priority}"
    if _due_safe:
        _tag += f" due={_due_safe}"

    ctx.is_command = True
    return LayerResult.stop(f"Got it. Adding that to your tasks. ###TASK: {_tag}")


def _handle_list(ctx, clean_in):
    _filter = "today" if "today" in clean_in else "all"
    ctx.is_command = True
    return LayerResult.stop(f"###TASK: action=list filter={_filter}")


def _handle_done(ctx, clean_in):
    _search = clean_in
    for _trigger in sorted(_TASK_DONE_TRIGGERS, key=len, reverse=True):
        if _trigger in _search:
            _search = _search.replace(_trigger, "").strip()
            break
    for _art in ["the ", "my ", "a "]:
        if _search.startswith(_art):
            _search = _search[len(_art):].strip()

    _search_tag = _search.replace(" ", "|||") if _search else "task"
    ctx.is_command = True
    return LayerResult.stop(f"Got it. ###TASK: action=complete search={_search_tag}")


def _handle_delete(ctx, clean_in):
    _search = clean_in
    for _trigger in sorted(_TASK_DELETE_TRIGGERS, key=len, reverse=True):
        if _trigger in _search:
            _search = _search.replace(_trigger, "").strip()
            break
    for _art in ["the ", "my ", "a "]:
        if _search.startswith(_art):
            _search = _search[len(_art):].strip()

    _search_tag = _search.replace(" ", "|||") if _search else "task"
    ctx.is_command = True
    return LayerResult.stop(f"Removing it. ###TASK: action=delete search={_search_tag}")