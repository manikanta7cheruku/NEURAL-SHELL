"""
brain_modules/self_model.py

Seven's ground truth about itself and the machine it runs on.

BUGS FIXED:
    - The license tier was read from cfg["tier"] but the config stores it at
      license.tier, so every user showed as "free".
    - The active model came from a stale config key instead of the model the
      brain actually selected.
    - Creator is a constant now, never taken from editable config
      ("Team Seven" in an old config used to leak into answers).
    - Hardware detection shells out to nvidia-smi (up to 2 seconds). It is now
      primed in a background thread at startup so no user message pays for it.
"""

import logging
import os
import platform
import subprocess
import threading
import time
from typing import Any, Dict

from brain_modules.capabilities import CAPABILITIES

SEVEN_NAME = "Seven"
SEVEN_CREATOR = "Seven Labs"

_log = logging.getLogger("seven.self_model")
_lock = threading.Lock()
_hw_cache: Dict[str, Any] = {}
_hw_ts = 0.0
_HW_TTL = 300.0
_active_model = ""


def set_active_model(name: str) -> None:
    """Called by brain.py once the model has been selected."""
    global _active_model
    _active_model = name or ""


def _detect_gpu() -> tuple:
    """(name, vram_gb). Falls back to ('Integrated Graphics', 0.0)."""
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            timeout=2, creationflags=flags, stderr=subprocess.DEVNULL).decode("utf-8").strip()
        if out:
            parts = [p.strip() for p in out.splitlines()[0].split(",")]
            return parts[0], round(float(parts[1]) / 1024.0, 1)
    except Exception:
        pass
    return "Integrated Graphics", 0.0


def _detect_hardware() -> Dict[str, Any]:
    ram_gb = 8.0
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        pass
    gpu_name, vram_gb = _detect_gpu()
    return {"ram_gb": ram_gb, "cpu_name": platform.processor() or "Unknown CPU",
            "cpu_cores": os.cpu_count() or 4, "gpu_name": gpu_name, "vram_gb": vram_gb}


def get_hardware(force: bool = False) -> Dict[str, Any]:
    """Cached hardware facts. Call prime_async() at startup to pre-fill."""
    global _hw_cache, _hw_ts
    with _lock:
        if not force and _hw_cache and time.time() - _hw_ts < _HW_TTL:
            return dict(_hw_cache)
    hw = _detect_hardware()
    with _lock:
        _hw_cache, _hw_ts = hw, time.time()
    return dict(hw)


def prime_async() -> None:
    """Detect hardware in the background so the first question about it is instant."""
    threading.Thread(target=get_hardware, daemon=True, name="SelfModelPrime").start()


def _version() -> str:
    try:
        import config
        v = str(config.KEY.get("version", "")).strip()
        if v:
            return v
    except Exception:
        pass
    return "1.3.3"


def get_runtime_state() -> Dict[str, Any]:
    """Ground truth used by identity answers. Never raises."""
    tier, model = "free", _active_model
    try:
        import config
        tier = config.KEY.get("license", {}).get("tier", "free") or "free"
        if not model:
            model = config.KEY.get("brain", {}).get("model_name", "") or ""
    except Exception:
        pass
    return {
        "name": SEVEN_NAME,
        "creator": SEVEN_CREATOR,
        "version": _version(),
        "model_name": model or "a local model",
        "license_tier": tier,
        "os": f"{platform.system()} {platform.release()}",
        "hardware": get_hardware(),
        "capabilities": [c["title"] for c in CAPABILITIES],
    }


def describe_hardware() -> str:
    """One natural sentence about the host machine."""
    hw = get_hardware()
    gpu = (f"{hw['gpu_name']} with {hw['vram_gb']} GB of VRAM"
           if hw["vram_gb"] else hw["gpu_name"])
    return (f"{hw['ram_gb']} GB of RAM, {hw['cpu_name']} with {hw['cpu_cores']} cores, "
            f"and {gpu}.")
