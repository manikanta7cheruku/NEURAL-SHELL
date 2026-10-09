"""
backend/routes/chat.py
POST /api/chat

WHAT CHANGED:
    The old streaming branch called list(generator), waiting for the ENTIRE
    reply before sending anything, and then iterated the already-exhausted
    generator, so the "stream" delivered nothing real. Now:

      stream=true   brain.think(stream_mode="token") returns a generator and
                    each token is sent the moment Ollama produces it, in the
                    format  data: {"token": "..."}\n\n  ending with [DONE].
      stream=false  one JSON body, as before.

    Instant answers (commands, identity, social) arrive as a single event.
    The per-request scan of every stored conversation (a plan-limit log
    line that cost a full database read per message) has been removed.
    Action execution imports are lazy and individually guarded, so one
    missing module can no longer turn every chat into an HTTP 500.
"""

import json
import logging
import random
import re
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

_log = logging.getLogger("seven.chat")
router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
_TAG_RE = re.compile(r"###(\w+):\s*(.*?)(?=###|$)", re.DOTALL)


class ChatRequest(BaseModel):
    text: str
    speaker_id: Optional[str] = "default"
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    actions: List[str] = []
    streaming: bool = False
    file_results: Optional[dict] = None
    task_results: Optional[dict] = None


def _sse(obj) -> str:
    """One Server-Sent Event frame."""
    return f"data: {json.dumps(obj)}\n\n"


def _params(param_str: str) -> dict:
    """Parse 'key=value key2=value2' into a dict."""
    params = {}
    for pair in param_str.strip().split():
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k.strip()] = v.strip()
    return params


def _set_thinking(value: bool) -> None:
    try:
        from backend.api_server import set_state
        set_state("thinking", value)
    except Exception:
        pass


def _build_clean_response(full_response: str, speaker_id: str) -> str:
    """Readable text for replies that contained only action tags."""
    try:
        from backend.api_server import get_state
        tr = get_state().get("task_results")
        if tr:
            action = tr.get("action", "")
            if action == "created":
                return f"Task added: {tr.get('task', {}).get('text', 'task')}."
            if action == "list":
                tasks = tr.get("tasks", [])
                if tasks:
                    names = ", ".join(t.get("text", "")[:30] for t in tasks[:5])
                    more = f" And {len(tasks) - 5} more." if len(tasks) > 5 else ""
                    return f"{len(tasks)} pending task{'s' if len(tasks) != 1 else ''}: {names}.{more}"
                return "No pending tasks."
            if action == "completed":
                return "Task marked complete."
            if action == "deleted":
                return "Task removed."
            return "Done."
    except Exception as exc:
        _log.debug("task results read failed: %s", exc)

    try:
        import hands.scheduler as sched
        for chunk in re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
            p = _params(chunk)
            p["speaker_id"] = speaker_id
            action = p.get("action", "")
            if action in ("reminder", "alarm", "timer", "event"):
                msg = p.get("message", "").replace("_", " ").replace("|||", " ")
                when = p.get("time", "").replace("_", " ")
                if msg and when:
                    return f"Reminder set: {msg}, {when}."
                return f"Reminder set: {msg}." if msg else "Reminder set."
            if action == "list":
                return sched.list_schedules(speaker_id=speaker_id)[1]
            if action == "cancel":
                return "Schedule cancelled."
    except Exception as exc:
        _log.debug("schedule response build failed: %s", exc)
    return "."


def _execute_actions(action_list, full_response, speaker_id):
    """Execute command tags produced by the instant (Python) layers."""
    def _telemetry():
        try:
            import telemetry
            telemetry.log_activity()
        except Exception:
            pass

    for chunk in re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        if params:
            try:
                import hands.windows as hands_windows
                hands_windows.manage_window(params)
            except Exception as exc:
                _log.warning("window action failed: %s", exc)

    for chunk in re.findall(r"###SYS:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        if params:
            try:
                import hands.system as system_mod
                system_mod.manage_system(params)
            except Exception as exc:
                _log.warning("system action failed: %s", exc)

    for chunk in re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        params["speaker_id"] = speaker_id
        try:
            import hands.scheduler as scheduler_mod
            scheduler_mod.manage_schedule(params)
            _telemetry()
        except Exception as exc:
            _log.warning("scheduler action failed: %s", exc)

    for chunk in re.findall(r"###TASK:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        if params:
            try:
                _task_action(params)
            except Exception as exc:
                _log.warning("task action failed: %s", exc, exc_info=True)

    for cmd_type, arg in re.findall(r"###(OPEN|CLOSE):\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        target = arg.replace('"', "").replace("'", "").replace(",", "").replace(".", "").strip()
        if not target:
            continue
        try:
            import hands.core as core
            core.open_app(target) if cmd_type == "OPEN" else core.close_app(target)
            _telemetry()
        except Exception as exc:
            _log.warning("app action failed: %s", exc)


def _task_action(params: dict) -> None:
    """Create, list, complete or delete a task and publish the result for the UI."""
    from datetime import date, datetime, timedelta
    from backend.api_server import set_state
    from backend.routes.tasks import (_get_conn, _row_to_dict, db_find_task_by_text,
                                      db_get_pending_list)
    action = params.get("action", "")

    if action == "create":
        text = params.get("text", "").replace("|||", " ").replace("_", " ")
        priority = params.get("priority", "medium").lower()
        priority = priority if priority in ("low", "medium", "high") else "medium"
        due_raw = params.get("due", "").replace("_", " ").lower()
        due_date = None
        if due_raw:
            try:
                if "today" in due_raw or "tonight" in due_raw:
                    due_date = date.today().isoformat()
                elif "tomorrow" in due_raw:
                    due_date = (date.today() + timedelta(days=1)).isoformat()
                else:
                    from hands.scheduler import _parse_time
                    parsed = _parse_time(due_raw)
                    due_date = parsed.date().isoformat() if parsed else None
            except Exception:
                due_date = None
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (text, due_date, due_time, priority, completed, created_at,"
                " completed_at, tags, description, subtasks)"
                " VALUES (?, ?, NULL, ?, 0, ?, NULL, NULL, NULL, '[]')",
                (text, due_date, priority, datetime.now().isoformat()))
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        set_state("task_results", {"action": "created", "task": _row_to_dict(row)})

    elif action == "list":
        set_state("task_results", {"action": "list", "tasks": db_get_pending_list()})

    elif action in ("complete", "delete"):
        found = db_find_task_by_text(params.get("search", "").replace("_", " "))
        if found:
            with _get_conn() as conn:
                if action == "complete":
                    conn.execute("UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
                                 (datetime.now().isoformat(), found["id"]))
                else:
                    conn.execute("DELETE FROM tasks WHERE id = ?", (found["id"],))
                conn.commit()
            set_state("task_results", {"action": "completed" if action == "complete" else "deleted",
                                       "task_id": found["id"]})


def _stream_tokens(gen):
    """SSE body for a live token generator. Always clears the thinking state."""
    started, first_ms = time.time(), None
    try:
        for token in gen:
            if first_ms is None:
                first_ms = int((time.time() - started) * 1000)
            yield _sse({"token": token})
        yield _sse({"done": True, "first_token_ms": first_ms,
                    "total_ms": int((time.time() - started) * 1000)})
        yield "data: [DONE]\n\n"
    except Exception as exc:
        _log.error("stream failed: %s", exc, exc_info=True)
        yield _sse({"error": str(exc)})
    finally:
        try:
            gen.close()
        except Exception:
            pass
        _set_thinking(False)


def _stream_text(clean: str, meta: dict):
    """SSE body for an instant (non-LLM) answer."""
    try:
        yield _sse(meta)
        yield _sse({"token": clean})
        yield _sse({"done": True})
        yield "data: [DONE]\n\n"
    finally:
        _set_thinking(False)


@router.post("/api/chat", summary="Send message to Seven",
             description="Runs the message through Seven's brain pipeline. With stream=true the "
                         "reply is delivered as Server-Sent Events, one token per event.")
def chat(req: ChatRequest):
    """Send a text message to Seven's brain."""
    import brain
    from backend.api_server import get_state, set_state

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")

    _set_thinking(True)
    try:
        import telemetry
        telemetry.log_activity()
    except Exception as exc:
        _log.debug("telemetry skipped: %s", exc)

    streaming_started = False
    try:
        mode = "token" if req.stream else "text"
        response = brain.think(text, speaker_id=req.speaker_id or "default", stream_mode=mode)

        if isinstance(response, tuple) and len(response) == 2 and response[0] == "__STREAM__":
            _, gen = response
            if req.stream:
                streaming_started = True
                return StreamingResponse(_stream_tokens(gen), media_type="text/event-stream",
                                         headers=_SSE_HEADERS)
            response = "".join(gen)

        if response == "":
            return ChatResponse(response=random.choice(["Good.", "Alright.", "Fair.", "Okay.", "Works."]))
        full_response = response or "Processing error."

        action_list = [f"{cmd}:{arg.strip()}" for cmd, arg in _TAG_RE.findall(full_response)]
        clean = _TAG_RE.sub("", full_response).strip()
        _execute_actions(action_list, full_response, req.speaker_id or "default")
        if not clean:
            clean = _build_clean_response(full_response, req.speaker_id or "default")

        state = get_state()
        file_results, task_results = state.get("file_search_results"), state.get("task_results")
        if file_results:
            set_state("file_search_results", None)
        if task_results:
            set_state("task_results", None)

        if req.stream:
            streaming_started = True
            meta = {"actions": action_list, "file_results": file_results, "task_results": task_results}
            return StreamingResponse(_stream_text(clean, meta), media_type="text/event-stream",
                                     headers=_SSE_HEADERS)
        return ChatResponse(response=clean, actions=action_list, streaming=False,
                            file_results=file_results, task_results=task_results)

    except HTTPException:
        raise
    except Exception as exc:
        _log.error("chat failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if not streaming_started:
            _set_thinking(False)