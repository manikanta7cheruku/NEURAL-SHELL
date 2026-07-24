"""
backend/routes/chat.py
Handles: POST /api/chat
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import re

router = APIRouter()


class ChatRequest(BaseModel):
    text: str
    speaker_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    actions: List[str] = []
    streaming: bool = False
    file_results: Optional[dict] = None
    task_results: Optional[dict] = None


@router.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a text message to Seven's brain."""
    import brain
    import telemetry
    from backend.api_server import set_state, check_limit

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    set_state("thinking", True)

    try:
        telemetry.log_activity()
    except Exception:
        pass

    try:
        response = brain.think(req.text.strip(), speaker_id=req.speaker_id)

        try:
            telemetry.log_activity()
        except Exception:
            pass

        # Handle streaming response — flatten it for REST API
        is_streaming = (
            isinstance(response, tuple)
            and len(response) == 2
            and response[0] == "__STREAM__"
        )

        if is_streaming:
            _, gen = response
            parts = list(gen)
            full_response = " ".join(parts)
        else:
            full_response = response if response else "Processing error."

        # Extract action tags
        actions = re.findall(r"###(\w+):\s*(.*?)(?=###|$)", full_response, re.DOTALL)
        action_list = [f"{cmd}:{arg.strip()}" for cmd, arg in actions]

        # Clean response (remove tags for display)
        clean_response = re.sub(r"###\w+:\s*.*?(?=###|$)", "", full_response, flags=re.DOTALL).strip()

        # Execute commands first so task_results state is populated
        _execute_actions(action_list, full_response, req.speaker_id)

        # Build human-readable response if empty after tag removal
        if not clean_response or clean_response == "":
            try:
                from backend.api_server import get_state as _gs
                _tr = _gs().get("task_results")
                if _tr:
                    _ta = _tr.get("action", "")
                    if _ta == "created":
                        _t = _tr.get("task", {})
                        clean_response = f"Task added: {_t.get('text', 'task')}."
                    elif _ta == "list":
                        _tl = _tr.get("tasks", [])
                        if _tl:
                            _names = ", ".join(
                                t.get("text", "")[:30] for t in _tl[:5]
                            )
                            clean_response = (
                                f"{len(_tl)} pending task{'s' if len(_tl) != 1 else ''}: "
                                f"{_names}."
                                + (f" And {len(_tl) - 5} more." if len(_tl) > 5 else "")
                            )
                        else:
                            clean_response = "No pending tasks."
                    elif _ta == "completed":
                        clean_response = "Task marked complete."
                    elif _ta == "deleted":
                        clean_response = "Task removed."
                    else:
                        clean_response = "Done."
                else:
                    # Check if a schedule was just created
                    # The scheduler returns speech text through the action execution
                    # Extract it from the SCHED tag execution results
                    _sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response, re.DOTALL)
                    if _sched_cmds:
                        # Schedule was processed. The manage_schedule function
                        # already returned a speech string. Re-execute to get it.
                        try:
                            import hands.scheduler as _sched_mod
                            for _sc in _sched_cmds:
                                _sp = {}
                                for pair in _sc.strip().split():
                                    if "=" in pair:
                                        k, v = pair.split("=", 1)
                                        _sp[k.strip()] = v.strip()
                                _sp["speaker_id"] = req.speaker_id
                                _action = _sp.get("action", "")
                                if _action in ("reminder", "alarm", "timer", "event"):
                                    # Schedule already created by _execute_actions
                                    # Just build a confirmation message
                                    _msg = _sp.get("message", "").replace("_", " ").replace("|||", " ")
                                    _time = _sp.get("time", "").replace("_", " ")
                                    if _msg and _time:
                                        clean_response = f"Reminder set: {_msg}, {_time}."
                                    elif _msg:
                                        clean_response = f"Reminder set: {_msg}."
                                    else:
                                        clean_response = "Reminder set."
                                    break
                                elif _action == "list":
                                    _, _speech = _sched_mod.list_schedules(speaker_id=req.speaker_id)
                                    clean_response = _speech
                                    break
                                elif _action == "cancel":
                                    clean_response = "Schedule cancelled."
                                    break
                        except Exception:
                            clean_response = "Schedule set."
                    else:
                        clean_response = "."
            except Exception:
                clean_response = "."

        # Store conversation in memory (enforce plan limit)
        try:
            from memory import seven_memory
            if len(req.text.strip()) > 3 and not full_response.strip().startswith("###"):
                clean_for_memory = re.sub(r'###\w+:\s*\S+', '', full_response).strip()
                if clean_for_memory:
                    try:
                        all_convos = seven_memory.conversations.get()
                        convo_count = len(all_convos["documents"]) if all_convos and all_convos.get("documents") else 0
                    except Exception:
                        convo_count = 0

                    limit_check = check_limit("conversation_history", convo_count)
                    if limit_check["allowed"]:
                        seven_memory.store_conversation(
                            req.text.strip(), clean_for_memory,
                            user_id=req.speaker_id
                        )
                    else:
                        print(f"[API] Conversation memory full ({convo_count}/{limit_check['limit']}) — tier: {limit_check['tier']}")
        except Exception:
            pass

        # Pull file search results from shared state
        file_results = None
        task_results = None
        try:
            from backend.api_server import get_state as _get_state
            _current_state = _get_state()
            file_results = _current_state.get("file_search_results")
            task_results = _current_state.get("task_results")
            if file_results:
                set_state("file_search_results", None)
            if task_results:
                set_state("task_results", None)
        except Exception:
            pass

        return ChatResponse(
            response=clean_response,
            actions=action_list,
            streaming=is_streaming,
            file_results=file_results,
            task_results=task_results
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        set_state("thinking", False)


def _execute_actions(action_list, full_response, speaker_id):
    """Execute extracted command tags from brain response."""
    import re
    import hands.core as core
    import hands.system as system_mod
    import hands.scheduler as scheduler_mod

    try:
        import telemetry
        _telemetry = telemetry
    except ImportError:
        _telemetry = None

    # Window commands
    window_cmds = re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", full_response, re.DOTALL)
    for param_str in window_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        if params:
            try:
                import hands.windows as hands_windows
                hands_windows.manage_window(params)
            except Exception:
                pass

    # System commands
    sys_cmds = re.findall(r"###SYS:\s*(.*?)(?=###|$)", full_response, re.DOTALL)
    for param_str in sys_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        if params:
            system_mod.manage_system(params)

    # Scheduler commands
    sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response, re.DOTALL)
    for param_str in sched_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        params["speaker_id"] = speaker_id
        if params:
            try:
                scheduler_mod.manage_schedule(params)
                if _telemetry:
                    _telemetry.log_activity()
            except Exception as e:
                print(f"[API] Scheduler error: {e}")
    
    # Task commands
    task_cmds = re.findall(r"###TASK:\s*(.*?)(?=###|$)", full_response, re.DOTALL)
    for param_str in task_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        if not params:
            continue

        action = params.get("action", "")

        try:
            from backend.api_server import set_state as _task_set

            if action == "create":
                text     = params.get("text", "").replace("|||", " ").replace("_", " ")
                priority = params.get("priority", "medium")
                due_raw  = params.get("due", "").replace("_", " ")

                due_date = None
                if due_raw:
                    try:
                        from datetime import date, timedelta
                        dl = due_raw.lower()
                        if "today" in dl or "tonight" in dl:
                            due_date = date.today().isoformat()
                        elif "tomorrow" in dl:
                            due_date = (date.today() + timedelta(days=1)).isoformat()
                        else:
                            from hands.scheduler import _parse_time
                            parsed = _parse_time(due_raw)
                            if parsed:
                                due_date = parsed.date().isoformat()
                    except Exception:
                        pass

                try:
                    from backend.routes.tasks import _get_conn, _row_to_dict
                    from datetime import datetime as _dt

                    with _get_conn() as conn:
                        cursor = conn.execute(
                            "INSERT INTO tasks (text, due_date, due_time, priority,"
                            " completed, created_at, completed_at, tags,"
                            " description, subtasks)"
                            " VALUES (?, ?, NULL, ?, 0, ?, NULL, NULL, NULL, '[]')",
                            (text, due_date, priority, _dt.now().isoformat())
                        )
                        conn.commit()
                        new_id = cursor.lastrowid
                        row = conn.execute(
                            "SELECT * FROM tasks WHERE id = ?", (new_id,)
                        ).fetchone()

                    _task_set("task_results", {
                        "action": "created",
                        "task":   _row_to_dict(row),
                    })
                    print(f"[CHAT] Task created: {text}")

                except Exception as _task_create_err:
                    print(f"[CHAT] Task create DB error: {_task_create_err}")
                    import traceback; traceback.print_exc()

            elif action == "list":
                from backend.routes.tasks import db_get_pending_list
                pending = db_get_pending_list()
                _task_set("task_results", {
                    "action": "list",
                    "tasks": pending,
                })

            elif action == "complete":
                search = params.get("search", "").replace("_", " ")
                from backend.routes.tasks import db_find_task_by_text, _get_conn
                from datetime import datetime as _dt
                found = db_find_task_by_text(search)
                if found:
                    with _get_conn() as conn:
                        conn.execute(
                            "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
                            (_dt.now().isoformat(), found["id"])
                        )
                        conn.commit()
                    _task_set("task_results", {
                        "action": "completed",
                        "task_id": found["id"],
                    })

            elif action == "delete":
                search = params.get("search", "").replace("_", " ")
                from backend.routes.tasks import db_find_task_by_text, _get_conn
                found = db_find_task_by_text(search)
                if found:
                    with _get_conn() as conn:
                        conn.execute("DELETE FROM tasks WHERE id = ?", (found["id"],))
                        conn.commit()
                    _task_set("task_results", {
                        "action": "deleted",
                        "task_id": found["id"],
                    })

        except Exception as e:
            print(f"[CHAT] Task action error: {e}")
            import traceback; traceback.print_exc()

    # App commands
    app_cmds = re.findall(r"###(OPEN|CLOSE):\s*(.*?)(?=###|$)", full_response, re.DOTALL)
    for cmd_type, arg in app_cmds:
        clean_arg = arg.replace('"', '').replace("'", "").replace(",", "").replace(".", "").strip()
        if not clean_arg:
            continue
        try:
            if cmd_type == "OPEN":
                core.open_app(clean_arg)
            elif cmd_type == "CLOSE":
                core.close_app(clean_arg)
            if _telemetry:
                _telemetry.log_activity()
        except Exception as e:
            print(f"[API] App command error: {e}")  