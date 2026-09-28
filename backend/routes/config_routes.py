"""
backend/routes/config_routes.py
Handles: /api/config/*, /api/commands/*, /api/voice-control/words
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os

router = APIRouter()


class ConfigUpdate(BaseModel):
    updates: Dict[str, Any]


class AppAlias(BaseModel):
    name:   str
    target: str


class AppPath(BaseModel):
    name: str
    path: str


@router.get("/api/config")
def get_config():
    """Get full configuration."""
    import config
    return config.KEY


@router.put("/api/config")
def update_config(req: ConfigUpdate):
    """Partial update of configuration."""
    import config
    protected = {"voice_gates"}
    updates = {k: v for k, v in req.updates.items() if k not in protected}
    success = config.update_config(updates)
    if success:
        # If identity.user_name changed, update brain's live USER_NAME
        # so Seven uses the new name immediately without restart.
        if "identity" in updates and "user_name" in updates["identity"]:
            new_name = updates["identity"]["user_name"].strip()
            if new_name:
                try:
                    import brain
                    brain.USER_NAME = new_name
                    print(f"[CONFIG] Brain USER_NAME updated live: {new_name}")
                except Exception as _brain_err:
                    print(f"[CONFIG] Brain name update skipped: {_brain_err}")
        return {"success": True, "config": config.KEY}
    else:
        raise HTTPException(status_code=500, detail="Failed to save config")


@router.get("/api/voice-control/words")
def get_voice_control_words():
    """Get current wake/pause/shutdown words."""
    import config
    identity = config.KEY.get("identity", {})
    tier     = config.KEY.get("license", {}).get("tier", "free")
    return {
        "wake_words":     identity.get("wake_words",     ["seven"]),
        "pause_words":    identity.get("pause_words",    ["hold on"]),
        "resume_words":   identity.get("resume_words",   ["wake up"]),
        "shutdown_words": identity.get("shutdown_words", ["go to sleep"]),
        "tier":           tier,
        "can_edit":       tier in ["pro", "ultimate"]
    }


@router.put("/api/voice-control/words")
def update_voice_control_words(data: dict):
    """Update wake/pause/shutdown words (Pro only)."""
    import config
    tier = config.KEY.get("license", {}).get("tier", "free")

    if tier not in ["pro", "ultimate"]:
        raise HTTPException(status_code=403, detail="Pro plan required to customize voice commands")

    if "wake_words" in data:
        if "identity" not in config.KEY:
            config.KEY["identity"] = {}
        config.KEY["identity"]["wake_words"] = [w.lower().strip() for w in data["wake_words"] if w.strip()]
    if "pause_words" in data:
        config.KEY["identity"]["pause_words"] = [w.lower().strip() for w in data["pause_words"] if w.strip()]
    if "resume_words" in data:
        config.KEY["identity"]["resume_words"] = [w.lower().strip() for w in data["resume_words"] if w.strip()]
    if "shutdown_words" in data:
        config.KEY["identity"]["shutdown_words"] = [w.lower().strip() for w in data["shutdown_words"] if w.strip()]

    config.save_config()
    return {"success": True, "message": "Voice commands updated"}

class PanelHotkeyUpdate(BaseModel):
    hotkey: str


@router.post("/panel/set-hotkey")
def set_panel_hotkey(body: PanelHotkeyUpdate):
    """Save user's chosen panel hotkey to config and signal panel_host to reload."""
    try:
        import config as _cfg

        hk = (body.hotkey or "").strip()
        if not hk:
            raise HTTPException(status_code=400, detail="Hotkey cannot be empty")

        panel_cfg = _cfg.KEY.get("panel", {})
        panel_cfg["hotkey"] = hk
        _cfg.KEY["panel"] = panel_cfg
        _cfg.save_config()

        try:
            import requests
            requests.post("http://127.0.0.1:7779/panel/reload-hotkey", timeout=1)
        except Exception:
            pass

        return {"success": True, "hotkey": hk}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/panel/get-hotkey")
def get_panel_hotkey():
    """Return the currently configured panel hotkey."""
    try:
        import config as _cfg
        hk = _cfg.KEY.get("panel", {}).get("hotkey", "Alt+Shift+T")
        return {"hotkey": hk}
    except Exception:
        return {"hotkey": "Alt+Shift+T"}