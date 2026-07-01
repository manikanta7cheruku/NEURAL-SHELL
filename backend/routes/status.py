"""
backend/routes/status.py
Handles: GET /api/status, GET /api/version, WS /ws/status
"""

from fastapi import APIRouter
from fastapi import WebSocket
import asyncio
import datetime
import time

router = APIRouter()


@router.get("/api/status")
def get_status():
    """Get current Seven system status. Bulletproof — never 500s."""
    # Import here to avoid circular import
    from backend.api_server import _state, _start_time

    try:
        try:
            import config
            model = config.KEY.get("brain", {}).get("model_name", "unknown")
            version = config.KEY.get("version", "1.1.4")
        except Exception as e:
            print(f"[API] /status config error: {e}")
            model = "unknown"
            version = "1.1.4"

        try:
            import telemetry as _tel
            _tel.log_activity()
        except Exception as e:
            print(f"[API] /status telemetry error: {e}")

        uptime_secs = int(time.time() - _start_time)
        hours = uptime_secs // 3600
        minutes = (uptime_secs % 3600) // 60

        mood_label = "neutral"
        mood_value = 0.5
        try:
            from memory.mood import mood_engine
            mood_status = mood_engine.get_status()
            mood_label = mood_status.get("label", "neutral")
            mood_value = mood_status.get("mood_value", 0.5)
        except Exception as e:
            print(f"[API] /status mood error: {e}")

        return {
            "listening":      _state.get("listening",  False),
            "speaking":       _state.get("speaking",   False),
            "thinking":       _state.get("thinking",   False),
            "user_text":      _state.get("user_text",  ""),
            "seven_text":     _state.get("seven_text", ""),
            "mood":           mood_label,
            "mood_value":     mood_value,
            "model":          model,
            "streaming":      False,
            "uptime":         f"{hours}h {minutes}m",
            "uptime_seconds": uptime_secs,
            "speaker":        _state.get("current_speaker", "default"),
            "version":        version
        }
    except Exception as e:
        import traceback
        print(f"[API] /status CATASTROPHIC error: {e}")
        traceback.print_exc()
        return {
            "listening":      False,
            "speaking":       False,
            "thinking":       False,
            "mood":           "neutral",
            "mood_value":     0.5,
            "model":          "unknown",
            "streaming":      False,
            "uptime":         "0h 0m",
            "uptime_seconds": 0,
            "speaker":        "default",
            "version":        "1.1.4",
            "error_debug":    str(e)
        }

@router.post("/api/interrupt")
def interrupt_speech():
    """Interrupt Seven's current speech immediately."""
    try:
        import mouth as _mouth
        _mouth.interrupt()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    

@router.get("/api/version")
def get_version():
    """Get version info."""
    import config
    return {
        "version":    config.KEY.get("version", "1.1.4"),
        "build_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "name":       config.KEY.get("identity", {}).get("name", "Seven")
    }


@router.websocket("/ws/status")
async def status_websocket(websocket: WebSocket):
    """Real-time status updates via WebSocket — pushes every 300ms."""
    from backend.api_server import _state

    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "listening":  _state.get("listening",  False),
                "thinking":   _state.get("thinking",   False),
                "speaking":   _state.get("speaking",   False),
                "user_text":  _state.get("user_text",  ""),
                "seven_text": _state.get("seven_text", ""),
            })
            await asyncio.sleep(0.3)
    except Exception:
        pass