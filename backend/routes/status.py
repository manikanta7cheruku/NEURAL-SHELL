"""
backend/routes/status.py
Handles: GET /api/status, GET /api/version, WS /ws/status
"""

from fastapi import APIRouter
import logging

_log = logging.getLogger('seven.status')
from fastapi import WebSocket
import asyncio
import datetime
import time

router = APIRouter()


@router.get("/api/status")
def get_status():
    """Get current Seven system status. Guaranteed to never return 500."""
    try:
        from backend.api_server import _state, _start_time
    except Exception:
        return {
            "listening": False, "speaking": False, "thinking": False,
            "user_text": "", "seven_text": "", "mood": "neutral",
            "mood_value": 0.5, "model": "unknown", "streaming": False,
            "uptime": "0h 0m", "uptime_seconds": 0, "speaker": "default",
            "version": "1.3.2"
        }

    try:
        model = "unknown"
        version = "1.3.2"
        try:
            import config
            if hasattr(config, 'KEY') and isinstance(config.KEY, dict):
                model = config.KEY.get("brain", {}).get("model_name", "unknown")
                version = config.KEY.get("version", "1.3.2")
        except Exception:
            pass

        try:
            import telemetry as _tel
            _tel.log_activity()
        except Exception:
            pass

        uptime_secs = int(time.time() - _start_time)
        hours = uptime_secs // 3600
        minutes = (uptime_secs % 3600) // 60

        mood_label = "neutral"
        mood_value = 0.5
        try:
            import config as _cfg
            if hasattr(_cfg, 'KEY') and _cfg.KEY.get("setup_complete", False):
                from memory.mood import mood_engine
                if mood_engine is not None:
                    mood_status = mood_engine.get_status()
                    if isinstance(mood_status, dict):
                        mood_label = str(mood_status.get("label", "neutral"))
                        mood_value = float(mood_status.get("mood_value", 0.5))
        except Exception:
            pass

        return {
            "listening":      bool(_state.get("listening", False)),
            "speaking":       bool(_state.get("speaking",  False)),
            "thinking":       bool(_state.get("thinking",  False)),
            "user_text":      str(_state.get("user_text",  "")),
            "seven_text":     str(_state.get("seven_text", "")),
            "mood":           mood_label,
            "mood_value":     mood_value,
            "model":          str(model),
            "streaming":      False,
            "uptime":         f"{hours}h {minutes}m",
            "uptime_seconds": int(uptime_secs),
            "speaker":        str(_state.get("current_speaker", "default")),
            "version":        str(version)
        }
    except Exception:
        return {
            "listening": False, "speaking": False, "thinking": False,
            "user_text": "", "seven_text": "", "mood": "neutral",
            "mood_value": 0.5, "model": "unknown", "streaming": False,
            "uptime": "0h 0m", "uptime_seconds": 0, "speaker": "default",
            "version": "1.3.2"
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
    except Exception as _e:
        _log.debug(f"Status check non-critical: {_e}")