"""
Seven Self-Model & Runtime Ground Truth
Inspects the real host machine and runtime environment.
Cached for 60 seconds to prevent disk/WMI overhead.
"""

import os
import sys
import platform
import subprocess
import time
from typing import Dict, Any

_CACHE: Dict[str, Any] = {}
_CACHE_TIMESTAMP = 0.0
_CACHE_TTL_SECONDS = 60.0


def _detect_gpu() -> tuple:
    """Detects GPU name and total VRAM in GB."""
    # Method 1: nvidia-smi command (most reliable on Windows for NVIDIA)
    try:
        smi_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            timeout=2,
            creationflags=0x08000000 if os.name == "nt" else 0
        ).decode("utf-8").strip()
        if smi_out:
            line = smi_out.splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            name = parts[0]
            vram_gb = round(float(parts[1]) / 1024.0, 1)
            return name, vram_gb
    except Exception:
        pass

    # Method 2: torch.cuda
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            vram_gb = round(vram_bytes / (1024 ** 3), 1)
            return name, vram_gb
    except Exception:
        pass

    # Method 3: Windows WMI fallback
    if platform.system() == "Windows":
        try:
            import wmi
            w = wmi.WMI()
            for controller in w.Win32_VideoController():
                name = controller.Name
                if name and "virtual" not in name.lower() and "basic" not in name.lower():
                    return name, 0.0
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

    cpu_name = platform.processor() or "Unknown CPU"
    cpu_cores = os.cpu_count() or 4
    gpu_name, vram_gb = _detect_gpu()

    return {
        "ram_gb": ram_gb,
        "cpu_name": cpu_name,
        "cpu_cores": cpu_cores,
        "gpu_name": gpu_name,
        "vram_gb": vram_gb,
    }


def get_runtime_state(force_refresh: bool = False) -> Dict[str, Any]:
    """Returns ground-truth hardware, version, model, and capabilities."""
    global _CACHE, _CACHE_TIMESTAMP

    now = time.time()
    if not force_refresh and _CACHE and (now - _CACHE_TIMESTAMP < _CACHE_TTL_SECONDS):
        return _CACHE

    # Load version and tier from config if available
    version = "1.3.3"
    license_tier = "free"
    model_name = "llama3.2:1b"
    app_path = os.environ.get("SEVEN_APP_PATH", os.getcwd())
    user_data_path = os.path.join(os.environ.get("APPDATA", ""), "SEVEN")

    try:
        config_path = os.path.join(user_data_path, "config.json")
        if os.path.exists(config_path):
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                version = cfg.get("version", version)
                license_tier = cfg.get("tier", license_tier)
                model_name = cfg.get("model", model_name)
    except Exception:
        pass

    state = {
        "name": "Seven",
        "version": version,
        "creator": "Seven Labs",
        "model_name": model_name,
        "license_tier": license_tier,
        "os": f"{platform.system()} {platform.release()}",
        "hardware": _detect_hardware(),
        "app_path": app_path,
        "user_data_path": user_data_path,
        "capabilities": [
            "voice and text interaction",
            "local system automation",
            "semantic long-term memory",
            "window management",
            "application control",
            "task scheduling",
            "local document intelligence",
            "real-time web search",
        ],
        "limitations": [
            "no direct financial transactions",
            "local execution bounded by host hardware",
            "free tier limits conversations and stored facts",
        ],
    }

    _CACHE = state
    _CACHE_TIMESTAMP = now
    return state


def describe_self() -> str:
    """Returns formatted block for system prompt injection."""
    st = get_runtime_state()
    hw = st["hardware"]
    gpu_desc = f"{hw['gpu_name']} ({hw['vram_gb']}GB VRAM)" if hw["gpu_name"] != "Integrated Graphics" else "Integrated Graphics"

    return (
        f"[SYSTEM IDENTITY & GROUND TRUTH]\n"
        f"Name: {st['name']}\n"
        f"Version: {st['version']}\n"
        f"Creator: {st['creator']}\n"
        f"Active Model: {st['model_name']}\n"
        f"Operating System: {st['os']}\n"
        f"Host Hardware: {hw['ram_gb']}GB RAM, CPU: {hw['cpu_name']} ({hw['cpu_cores']} cores), GPU: {gpu_desc}\n"
        f"Capabilities: {', '.join(st['capabilities'])}\n"
        f"Rule: Always use the exact specs above when asked about your system, hardware, version, or identity."
    )