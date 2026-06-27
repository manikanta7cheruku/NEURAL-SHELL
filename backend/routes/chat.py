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
        actions = re.findall(r"###(\w+):\s*(.*?)(?=###|$)", full_response)
        action_list = [f"{cmd}:{arg.strip()}" for cmd, arg in actions]

        # Clean response (remove tags for display)
        clean_response = re.sub(r"###\w+:\s*[^\n]*", "", full_response).strip()
        if not clean_response or clean_response == "":
            # Empty = acknowledgement word, Seven stays silent in voice
            # In chat UI, show a minimal response instead of error
            clean_response = "."

        # Execute commands if present
        _execute_actions(action_list, full_response, req.speaker_id)

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

        # Pull file search results from shared state if brain.py set them
        file_results = None
        try:
            from backend.api_server import get_state as _get_state
            _current_state = _get_state()
            file_results = _current_state.get("file_search_results")
            # Clear after reading so next request starts fresh
            if file_results:
                set_state("file_search_results", None)
        except Exception:
            pass

        return ChatResponse(
            response=clean_response,
            actions=action_list,
            streaming=is_streaming,
            file_results=file_results
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
    window_cmds = re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", full_response)
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
    sys_cmds = re.findall(r"###SYS:\s*(.*?)(?=###|$)", full_response)
    for param_str in sys_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        if params:
            system_mod.manage_system(params)

    # Scheduler commands
    sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response)
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

    # App commands
    app_cmds = re.findall(r"###(OPEN|CLOSE):\s*(.*?)(?=###|$)", full_response)
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