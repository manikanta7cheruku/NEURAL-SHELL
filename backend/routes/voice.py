"""
backend/routes/voice.py
Seven's voice and hearing, for Settings and setup.

    GET  /api/voice/voices     the natural voices, which one is chosen, and whether they're installed
    POST /api/voice/preview    hear a voice say a line (stops any preview already playing)
    POST /api/voice/install    download the natural voice if it isn't here yet; GET for progress
    GET  /api/voice/mics       the microphones Windows offers
    POST /api/voice/test       say something: returns exactly what Seven heard (or why it ignored it), without acting
"""
import json
import os
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _voice_config() -> dict:
    try:
        p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "config.json")
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("voice", {}) or {}
    except Exception:
        return {}


@router.get("/api/voice/voices", summary="Natural voices and the current choice")
def list_voices():
    from mouth import voices
    v = _voice_config()
    current = v.get("voice_id") if voices.is_natural(v.get("voice_id", "")) else voices.DEFAULT_VOICE
    return {
        "ready": voices.kokoro_ready(),
        "size_mb": voices.KOKORO_SIZE_MB,
        "current": {"voice_id": current, "speed": voices.speed_factor(v.get("speed", 1.0))},
        "voices": [dict(x, ready=voices.kokoro_ready()) for x in voices.NATURAL],
    }


class PreviewRequest(BaseModel):
    voice_id: str
    speed: float = 1.0
    text: str = ""


_preview_lock = threading.Lock()


@router.post("/api/voice/preview", summary="Hear a voice")
def preview(req: PreviewRequest):
    from mouth import voices
    from mouth.engine import ENGINE
    if not voices.kokoro_ready():
        raise HTTPException(status_code=409, detail="The natural voice is still downloading.")
    name = next((x["name"] for x in voices.NATURAL if x["id"] == req.voice_id), "Seven")
    text = req.text.strip()[:200] or f"Hi, I'm {name}. This is how I'll sound when I talk to you."
    ENGINE.stop()                                         # a new preview replaces the one playing

    def play():
        with _preview_lock:
            ENGINE.say([text], voice=req.voice_id, speed=voices.speed_factor(req.speed))
    threading.Thread(target=play, daemon=True, name="VoicePreview").start()
    return {"ok": True, "text": text}


@router.post("/api/voice/stop", summary="Stop a preview")
def stop_preview():
    from mouth.engine import ENGINE
    ENGINE.stop()
    return {"ok": True}


_install_thread = None


@router.post("/api/voice/install", summary="Download the natural voice")
def install():
    global _install_thread
    from mouth import voices
    if voices.kokoro_ready():
        return {"status": "done", "progress": 100}
    if _install_thread is None or not _install_thread.is_alive():
        from backend.bootstrap import ensure_voice_model
        _install_thread = threading.Thread(target=ensure_voice_model, daemon=True, name="VoiceInstall")
        _install_thread.start()
    return install_status()


@router.get("/api/voice/install", summary="Natural voice download progress")
def install_status():
    from mouth import voices
    if voices.kokoro_ready():
        return {"status": "done", "progress": 100}
    try:
        from backend.bootstrap import _bootstrap_state
        s = _bootstrap_state.get("voice_model", {})
        return {"status": s.get("status", "pending"), "progress": s.get("progress", 0), "error": s.get("error")}
    except Exception:
        return {"status": "pending", "progress": 0}


@router.get("/api/voice/mics", summary="Microphones")
def mics():
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        try:
            default = pa.get_default_input_device_info().get("name", "")
        except Exception:
            default = ""
        # Windows lists every mic once per audio system, some with names cut to 31 characters. WASAPI's list has the
        # full names; leave out what isn't a microphone (Stereo Mix, speakers, virtual devices with no name).
        wasapi = None
        for h in range(pa.get_host_api_count()):
            if "WASAPI" in pa.get_host_api_info_by_index(h).get("name", ""):
                wasapi = h
        skip = ("stereo mix", "speaker", "what u hear", "loopback", "mapper", "primary", "()")
        names = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            n = (info.get("name") or "").strip()
            if info.get("maxInputChannels", 0) <= 0 or not n or any(s in n.lower() for s in skip):
                continue
            if wasapi is not None and info.get("hostApi") != wasapi:
                continue
            if n not in names:
                names.append(n)
        pa.terminate()
        default_full = next((n for n in names if default and n.startswith(default)), default)
        return {"default": default_full, "mics": names, "current": _voice_config().get("mic", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/voice/test", summary="What does Seven hear?")
def hearing_test():
    """Wait up to 8 seconds for one thing said; return what Seven heard, without acting on it."""
    try:
        import ears.core as ears
    except Exception:
        raise HTTPException(status_code=409, detail="Seven's hearing hasn't started yet.")
    if not ears.listening():
        raise HTTPException(status_code=409, detail="Seven isn't listening right now.")
    result = ears.hearing_test(8.0)
    if result is None:
        return {"heard": "", "ignored": "Nothing was said in 8 seconds.", "raw": ""}
    return result
