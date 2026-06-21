"""
backend/routes/hardware.py
Handles: /api/hardware, /api/speed, /api/commands/log, /api/mood, /api/speakers
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/hardware")
def get_hardware():
    """Get hardware info and model recommendation."""
    import brain_manager
    hw                          = brain_manager.get_hardware_summary()
    rec_model, tier, reason     = brain_manager.recommend_model(hw)
    installed                   = brain_manager.get_installed_models()
    return {
        "gpu":                    hw["gpu"],
        "ram_gb":                 hw["ram_gb"],
        "cpu":                    hw["cpu"],
        "os":                     hw["os"],
        "recommended_model":      rec_model,
        "recommended_tier":       tier,
        "recommendation_reason":  reason,
        "installed_models":       installed
    }


@router.get("/api/speed")
def get_speed():
    """Get latency statistics."""
    import brain_manager
    import config
    stats          = brain_manager.get_latency_stats()
    stats["model"] = config.KEY.get("brain", {}).get("model_name", "unknown")
    stats["streaming"] = config.KEY.get("brain", {}).get("streaming", False)
    return stats


@router.get("/api/commands/log")
def get_command_log(limit: int = 50):
    """Get recent command execution log."""
    from memory.command_log import command_log
    return {
        "recent": command_log.get_recent(count=limit),
        "stats":  command_log.get_stats()
    }


@router.get("/api/mood")
def get_mood():
    """Get current mood status."""
    from memory.mood import mood_engine
    return mood_engine.get_status()


@router.get("/api/speakers")
def get_speakers():
    """Get enrolled speakers."""
    try:
        from ears.voice_id import get_enrolled_speakers, is_voice_id_enabled
        if not is_voice_id_enabled():
            return {"enabled": False, "speakers": []}
        speakers = get_enrolled_speakers()
        return {"enabled": True, "speakers": [{"name": s, "enrolled": True} for s in speakers]}
    except Exception:
        return {"enabled": False, "speakers": []}