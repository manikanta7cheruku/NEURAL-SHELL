"""
brain/model_selector.py
Seven — Automatic model selection based on hardware.

Logic:
  1. Check config for model_name
  2. If "auto" or empty → detect hardware → pick best model
  3. Cross-check against what's actually installed in Ollama
  4. Fall back gracefully if nothing good is available
  5. Save chosen model back to config so Settings shows it

Called once at brain.py startup. After that, MODEL_NAME is fixed for the session.
"""

import requests
import config
from colorama import Fore


# Model assignment matrix — ordered best to worst per VRAM tier
# Format: (min_vram_gb, [models_in_preference_order])
VRAM_MODEL_MATRIX = [
    (16,  ["llama3.3:70b", "qwen2.5:14b", "llama3.1:8b", "mistral:7b"]),
    (12,  ["llama3.1:8b",  "mistral:7b",  "llama3.2:3b"]),
    (8,   ["llama3.1:8b",  "mistral:7b",  "llama3.2:3b", "phi3:mini"]),
    (6,   ["mistral:7b",   "llama3.2:3b", "phi3:mini"]),
    (4,   ["llama3.2:3b",  "phi3:mini",   "llama3.2:1b"]),
    (2,   ["phi3:mini",    "llama3.2:1b", "tinyllama"]),
    (0,   ["phi3:mini",    "llama3.2:1b", "tinyllama"]),  # CPU only
]

# RAM-only fallback (no GPU)
RAM_MODEL_MATRIX = [
    (16, ["llama3.2:3b", "phi3:mini"]),
    (8,  ["phi3:mini",   "llama3.2:1b"]),
    (4,  ["llama3.2:1b", "tinyllama"]),
    (0,  ["tinyllama"]),
]


def _get_ollama_models() -> list[str]:
    """Returns list of model names currently installed in Ollama."""
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        if r.status_code == 200:
            return [m['name'] for m in r.json().get('models', [])]
    except Exception:
        pass
    return []


def _get_hardware() -> dict:
    """
    Detect GPU VRAM and system RAM.
    Returns dict with vram_gb (0 if no GPU) and ram_gb.
    """
    vram_gb = 0
    ram_gb  = 0

    # RAM
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    except Exception:
        ram_gb = 8  # safe default

    # Windows: CREATE_NO_WINDOW flag hides console window on subprocess spawn
    import sys as _sys_hw
    _hw_flags = 0x08000000 if _sys_hw.platform == "win32" else 0

    # GPU VRAM (NVIDIA)
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
            creationflags=_hw_flags
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines and lines[0].strip().isdigit():
                vram_mb = int(lines[0].strip())
                vram_gb = round(vram_mb / 1024)
    except Exception:
        pass

    # Try AMD if NVIDIA failed
    if vram_gb == 0:
        try:
            import subprocess
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--json"],
                capture_output=True, text=True, timeout=5,
                creationflags=_hw_flags
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                # rocm-smi output varies — best effort
                for card in data.values():
                    if isinstance(card, dict):
                        vram_bytes = card.get("VRAM Total Memory (B)", 0)
                        if vram_bytes:
                            vram_gb = round(int(vram_bytes) / (1024 ** 3))
                            break
        except Exception:
            pass

    return {"vram_gb": vram_gb, "ram_gb": ram_gb}


def _find_best_available(model_list: list[str], installed: list[str]) -> str | None:
    """
    Given a preference-ordered list of models,
    returns the first one that's actually installed in Ollama.
    Handles both "llama3.1:8b" and "llama3.1" matching.
    """
    installed_bases = {m.split(':')[0]: m for m in installed}
    for model in model_list:
        base = model.split(':')[0]
        # Exact match first
        if model in installed:
            return model
        # Base name match (e.g. "llama3.1" matches "llama3.1:8b")
        if base in installed_bases:
            return installed_bases[base]
    return None


def select_model() -> str:
    """
    Main entry point. Called once at brain startup.
    
    Returns the model name Seven should use this session.
    Saves it to config if auto-selected.
    """
    cfg_model = config.KEY.get('brain', {}).get('model_name', 'auto').strip()

    # If user manually set a model (not "auto" or empty), respect it
    if cfg_model and cfg_model.lower() not in ('auto', ''):
        installed = _get_ollama_models()
        if not installed:
            print(Fore.YELLOW + f"[MODEL] Using configured model: {cfg_model} (Ollama not reachable to verify)")
            return cfg_model

        # Check if configured model is actually installed
        bases = {m.split(':')[0]: m for m in installed}
        cfg_base = cfg_model.split(':')[0]
        if cfg_model in installed or cfg_base in bases:
            actual = bases.get(cfg_base, cfg_model)
            print(Fore.GREEN + f"[MODEL] Using configured model: {actual}")
            return actual
        else:
            print(Fore.YELLOW + f"[MODEL] Configured model '{cfg_model}' not found in Ollama.")
            print(Fore.YELLOW + f"[MODEL] Installed: {installed}")
            print(Fore.YELLOW + "[MODEL] Falling back to auto-selection.")
            # Fall through to auto-select

    # Auto-select based on hardware
    print(Fore.CYAN + "[MODEL] Auto-selecting model based on hardware...")
    hw       = _get_hardware()
    installed = _get_ollama_models()
    vram_gb  = hw['vram_gb']
    ram_gb   = hw['ram_gb']

    print(Fore.CYAN + f"[MODEL] Detected: VRAM={vram_gb}GB, RAM={ram_gb}GB")
    print(Fore.CYAN + f"[MODEL] Installed models: {installed}")

    if not installed:
        print(Fore.RED + "[MODEL] No models installed in Ollama. Defaulting to tinyllama.")
        return "tinyllama"

    chosen = None

    if vram_gb > 0:
        # GPU path
        for min_vram, models in VRAM_MODEL_MATRIX:
            if vram_gb >= min_vram:
                chosen = _find_best_available(models, installed)
                if chosen:
                    break
    
    if not chosen:
        # CPU/RAM path
        for min_ram, models in RAM_MODEL_MATRIX:
            if ram_gb >= min_ram:
                chosen = _find_best_available(models, installed)
                if chosen:
                    break

    if not chosen:
        # Last resort — just use whatever is installed
        chosen = installed[0]
        print(Fore.YELLOW + f"[MODEL] No matrix match — using first available: {chosen}")

    # Save back to config so Settings UI shows it
    try:
        current_brain = config.KEY.get('brain', {})
        current_brain['model_name'] = chosen
        config.update_config({'brain': current_brain})
    except Exception as e:
        print(Fore.YELLOW + f"[MODEL] Could not save model to config: {e}")

    print(Fore.GREEN + f"[MODEL] Auto-selected: {chosen} (VRAM={vram_gb}GB, RAM={ram_gb}GB)")
    return chosen


def get_recommended_model() -> str:
    """
    Returns what Seven would recommend for current hardware.
    Used by Settings UI hardware panel.
    Does NOT change the active model.
    """
    hw       = _get_hardware()
    installed = _get_ollama_models()
    vram_gb  = hw['vram_gb']
    ram_gb   = hw['ram_gb']

    if vram_gb > 0:
        for min_vram, models in VRAM_MODEL_MATRIX:
            if vram_gb >= min_vram:
                result = _find_best_available(models, installed)    
                if result:
                    return result
                # Return preferred even if not installed
                return models[0]

    for min_ram, models in RAM_MODEL_MATRIX:
        if ram_gb >= min_ram:
            result = _find_best_available(models, installed)
            if result:
                return result
            return models[0]

    return "tinyllama"