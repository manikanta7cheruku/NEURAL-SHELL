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

@router.post("/api/voice/enroll")
def enroll_via_api(req: EnrollRequest):
    """
    Signal main.py to begin enrollment.
    Does NOT capture audio here — that happens in main.py voice loop.
    Frontend must poll /api/voice/enrollment-status to get result.
    """
    from backend.api_server import set_state, get_state
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    # Clear any previous result and set pending
    set_state("pending_enrollment", name)
    set_state("enrollment_done", None)
    return {"queued": True, "name": name}


@router.get("/api/voice/enrollment-status")
def get_enrollment_status():
    """Poll this to check if enrollment completed."""
    from backend.api_server import get_state
    state = get_state()
    pending = state.get("pending_enrollment")
    done    = state.get("enrollment_done")
    return {
        "pending": pending,
        "done":    done,
        "status":  "done" if done else ("waiting" if pending else "idle")
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