from fastapi import APIRouter
import os
import sys
import platform
import logging

_log = logging.getLogger('seven.hardware')

router = APIRouter()


def _get_safe_hardware_onboarding():
    """
    Lightweight, fast hardware detection for Setup Mode.
    Does not import brain_manager or any ML/heavy libraries.
    """
    import psutil
    
    # Detect CPU Cores
    cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 4
    
    # Detect RAM
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    
    # Detect GPU safely on Windows via registry/WMI without loading PyTorch/CUDA DLLs
    gpu_name = "Intel Integrated Graphics"
    gpu_available = False
    
    try:
        if platform.system() == 'Windows':
            import winreg
            path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                    desc, _ = winreg.QueryValueEx(key, "DriverDesc")
                    gpu_name = str(desc)
                    # Check for dedicated Nvidia / AMD card
                    lower_name = gpu_name.lower()
                    if any(x in lower_name for x in ["nvidia", "geforce", "rtx", "gtx", "amd", "radeon", "arc"]):
                        gpu_available = True
            except Exception:
                pass
    except Exception:
        pass

    # Basic recommendation engine mapped to Meta Llama 3.2 specs
    if gpu_available and ram_gb >= 16:
        rec_model = "llama3.2:3b"
        tier = "high"
        reason = "Dedicated GPU and 16GB+ RAM detected. Excellent fit for premium models."
    elif gpu_available and ram_gb >= 8:
        rec_model = "llama3.2:3b"
        tier = "medium"
        reason = "GPU detected with moderate RAM. Recommending balanced 3B models."
    elif ram_gb >= 8:
        rec_model = "llama3.2:1b"
        tier = "low"
        reason = "Decent system RAM detected. Recommending fast 1B/3B models on CPU."
    else:
        rec_model = "llama3.2:1b"
        tier = "minimum"
        reason = "Limited system resources. Recommending Llama 3.2 1B for maximum speed."

    return {
        "gpu": {
            "available": gpu_available,
            "name": gpu_name
        },
        "ram_gb": ram_gb,
        "cpu": {
            "cores": cores,
            "name": platform.processor() or "Unknown CPU"
        },
        "os": f"{platform.system()} {platform.release()}",
        "recommended_model": rec_model,
        "recommended_tier": tier,
        "recommendation_reason": reason,
        "installed_models": []
    }


@router.get("/api/hardware")
def get_hardware():
    """Get hardware info. Thread-safe and isolated during onboarding."""
    try:
        import config
        is_setup_done = config.KEY.get("setup_complete", False)
    except Exception:
        is_setup_done = False

    if not is_setup_done:
        # Avoid importing brain_manager during onboarding setup
        _log.debug("[API] Serving safe hardware summary for onboarding")
        return _get_safe_hardware_onboarding()

    try:
        import brain_manager
        hw = brain_manager.get_hardware_summary()
        rec_model, tier, reason = brain_manager.recommend_model(hw)
        installed = brain_manager.get_installed_models()
        return {
            "gpu":                    hw.get("gpu", {"available": False, "name": "Unknown"}),
            "ram_gb":                 hw.get("ram_gb", 8),
            "cpu":                    hw.get("cpu", {"cores": 4, "name": "Unknown"}),
            "os":                     hw.get("os", "Windows"),
            "recommended_model":      rec_model,
            "recommended_tier":       tier,
            "recommendation_reason":  reason,
            "installed_models":       installed
        }
    except Exception as e:
        _log.warning(f"[API] Full hardware fetch failed: {e}. Falling back to safe mode.")
        return _get_safe_hardware_onboarding()


@router.get("/api/speed")
def get_speed():
    """Get latency statistics safely."""
    try:
        import config
        is_setup_done = config.KEY.get("setup_complete", False)
    except Exception:
        is_setup_done = False

    if not is_setup_done:
        return {
            "count": 0,
            "avg": 0,
            "min": 0,
            "max": 0,
            "model": "unknown",
            "streaming": False
        }

    try:
        import brain_manager
        import config
        stats = brain_manager.get_latency_stats()
        stats["model"] = config.KEY.get("brain", {}).get("model_name", "unknown")
        stats["streaming"] = config.KEY.get("brain", {}).get("streaming", False)
        return stats
    except Exception:
        return {
            "count": 0,
            "avg": 0,
            "min": 0,
            "max": 0,
            "model": "unknown",
            "streaming": False
        }


@router.get("/api/commands/log")
def get_command_log(limit: int = 50):
    """Get recent command execution log."""
    try:
        from memory.command_log import command_log
        return {
            "recent": command_log.get_recent(count=limit),
            "stats":  command_log.get_stats()
        }
    except Exception:
        return {"recent": [], "stats": {}}


@router.get("/api/mood")
def get_mood():
    """Get current mood status."""
    try:
        from memory.mood import mood_engine
        return mood_engine.get_status()
    except Exception:
        return {"score": 0.5, "label": "neutral"}


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