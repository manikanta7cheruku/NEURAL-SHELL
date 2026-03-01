"""
=============================================================================
PROJECT SEVEN - brain_manager.py (Smart Model Manager)
Version: 1.9

PURPOSE:
    - Detect hardware specs (GPU, VRAM, RAM)
    - Recommend best model for user's machine
    - Download model via Ollama if needed
    - Unload/swap models for VRAM management
    - Provide speed/latency stats

HARDWARE TIERS:
    >= 8GB VRAM  → llama3 8B (best quality)
    4-8GB VRAM   → phi3:mini 3.8B (good balance)
    2-4GB VRAM   → qwen2:1.5b (fast, basic)
    No GPU / <2GB → tinyllama 1.1B (CPU fallback)
=============================================================================
"""

import subprocess
import requests
import json
import os
import time
import platform
from colorama import Fore
import config

OLLAMA_API = "http://localhost:11434/api"


# =========================================================================
# HARDWARE DETECTION
# =========================================================================

def detect_gpu():
    """
    Detect GPU name and VRAM.
    Returns: dict with name, vram_mb, vram_gb, driver
    """
    result = {
        "name": "No GPU detected",
        "vram_mb": 0,
        "vram_gb": 0,
        "driver": "N/A",
        "available": False
    }
    
    try:
        # Try nvidia-smi first
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5
        ).strip()
        
        if output:
            parts = output.split(",")
            if len(parts) >= 3:
                result["name"] = parts[0].strip()
                result["vram_mb"] = int(parts[1].strip())
                result["vram_gb"] = round(result["vram_mb"] / 1024, 1)
                result["driver"] = parts[2].strip()
                result["available"] = True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fallback: try via Python
    if not result["available"]:
        try:
            import torch
            if torch.cuda.is_available():
                result["name"] = torch.cuda.get_device_name(0)
                result["vram_mb"] = int(torch.cuda.get_device_properties(0).total_mem / (1024 * 1024))
                result["vram_gb"] = round(result["vram_mb"] / 1024, 1)
                result["available"] = True
        except ImportError:
            pass
    
    return result


def detect_ram():
    """Detect total system RAM in GB."""
    try:
        import psutil
        ram_bytes = psutil.virtual_memory().total
        return round(ram_bytes / (1024 ** 3), 1)
    except ImportError:
        return 0


def detect_cpu():
    """Detect CPU info."""
    return {
        "processor": platform.processor() or "Unknown",
        "cores": os.cpu_count() or 0,
        "arch": platform.machine()
    }


def get_hardware_summary():
    """Get complete hardware summary."""
    gpu = detect_gpu()
    ram = detect_ram()
    cpu = detect_cpu()
    
    return {
        "gpu": gpu,
        "ram_gb": ram,
        "cpu": cpu,
        "os": platform.system(),
        "os_version": platform.version()
    }


# =========================================================================
# MODEL RECOMMENDATION
# =========================================================================

def recommend_model(hardware=None):
    """
    Recommend the best model based on hardware.
    Returns: (model_name, tier, reason)
    """
    if hardware is None:
        hardware = get_hardware_summary()
    
    vram = hardware["gpu"]["vram_gb"]
    has_gpu = hardware["gpu"]["available"]
    ram = hardware["ram_gb"]
    
    tiers = config.KEY.get("brain", {}).get("model_tiers", {
        "high": "llama3",
        "medium": "phi3:mini",
        "low": "qwen2:1.5b",
        "minimum": "tinyllama"
    })
    
    if has_gpu and vram >= 8:
        return tiers["high"], "high", f"GPU with {vram}GB VRAM — full power"
    elif has_gpu and vram >= 4:
        return tiers["medium"], "medium", f"GPU with {vram}GB VRAM — balanced"
    elif has_gpu and vram >= 2:
        return tiers["low"], "low", f"GPU with {vram}GB VRAM — lightweight"
    elif ram >= 16:
        return tiers["low"], "low", f"No GPU but {ram}GB RAM — CPU mode"
    elif ram >= 8:
        return tiers["minimum"], "minimum", f"Limited hardware — minimal model"
    else:
        return tiers["minimum"], "minimum", "Low-end system — minimal model"


# =========================================================================
# OLLAMA MODEL MANAGEMENT
# =========================================================================

def get_installed_models():
    """Get list of installed Ollama models."""
    try:
        r = requests.get(f"{OLLAMA_API}/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return [m["name"] for m in models]
    except:
        pass
    return []


def is_model_installed(model_name):
    """Check if a specific model is installed."""
    installed = get_installed_models()
    # Check both exact and partial match (llama3 matches llama3:latest)
    for m in installed:
        if model_name in m or m.startswith(model_name):
            return True
    return False


def download_model(model_name):
    """
    Download a model via Ollama.
    Returns: (success, message)
    """
    print(Fore.CYAN + f"[MODEL] Downloading {model_name}... This may take a few minutes.")
    
    try:
        # Use ollama pull command
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        for line in process.stdout:
            line = line.strip()
            if line:
                print(Fore.WHITE + f"  {line}")
        
        process.wait()
        
        if process.returncode == 0:
            print(Fore.GREEN + f"[MODEL] {model_name} downloaded successfully.")
            return True, f"{model_name} ready."
        else:
            return False, f"Download failed with code {process.returncode}"
    
    except FileNotFoundError:
        return False, "Ollama not found. Install Ollama first: https://ollama.com"
    except Exception as e:
        return False, f"Download error: {e}"


def ensure_model(model_name):
    """
    Ensure a model is installed. Download if needed.
    Returns: (success, actual_model_name)
    """
    if is_model_installed(model_name):
        return True, model_name
    
    print(Fore.YELLOW + f"[MODEL] {model_name} not found. Downloading...")
    success, msg = download_model(model_name)
    
    if success:
        return True, model_name
    
    # Fallback chain
    fallbacks = ["llama3", "phi3:mini", "tinyllama"]
    for fb in fallbacks:
        if fb != model_name and is_model_installed(fb):
            print(Fore.YELLOW + f"[MODEL] Using fallback: {fb}")
            return True, fb
    
    return False, model_name


def unload_model(model_name):
    """Force Ollama to unload a model from VRAM."""
    print(Fore.CYAN + f"[MODEL] Unloading {model_name}...")
    try:
        requests.post(f"{OLLAMA_API}/generate", json={
            "model": model_name,
            "keep_alive": 0
        }, timeout=5)
    except Exception as e:
        print(Fore.RED + f"[MODEL] Unload error: {e}")


def switch_to_vision():
    """Unloads Chat, Loads Vision."""
    unload_model(config.KEY['brain']['model_name'])


def switch_to_chat():
    """Unloads Vision, Loads Chat."""
    unload_model(config.KEY['vision']['model_name'])


# =========================================================================
# LATENCY TRACKING
# =========================================================================

_latency_history = []


def record_latency(duration_ms):
    """Record a response latency measurement."""
    _latency_history.append(duration_ms)
    if len(_latency_history) > 50:
        _latency_history.pop(0)


def get_latency_stats():
    """Get latency statistics."""
    if not _latency_history:
        return {"avg": 0, "min": 0, "max": 0, "count": 0, "last": 0}
    
    return {
        "avg": round(sum(_latency_history) / len(_latency_history)),
        "min": round(min(_latency_history)),
        "max": round(max(_latency_history)),
        "count": len(_latency_history),
        "last": round(_latency_history[-1])
    }


def get_speed_report():
    """Get full speed/hardware report."""
    hw = get_hardware_summary()
    model = config.KEY['brain']['model_name']
    streaming = config.KEY.get('brain', {}).get('streaming', False)
    rec_model, tier, reason = recommend_model(hw)
    latency = get_latency_stats()
    installed = get_installed_models()
    
    lines = []
    lines.append(f"GPU: {hw['gpu']['name']} ({hw['gpu']['vram_gb']}GB VRAM)")
    lines.append(f"RAM: {hw['ram_gb']}GB")
    lines.append(f"CPU: {hw['cpu']['processor']} ({hw['cpu']['cores']} cores)")
    lines.append(f"OS: {hw['os']} {hw['os_version']}")
    lines.append(f"")
    lines.append(f"Current Model: {model}")
    lines.append(f"Streaming: {'ON' if streaming else 'OFF'}")
    lines.append(f"Recommended: {rec_model} (tier: {tier})")
    lines.append(f"Reason: {reason}")
    lines.append(f"Installed Models: {', '.join(installed) if installed else 'none detected'}")
    lines.append(f"")
    if latency["count"] > 0:
        lines.append(f"Avg Latency: {latency['avg']}ms")
        lines.append(f"Min/Max: {latency['min']}ms / {latency['max']}ms")
        lines.append(f"Last: {latency['last']}ms")
        lines.append(f"Samples: {latency['count']}")
    else:
        lines.append(f"Latency: No measurements yet")
    
    return "\n".join(lines)