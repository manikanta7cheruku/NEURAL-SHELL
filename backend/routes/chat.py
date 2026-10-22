"""
backend/routes/chat.py
POST /api/chat

    stream=true   Server-Sent Events, one token per event:
                    data: {"conversation_id": "..."}            first
                    data: {"token": "..."}                      many
                    data: {"warning": "..."}                    only if saving failed
                    data: {"done": true, "meta": {...}}         timings and what was used
                    data: [DONE]
    stream=false  one JSON body.

Actions requested by the instant layers (open, close, window, system, schedule,
task) run here and produce RECEIPTS. The reply is reconciled with them: an
action that failed is reported as failed, never as done. Risky actions pause
for a yes. Receipts are fed back to the brain, which records outcomes and can
offer to remember a corrected app name.
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

from brain_modules import action_receipts

_log = logging.getLogger("seven.chat")
router = APIRouter()
_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
_TAG_RE = re.compile(r"###(\w+):\s*(.*?)(?=###|$)", re.DOTALL)


class ChatRequest(BaseModel):
    text: str
    speaker_id: Optional[str] = "default"
    stream: Optional[bool] = False
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    actions: List[str] = []
    streaming: bool = False
    file_results: Optional[dict] = None
    task_results: Optional[dict] = None
    conversation_id: Optional[str] = None
    meta: Optional[dict] = None


def _sse(obj) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _params(param_str: str) -> dict:
    out = {}
    for pair in param_str.strip().split():
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _set_thinking(value: bool) -> None:
    try:
        from backend.api_server import set_state
        set_state("thinking", value)
    except Exception:
        pass


def _build_clean_response(full_response: str, speaker_id: str) -> str:
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
            return {"completed": "Task marked complete.", "deleted": "Task removed."}.get(action, "Done.")
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
                return f"Reminder set: {msg}, {when}." if msg and when else (f"Reminder set: {msg}." if msg else "Reminder set.")
            if action == "list":
                return sched.list_schedules(speaker_id=speaker_id)[1]
            if action == "cancel":
                return "Schedule cancelled."
    except Exception as exc:
        _log.debug("schedule response build failed: %s", exc)
    return "."


def _task_action(params: dict) -> None:
    from datetime import date, datetime, timedelta
    from backend.api_server import set_state
    from backend.routes.tasks import _get_conn, _row_to_dict, db_find_task_by_text, db_get_pending_list
    action = params.get("action", "")
    if action == "create":
        text = params.get("text", "").replace("|||", " ").replace("_", " ")
        priority = params.get("priority", "medium").lower()
        priority = priority if priority in ("low", "medium", "high") else "medium"
        due_raw, due_date = params.get("due", "").replace("_", " ").lower(), None
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
                "INSERT INTO tasks (text, due_date, due_time, priority, completed, created_at, completed_at, tags,"
                " description, subtasks) VALUES (?, ?, NULL, ?, 0, ?, NULL, NULL, NULL, '[]')",
                (text, due_date, priority, datetime.now().isoformat()))
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        set_state("task_results", {"action": "created", "task": _row_to_dict(row)})
    elif action == "list":
        set_state("task_results", {"action": "list", "tasks": db_get_pending_list()})
    elif action in ("complete", "delete"):
        # Raises unless the database really changed, so the receipt (and the reply) can't claim a no-op.
        from brain_modules import lifecycle
        params = {**params, "search": params.get("search", "").replace("_", " ")}
        lifecycle.execute_task_action(params)
        set_state("task_results", {"action": "completed" if action == "complete" else "deleted",
                                   "task_id": params.get("id")})


def _execute_actions(action_list, full_response, speaker_id) -> List[action_receipts.ActionReceipt]:
    """Run every action tag and return one receipt per action. Never raises."""
    receipts: List[action_receipts.ActionReceipt] = []

    def _telemetry():
        try:
            import telemetry
            telemetry.log_activity()
        except Exception:
            pass

    def _run(kind, target, fn, verify=None):
        r = action_receipts.run_action(kind, target, fn, verify)
        receipts.append(r)
        if r.status != "failed":
            _telemetry()

    for chunk in re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        if params:
            def _w(p=params):
                import hands.windows as hw
                return hw.manage_window(p)
            _run("WINDOW", params.get("target", params.get("action", "")), _w)
    for chunk in re.findall(r"###SYS:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        if params:
            def _s(p=params):
                import hands.system as sm
                return sm.manage_system(p)
            _run("SYS", params.get("action", ""), _s)
    for chunk in re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        params["speaker_id"] = speaker_id

        def _sc(p=params):
            import hands.scheduler as sc
            return sc.manage_schedule(p)
        _run("SCHED", params.get("action", ""), _sc)
    for chunk in re.findall(r"###TASK:\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        params = _params(chunk)
        if params:
            _run("TASK", params.get("action", ""), lambda p=params: _task_action(p))
    for cmd_type, arg in re.findall(r"###(OPEN|CLOSE):\s*(.*?)(?=###|$)", full_response, re.DOTALL):
        target = arg.replace('"', "").replace("'", "").replace(",", "").replace(".", "").strip()
        if not target:
            continue

        def _oc(k=cmd_type, t=target):
            import hands.core as core
            return core.open_app(t) if k == "OPEN" else core.close_app(t)
        _run(cmd_type, target.replace("ALL_", ""), _oc,
             lambda k=cmd_type, t=target: action_receipts.verify_running(t, expect=(k == "OPEN")))
    return receipts


def _gate_risky(full_response: str, speaker_id: str, conv_id: str):
    """(blocked_tags_text, question) when a risky action is waiting for a yes, else (None, None)."""
    import brain
    risky = [(k, a) for k, a in _TAG_RE.findall(full_response) if brain.needs_confirmation(k, a.strip())]
    if not risky:
        return None, None
    tags = " ".join(f"###{k}: {a.strip()}" for k, a in risky)
    names = ", ".join(a.strip().replace("ALL_", "all ") for _k, a in risky)
    return tags, brain.request_confirmation(speaker_id, conv_id, tags, f"That would affect {names}, and unsaved work could be lost.")


def _finish_string(response, req, conv_id):
    """Execute actions, reconcile the reply with receipts, collect UI results."""
    import brain
    from backend.api_server import get_state, set_state
    speaker = req.speaker_id or "default"
    full = response or "Processing error."
    clean = _TAG_RE.sub("", full).strip()
    action_list = [f"{k}:{a.strip()}" for k, a in _TAG_RE.findall(full)]
    trace = brain.get_trace(speaker, conv_id)
    receipts: list = []
    if action_list:
        blocked, question = (None, None) if trace.get("confirmed") else _gate_risky(full, speaker, conv_id)
        if blocked:
            clean, action_list = question, []
        else:
            receipts = _execute_actions(action_list, full, speaker)
            clean = action_receipts.reconcile_reply(clean or _build_clean_response(full, speaker), receipts)
            follow = brain.note_receipts(speaker, conv_id, receipts)
            if follow:
                clean = f"{clean} {follow}".strip()
    if not clean:
        clean = _build_clean_response(full, speaker)
    state = get_state()
    files, tasks = state.get("file_search_results"), state.get("task_results")
    if files:
        set_state("file_search_results", None)
    if tasks:
        set_state("task_results", None)
    return clean, action_list, files, tasks, [r.to_dict() for r in receipts], trace


def _stream_tokens(gen, conv_id, speaker):
    import brain
    started, first_ms = time.time(), None
    try:
        yield _sse({"conversation_id": conv_id})
        for token in gen:
            if first_ms is None:
                first_ms = int((time.time() - started) * 1000)
            yield _sse({"token": token})
        trace = brain.get_trace(speaker, conv_id)
        if trace.get("storage_error"):
            yield _sse({"warning": f"This message was not saved: {trace['storage_error']}"})
        trace.setdefault("first_token_ms", first_ms)
        yield _sse({"done": True, "meta": trace})
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


def _stream_text(clean, meta, conv_id):
    try:
        yield _sse({"conversation_id": conv_id})
        yield _sse({k: v for k, v in meta.items() if k in ("actions", "file_results", "task_results", "receipts")})
        yield _sse({"token": clean})
        trace = meta.get("trace") or {}
        if trace.get("storage_error"):
            yield _sse({"warning": f"This message was not saved: {trace['storage_error']}"})
        yield _sse({"done": True, "meta": trace})
        yield "data: [DONE]\n\n"
    finally:
        _set_thinking(False)


@router.post("/api/chat", summary="Send message to Seven")
def chat(req: ChatRequest):
    """Run one message through Seven's brain."""
    import brain
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    _set_thinking(True)
    try:
        import telemetry
        telemetry.log_activity()
    except Exception:
        pass
    streaming_started = False
    try:
        speaker = req.speaker_id or "default"
        conv_id = brain.resolve_conversation(speaker, req.conversation_id)
        response = brain.think(text, speaker_id=speaker, stream_mode="token" if req.stream else "text",
                               conversation_id=conv_id)
        if isinstance(response, tuple) and len(response) == 2 and response[0] == "__STREAM__":
            _, gen = response
            if req.stream:
                streaming_started = True
                return StreamingResponse(_stream_tokens(gen, conv_id, speaker), media_type="text/event-stream",
                                         headers=_SSE_HEADERS)
            response = "".join(gen)
        if response == "":
            return ChatResponse(response=random.choice(["Good.", "Alright.", "Fair.", "Okay.", "Works."]),
                                conversation_id=conv_id)
        clean, actions, files, tasks, receipts, trace = _finish_string(response, req, conv_id)
        if req.stream:
            streaming_started = True
            meta = {"actions": actions, "file_results": files, "task_results": tasks,
                    "receipts": receipts, "trace": trace}
            return StreamingResponse(_stream_text(clean, meta, conv_id), media_type="text/event-stream",
                                     headers=_SSE_HEADERS)
        return ChatResponse(response=clean, actions=actions, file_results=files, task_results=tasks,
                            conversation_id=conv_id, meta=trace)
    except HTTPException:
        raise
    except Exception as exc:
        _log.error("chat failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if not streaming_started:
            _set_thinking(False)
