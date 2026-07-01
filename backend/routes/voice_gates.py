"""
backend/routes/voice_gates.py
Handles: /api/voice/gates, /api/voice/enrolled
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import threading
import os

router = APIRouter()

_DEFAULT_GATES = {
    "push_to_talk":   {"enabled": False, "key": "shift"},
    "wake_word":      {"enabled": False, "words": ["hey seven", "ok seven", "seven"]},
    "speaker_verify": {"enabled": False}
}


@router.get("/api/voice/gates")
def get_voice_gates():
    """Get current voice gate configuration."""
    import config
    gates = config.KEY.get("voice_gates", _DEFAULT_GATES.copy())
    # Ensure all keys exist
    for k, v in _DEFAULT_GATES.items():
        if k not in gates:
            gates[k] = v.copy()
    return gates


@router.post("/api/voice/gates")
def save_voice_gates(body: dict):
    """Save voice gate configuration."""
    import config
    config.update_config({"voice_gates": body})
    return {"ok": True}


@router.get("/api/voice/enrolled")
def get_enrolled_speakers():
    """Get list of enrolled voice profiles."""
    try:
        from ears.voice_id import get_enrolled_speakers, is_voice_id_enabled
        return {
            "enrolled": get_enrolled_speakers(),
            "enabled":  is_voice_id_enabled()
        }
    except Exception as e:
        return {"enrolled": [], "enabled": False, "error": str(e)}    
    
class EnrollRequest(BaseModel):
    name: str

_welcome_spoken = False

@router.post("/api/voice/enrollment-welcome")
def enrollment_welcome():
    global _welcome_spoken
    # Guard against double calls from React StrictMode
    if _welcome_spoken:
        _welcome_spoken = False  # Reset for next enrollment session
        return {"ok": True, "skipped": True}
    _welcome_spoken = True

    def _speak():
        try:
            import mouth as _mouth
            # Short single sentence — user is looking at the form, not listening to a lecture
            _mouth.speak("Enter your name, then click Start Enrollment.")
        except Exception as e:
            print(f"[ENROLL-WELCOME] {e}")

    threading.Thread(target=_speak, daemon=True).start()
    return {"ok": True}

@router.post("/api/voice/enroll")
def enroll_via_api(req: EnrollRequest):
    """
    Signal main.py to begin enrollment.
    Also sets force_return so listen() unblocks within 1.5 seconds.
    """
    from backend.api_server import set_state
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    set_state("pending_enrollment", name)
    set_state("enrollment_done", None)
    set_state("enrollment_clips_done", 0)

    # Unblock the current listen() call so the enrollment loop runs immediately
    try:
        from ears.core import set_force_return
        set_force_return(True)
    except Exception as e:
        print(f"[ENROLL] Could not set force_return: {e}")

    return {"queued": True, "name": name}


@router.get("/api/voice/enrollment-status")
def get_enrollment_status():
    """Poll this to check if enrollment completed."""
    from backend.api_server import get_state
    state = get_state()
    pending    = state.get("pending_enrollment")
    done       = state.get("enrollment_done")
    clips_done = state.get("enrollment_clips_done", 0)
    return {
        "pending":    pending,
        "done":       done,
        "clips_done": clips_done,
        "status":     "done" if done else ("recording" if clips_done > 0 else ("waiting" if pending else "idle"))
    }


@router.post("/api/voice/play-sample")
def play_voice_sample(body: dict):
    """
    Play back a recorded voice sample for the user to verify.
    Looks for saved sample in voice_prints directory.
    """
    name = body.get("name", "").lower().strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")

    sample_path = os.path.join(".", "seven_data", "voice_prints", f"{name}_sample.wav")
    if not os.path.exists(sample_path):
        raise HTTPException(status_code=404, detail="No sample saved for this voice")

    try:
        import winsound
        threading.Thread(
            target=lambda: winsound.PlaySound(sample_path, winsound.SND_FILENAME),
            daemon=True
        ).start()
        return {"playing": True, "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/voice/enrolled/{name}")
def delete_enrolled_speaker(name: str):
    """Remove an enrolled voice profile."""
    try:
        from ears.voice_id import remove_speaker
        success = remove_speaker(name)
        if success:
            return {"ok": True, "removed": name}
        raise HTTPException(status_code=404, detail=f"Speaker '{name}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))