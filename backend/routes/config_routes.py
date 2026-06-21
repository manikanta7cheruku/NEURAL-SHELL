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
    success = config.update_config(req.updates)
    if success:
        return {"success": True, "config": config.KEY}
    else:
        raise HTTPException(status_code=500, detail="Failed to save config")


@router.get("/api/config/commands")
def get_commands_config():
    """Get all command configurations."""
    import config
    commands = config.KEY.get("commands", {})
    return {
        "app_aliases":  commands.get("app_aliases", {}),
        "app_paths":    commands.get("app_paths",   {}),
        "failed_apps":  commands.get("failed_apps", [])
    }


@router.put("/api/config/commands")
def update_commands_config(req: ConfigUpdate):
    """Update command configurations."""
    import config
    success = config.update_config({"commands": req.updates})
    if success:
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save commands config")


@router.get("/api/commands/failed-apps")
def get_failed_apps():
    """Get recent failed app launch attempts."""
    import config
    return config.KEY.get("commands", {}).get("failed_apps", [])


@router.post("/api/commands/app-aliases")
def add_app_alias(alias: AppAlias):
    """Add or update an app alias. Enforces plan limit."""
    import config
    from backend.api_server import check_limit, plan_limit_error, get_current_tier

    current_aliases = config.KEY.get("commands", {}).get("app_aliases", {})
    alias_key       = alias.name.lower().strip()
    is_new          = alias_key not in current_aliases

    limit_check = None
    if is_new:
        limit_check = check_limit("app_aliases", len(current_aliases))
        if not limit_check["allowed"]:
            raise plan_limit_error("app_aliases", limit_check)

    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    if "app_aliases" not in config.KEY["commands"]:
        config.KEY["commands"]["app_aliases"] = {}

    config.KEY["commands"]["app_aliases"][alias_key] = alias.target.lower().strip()
    config.save_config()

    return {
        "success": True,
        "alias":   alias.name,
        "target":  alias.target,
        "usage": {
            "current": len(config.KEY["commands"]["app_aliases"]),
            "limit":   limit_check["limit"] if limit_check else -1,
            "tier":    get_current_tier()
        } if is_new else {}
    }


@router.delete("/api/commands/app-aliases/{alias_name}")
def delete_app_alias(alias_name: str):
    """Delete an app alias."""
    import config
    aliases = config.KEY.get("commands", {}).get("app_aliases", {})
    if alias_name in aliases:
        del aliases[alias_name]
        config.save_config()
        return {"success": True, "deleted": alias_name}
    else:
        raise HTTPException(status_code=404, detail=f"Alias '{alias_name}' not found")


@router.post("/api/commands/app-paths")
def add_app_path(app_path_req: AppPath):
    """Add or update a custom app path. Enforces plan limit."""
    import config
    from backend.api_server import check_limit, plan_limit_error, get_current_tier

    current_paths = config.KEY.get("commands", {}).get("app_paths", {})
    path_key      = app_path_req.name.lower().strip()
    is_new        = path_key not in current_paths

    limit_check = None
    if is_new:
        limit_check = check_limit("custom_paths", len(current_paths))
        if not limit_check["allowed"]:
            raise plan_limit_error("custom_paths", limit_check)

    clean_path = app_path_req.path.strip().strip('"').strip("'")
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {clean_path}")

    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    if "app_paths" not in config.KEY["commands"]:
        config.KEY["commands"]["app_paths"] = {}

    config.KEY["commands"]["app_paths"][path_key] = clean_path
    config.save_config()

    return {
        "success": True,
        "name":    app_path_req.name,
        "path":    clean_path,
        "usage": {
            "current": len(config.KEY["commands"]["app_paths"]),
            "limit":   limit_check["limit"] if limit_check else -1,
            "tier":    get_current_tier()
        } if is_new else {}
    }


@router.delete("/api/commands/app-paths/{app_name}")
def delete_app_path(app_name: str):
    """Delete a custom app path."""
    import config
    paths = config.KEY.get("commands", {}).get("app_paths", {})
    if app_name in paths:
        del paths[app_name]
        config.save_config()
        return {"success": True, "deleted": app_name}
    else:
        raise HTTPException(status_code=404, detail=f"App path '{app_name}' not found")


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