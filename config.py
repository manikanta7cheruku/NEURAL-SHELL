"""
=============================================================================
PROJECT SEVEN - config.py (Configuration Manager)
Version: 3.0 (Packaged App + %APPDATA% Migration)

CHANGES FROM V2.0:
    1. NEW: get_app_data_dir() — resolves %APPDATA%\SEVEN in packaged mode
    2. NEW: Automatic migration from old ./data/ path to %APPDATA%\SEVEN
    3. NEW: CONFIG_FILE now lives in %APPDATA%\SEVEN\config.json
    4. KEPT: All V2.0 API (KEY, save_config, update_config) unchanged
    5. KEPT: Thread-safe lock

WHY THIS CHANGE:
    In a packaged Electron app, the install directory (C:\Program Files\SEVEN)
    is read-only for standard users. Config, databases, and memory must live
    in a writable location: %APPDATA%\SEVEN\
=============================================================================
"""

import json
import os
import shutil
import threading

_lock = threading.Lock()


# ============================================================================
# PATH RESOLUTION
# ============================================================================

def get_app_data_dir():
    """
    Returns the writable app data directory.
    
    Packaged:   C:\\Users\\<name>\\AppData\\Roaming\\SEVEN
    Dev mode:   Same (consistent behavior across environments)
    
    Directory is created if it does not exist.
    """
    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
    app_dir = os.path.join(app_data, 'SEVEN')
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_data_dir():
    """
    Returns the data subdirectory inside app data dir.
    Houses: device_id.txt, email.txt, license.db, telemetry.db
    
    Path: %APPDATA%\\SEVEN\\data\\
    """
    data_dir = os.path.join(get_app_data_dir(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_memory_dir():
    """
    Returns ChromaDB memory directory.
    
    Path: %APPDATA%\\SEVEN\\seven_data\\memory\\
    """
    mem_dir = os.path.join(get_app_data_dir(), 'seven_data', 'memory')
    os.makedirs(mem_dir, exist_ok=True)
    return mem_dir


def get_knowledge_dir():
    """
    Returns knowledge base directory.
    
    Path: %APPDATA%\\SEVEN\\seven_data\\knowledge\\
    """
    know_dir = os.path.join(get_app_data_dir(), 'seven_data', 'knowledge')
    os.makedirs(know_dir, exist_ok=True)
    return know_dir


# ── Config file lives in app data dir ──
CONFIG_FILE = os.path.join(get_app_data_dir(), 'config.json')


# ============================================================================
# MIGRATION — Move old ./data/ to %APPDATA%\SEVEN\data\
# ============================================================================

def _migrate_old_data():
    """
    One-time migration from legacy path to %APPDATA%\SEVEN\.
    
    Runs silently on first launch after upgrade.
    Only migrates if old path exists AND new path is empty.
    Safe to call multiple times — skips if already migrated.
    """
    # Find old data directory (relative to this script's location)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    old_data = os.path.join(script_dir, 'data')
    old_config = os.path.join(script_dir, 'config.json')
    new_data = get_data_dir()
    new_config = CONFIG_FILE

    migrated_something = False

    # Migrate config.json
    if os.path.exists(old_config) and not os.path.exists(new_config):
        try:
            shutil.copy2(old_config, new_config)
            print(f"[CONFIG] Migrated config.json → {new_config}")
            migrated_something = True
        except Exception as e:
            print(f"[CONFIG] Migration warning (config): {e}")

    # Migrate data/ folder contents
    # Skip device_id.txt — never migrate this, always create fresh
    if os.path.exists(old_data):
        for filename in ['email.txt', 'license.db', 'telemetry.db']:
            old_file = os.path.join(old_data, filename)
            new_file = os.path.join(new_data, filename)
            if os.path.exists(old_file) and not os.path.exists(new_file):
                try:
                    shutil.copy2(old_file, new_file)
                    print(f"[CONFIG] Migrated {filename} → {new_data}")
                    migrated_something = True
                except Exception as e:
                    print(f"[CONFIG] Migration warning ({filename}): {e}")

    # Migrate ChromaDB memory
    old_memory = os.path.join(script_dir, 'seven_data', 'memory')
    new_memory = get_memory_dir()
    if os.path.exists(old_memory) and not os.listdir(new_memory):
        try:
            shutil.copytree(old_memory, new_memory, dirs_exist_ok=True)
            print(f"[CONFIG] Migrated memory → {new_memory}")
            migrated_something = True
        except Exception as e:
            print(f"[CONFIG] Migration warning (memory): {e}")

    if migrated_something:
        print("[CONFIG] Data migration complete.")


# ============================================================================
# CONFIG LOAD / SAVE
# ============================================================================

def load_config():
    """
    Load settings from config.json in %APPDATA%\SEVEN\.
    Falls back to defaults if file is missing or corrupt.
    """
    # Run migration first (silent, safe to call every startup)
    _migrate_old_data()

    if not os.path.exists(CONFIG_FILE):
        print(f"[CONFIG] No config found. Writing defaults to {CONFIG_FILE}")
        defaults = get_defaults()
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(defaults, f, indent=4)
        except Exception as e:
            print(f"[CONFIG] Could not write defaults: {e}")
        return defaults

    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        print(f"[CONFIG] Loaded from {CONFIG_FILE}")
        return data
    except Exception as e:
        print(f"[CONFIG] Corrupt config, using defaults: {e}")
        return get_defaults()


def save_config():
    """
    Write current KEY dict back to %APPDATA%\SEVEN\config.json.
    Thread-safe.
    """
    with _lock:
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(KEY, f, indent=4)
            return True
        except Exception as e:
            print(f"[CONFIG] Could not save: {e}")
            return False


def update_config(updates):
    """
    Deep-merge updates into KEY and persist to disk.
    Does not overwrite keys not mentioned in updates.
    
    Example:
        update_config({"brain": {"streaming": True}})
        → changes only brain.streaming
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
            print(f"[CONFIG] Could not save update: {e}")
            return False


# ============================================================================
# DEFAULTS
# ============================================================================

def get_defaults():
    """
    Default configuration. Used when config.json is missing.
    All values here are safe starting points.
    """
    return {
        "identity": {
            "name": "Seven",
            "creator": "Seven Labs",
            "user_name": "",
            "wake_words": ["seven", "hey seven"],
            "pause_words": ["not you", "hold on", "wait", "stop listening"],
            "resume_words": ["wake up", "seven", "continue", "start listening"],
            "shutdown_words": ["go to sleep", "goodbye", "shutdown", "close seven"]
        },
        "email": "",
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
        "gui": {
            "opacity": 0.8,
            "text_color": "#00FF00"
        },
        "commands": {
            "app_aliases": {},
            "app_paths": {}
        },
        "license": {
            "key": "",
            "tier": "free",
            "verified": False,
            "expires_at": None
        },
        "setup_complete": False,
        "version": "1.1.4"
    }


# ── Load immediately on import ──
KEY = load_config()


def sync_version():
    """
    Read version from package.json and update config.json.
    Searches multiple locations — works in dev and packaged app.
    """
    try:
        import json as _json
        base = os.path.dirname(os.path.abspath(__file__))
        app_path = os.environ.get("SEVEN_APP_PATH", "")

        candidates = [
            # Dev mode — project root
            os.path.join(base, "package.json"),
            os.path.join(os.path.dirname(base), "package.json"),
            # Packaged app — SEVEN_APP_PATH points to resources/app/
            os.path.join(app_path, "package.json") if app_path else None,
            os.path.join(app_path, "..", "package.json") if app_path else None,
            # Packaged app — relative to Python executable
            os.path.join(os.path.dirname(os.path.abspath(
                __import__("sys").executable)), "package.json"),
            os.path.join(os.path.dirname(os.path.abspath(
                __import__("sys").executable)), "..", "app", "package.json"),
        ]

        # Remove None entries
        candidates = [os.path.normpath(c) for c in candidates if c]

        for pkg_path in candidates:
            if os.path.exists(pkg_path):
                with open(pkg_path, "r", encoding="utf-8") as f:
                    content = f.read().lstrip("\ufeff")  # Remove BOM
                    pkg_version = _json.loads(content).get("version", "")
                if pkg_version:
                    if pkg_version != KEY.get("version", ""):
                        KEY["version"] = pkg_version
                        save_config()
                        print("[CONFIG] Version synced to " + pkg_version)
                    else:
                        print("[CONFIG] Version already current: " + pkg_version)
                    return

        print("[CONFIG] package.json not found in any location")

    except Exception as e:
        print("[CONFIG] Version sync error: " + str(e))


sync_version()