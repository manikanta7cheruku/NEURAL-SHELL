"""
backend/routes/voice_gates.py
Handles: /api/voice/gates, /api/voice/enrolled
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    Trigger enrollment from Settings UI.
    Sets a flag that main.py picks up on next listen() cycle.
    The actual voice capture happens in main.py voice loop.
    Returns instruction to user since recording happens through voice.
    """
    import config
    # Store pending enrollment name so main.py can pick it up
    config.update_config({"pending_enrollment": req.name.strip()})
    return {
        "success": True,
        "message": f"Say a few sentences now. Seven is listening for {req.name}.",
        "name": req.name
    }

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