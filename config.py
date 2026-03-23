"""
=============================================================================
PROJECT SEVEN - config.py (Configuration Manager)
Version: 2.0 (Dashboard-Ready)

CHANGES FROM V1.0:
    1. NEW: save_config() — writes changes back to config.json
    2. NEW: update_config() — partial update (merge, not replace)
    3. NEW: Thread-safe with lock
    4. KEPT: KEY dict works exactly the same everywhere
=============================================================================
"""

import json
import os
import threading

CONFIG_FILE = "config.json"
_lock = threading.Lock()


def load_config():
    """Load settings from config.json. Falls back to defaults if missing."""
    if not os.path.exists(CONFIG_FILE):
        print(f"[WARNING] {CONFIG_FILE} not found. Using default settings.")
        defaults = get_defaults()
        # Write defaults to disk so file exists for future saves
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(defaults, f, indent=4)
        except Exception:
            pass
        return defaults

    try:
        with open(CONFIG_FILE, 'r') as file:
            data = json.load(file)
            print(f"[SYSTEM] Configuration loaded successfully.")
            return data
    except Exception as e:
        print(f"[ERROR] Could not load config: {e}")
        return get_defaults()


def save_config():
    """
    Write current KEY dict back to config.json.
    Thread-safe — can be called from API thread or main thread.
    """
    with _lock:
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(KEY, f, indent=4)
            return True
        except Exception as e:
            print(f"[ERROR] Could not save config: {e}")
            return False


def update_config(updates):
    """
    Partial update — merge updates into KEY without losing other fields.
    
    Args:
        updates: dict with keys to update (can be nested)
        
    Example:
        update_config({"brain": {"streaming": True}})
        → only changes brain.streaming, keeps everything else
    """
    def _deep_merge(base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                _deep_merge(base[key], value)
            else:
                base[key] = value
    
    with _lock:
        _deep_merge(KEY, updates)
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(KEY, f, indent=4)
            return True
        except Exception as e:
            print(f"[ERROR] Could not save config: {e}")
            return False


def get_defaults():
    """Backup settings in case the JSON file is broken or missing."""
    return {
        "identity": {"name": "Seven", "creator": "Team Seven", "wake_words": ["seven"]},
        "brain": {
            "model_name": "llama3",
            "temperature": 0.3,
            "max_history": 10,
            "streaming": False,
            "auto_model": True,
            "model_tiers": {
                "high": "llama3",
                "medium": "phi3:mini",
                "low": "qwen2:1.5b",
                "minimum": "tinyllama"
            }
        },
        "gui": {"opacity": 0.8, "text_color": "#00FF00"},
        "commands": {
            "app_aliases": {},
            "app_paths": {}
        },
        "license": {
            "key": "",
            "tier": "free",
            "verified": False
        },
        "setup_complete": False,
        "version": "1.10"
    }


# Load the config immediately when this script is imported
KEY = load_config()