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
    
# ============================================================================
# BRAIN CONFIG — dedicated endpoints for fast reads/writes
# ============================================================================

class BrainConfigUpdate(BaseModel):
    updates: Dict[str, Any]


@router.get("/api/config/brain")
def get_brain_config():
    """Every brain setting with its effective value (defaults filled in, bad values clamped)."""
    import config
    from brain_modules import brain_settings
    out = {path.split(".", 1)[1]: info["effective"]
           for path, info in brain_settings.effective(config).items() if path.startswith("brain.")}
    out["auto_model"] = config.KEY.get("brain", {}).get("auto_model", True)
    return out


@router.patch("/api/config/brain")
def update_brain_config(req: BrainConfigUpdate):
    """
    Update brain settings. Allowed keys and bounds come from brain_settings, the
    same registry the brain and chat commands ("set honesty to 75%") use.
    """
    import config
    from brain_modules import brain_settings

    clean, errors = {}, {}
    for key, value in req.updates.items():
        if key == "auto_model":
            clean[key] = bool(value)
            continue
        path = f"brain.{key}"
        if path not in brain_settings.SETTINGS:
            continue
        ok, stored, note = brain_settings.validate_update(path, value)
        if not ok:
            errors[key] = note
        else:
            clean[key] = stored

    if errors:
        raise HTTPException(status_code=400, detail="; ".join(f"{k}: {v}" for k, v in errors.items()))
    if not clean:
        raise HTTPException(status_code=400, detail="No valid brain fields provided")

    if not config.update_config({"brain": clean}):
        raise HTTPException(status_code=500, detail="Failed to save brain config")

    if "follow_up_timeout" in clean:
        try:
            import brain_modules.dialogue_manager as _dm
            _dm._MEMORY_TIMEOUT_SEC = int(clean["follow_up_timeout"])
        except Exception as _e:
            print(f"[CONFIG] Dialogue timeout live update skipped: {_e}")
    return {"success": True, "brain": get_brain_config()}


@router.get("/api/config/brain/available-models")
def get_available_models():
    """
    Return installed Ollama models grouped by parameter size tier.
    Used by Settings UI to show a proper model picker.
    """
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if r.status_code != 200:
            return {"tiers": {}, "all": [], "ollama_running": False}

        raw_models = r.json().get("models", [])
        tiers = {"small": [], "medium": [], "large": []}
        all_names = []

        for m in raw_models:
            name = m.get("name", "")
            if not name:
                continue
            all_names.append(name)

            # Detect size from name (heuristic)
            lower = name.lower()
            size_gb = m.get("size", 0) / (1024 ** 3)

            if any(x in lower for x in ["1b", "1.5b", "tinyllama", "phi3:mini"]):
                tier = "small"
            elif any(x in lower for x in ["3b", "3.8b"]):
                tier = "small"
            elif any(x in lower for x in ["7b", "8b", "mistral"]):
                tier = "medium"
            elif any(x in lower for x in ["13b", "14b", "34b", "70b"]):
                tier = "large"
            elif size_gb < 3:
                tier = "small"
            elif size_gb < 7:
                tier = "medium"
            else:
                tier = "large"

            tiers[tier].append({
                "name": name,
                "size_gb": round(size_gb, 1),
            })

        # Get recommended
        try:
            from brain_modules.model_selector import get_recommended_model
            recommended = get_recommended_model()
        except Exception:
            recommended = None

        return {
            "tiers": tiers,
            "all": all_names,
            "recommended": recommended,
            "ollama_running": True,
        }
    except Exception as e:
        return {"tiers": {}, "all": [], "ollama_running": False, "error": str(e)}