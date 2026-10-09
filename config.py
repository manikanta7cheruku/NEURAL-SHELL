"""
=============================================================================
PROJECT SEVEN - config.py (Configuration Manager)
Version: 3.1

WHY THIS CHANGED (personal data leak):
    The previous _migrate_old_data() copied the repository's config.json into
    each user's %APPDATA%\\SEVEN folder on first launch. That file contained the
    developer's own email, GitHub shortcut and name, so every installed copy
    inherited them. This version:
      - NEVER migrates config.json (defaults come from get_defaults()).
      - Never migrates anything in a git checkout (SEVEN_DISABLE_MIGRATION=1
        also turns it off).
      - Fills missing keys from defaults, so older configs gain new settings.
      - Forces identity.creator to "Seven Labs".

API unchanged: KEY, load_config, save_config, update_config, get_defaults,
get_app_data_dir, get_data_dir, get_memory_dir, get_knowledge_dir, sync_version.
=============================================================================
"""

import copy
import json
import logging
import os
import shutil
import threading

_log = logging.getLogger("seven.config")
_lock = threading.Lock()


# ============================================================================
# PATHS
# ============================================================================

def get_app_data_dir():
    """Writable per-user directory: %APPDATA%\\SEVEN (created if missing)."""
    app_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_data_dir():
    """%APPDATA%\\SEVEN\\data: device id, email, license and telemetry databases."""
    d = os.path.join(get_app_data_dir(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def get_memory_dir():
    """%APPDATA%\\SEVEN\\seven_data\\memory: ChromaDB and the facts store."""
    d = os.path.join(get_app_data_dir(), "seven_data", "memory")
    os.makedirs(d, exist_ok=True)
    return d


def get_knowledge_dir():
    """%APPDATA%\\SEVEN\\seven_data\\knowledge: indexed documents."""
    d = os.path.join(get_app_data_dir(), "seven_data", "knowledge")
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_FILE = os.path.join(get_app_data_dir(), "config.json")


# ============================================================================
# MIGRATION (data files only, never config.json)
# ============================================================================

def _migration_allowed(script_dir):
    if os.environ.get("SEVEN_DISABLE_MIGRATION") == "1":
        return False
    return not os.path.isdir(os.path.join(script_dir, ".git"))


def _migrate_old_data():
    """One-time copy of legacy data files into %APPDATA%. Skipped in dev checkouts."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not _migration_allowed(script_dir):
        return

    old_data, new_data = os.path.join(script_dir, "data"), get_data_dir()
    if os.path.exists(old_data):
        for name in ("license.db", "telemetry.db"):
            src, dst = os.path.join(old_data, name), os.path.join(new_data, name)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except Exception as exc:
                    _log.warning("migration warning (%s): %s", name, exc)

    old_memory, new_memory = os.path.join(script_dir, "seven_data", "memory"), get_memory_dir()
    if os.path.exists(old_memory) and not os.listdir(new_memory):
        try:
            shutil.copytree(old_memory, new_memory, dirs_exist_ok=True)
        except Exception as exc:
            _log.warning("migration warning (memory): %s", exc)


# ============================================================================
# DEFAULTS
# ============================================================================

def get_defaults():
    """Clean defaults. Contains no personal data."""
    return {
        "identity": {
            "name": "Seven",
            "creator": "Seven Labs",
            "user_name": "",
            "wake_words": ["seven", "hey seven"],
            "pause_words": ["not you", "hold on", "wait", "stop listening"],
            "resume_words": ["wake up", "seven", "continue", "start listening"],
            "shutdown_words": ["go to sleep", "goodbye", "shutdown", "close seven"],
        },
        "email": "",
        "brain": {
            "model_name": "auto",
            "temperature": 0.3,
            "max_history": 10,
            "streaming": True,
            "auto_model": True,
            "model_tiers": {"high": "llama3", "medium": "phi3:mini",
                            "low": "qwen2:1.5b", "minimum": "tinyllama"},
            "tars_humor": 75,
            "tars_honesty": 85,
            "history_ttl_seconds": 1800,
            "search_max_results": 8,
            "auto_open_best_match": True,
            "follow_up_timeout": 90,
            "prefer_browser_for_unknown": True,
            "content_search_enabled": True,
        },
        "memory": {"min_relevance": 0.70, "retrieval_timeout_ms": 450},
        "web": {"enabled": True, "max_results": 2, "news_max_results": 2, "timeout": 5},
        "gui": {"opacity": 0.8, "text_color": "#00FF00"},
        "commands": {},
        "file_search_roots": [],
        "license": {"key": "", "tier": "free", "verified": False, "expires_at": None},
        "setup_complete": False,
        "version": "1.3.3",
    }


def _fill_defaults(data, defaults):
    """Recursively add keys missing from data. Existing values always win."""
    for key, value in defaults.items():
        if key not in data:
            data[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(data[key], dict):
            _fill_defaults(data[key], value)
    return data


def _normalize(data):
    """Enforce invariants on a loaded config."""
    identity = data.setdefault("identity", {})
    identity["name"] = "Seven"
    identity["creator"] = "Seven Labs"
    return data


# ============================================================================
# LOAD / SAVE
# ============================================================================

def load_config():
    """Load config.json from %APPDATA%\\SEVEN, creating clean defaults if absent."""
    _migrate_old_data()
    defaults = get_defaults()

    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
                json.dump(defaults, fh, indent=4)
        except Exception as exc:
            _log.warning("could not write defaults: %s", exc)
        return defaults

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return _normalize(_fill_defaults(data, defaults))
    except Exception as exc:
        _log.warning("corrupt config, using defaults: %s", exc)
        return defaults


def save_config():
    """Persist KEY to disk. Thread-safe."""
    with _lock:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
                json.dump(KEY, fh, indent=4)
            return True
        except Exception as exc:
            _log.warning("could not save: %s", exc)
            return False


def update_config(updates):
    """Deep-merge updates into KEY and persist. Keys not mentioned are untouched."""
    def _merge(base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                _merge(base[key], value)
            else:
                base[key] = value

    with _lock:
        _merge(KEY, updates)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
                json.dump(KEY, fh, indent=4)
            return True
        except Exception as exc:
            _log.warning("could not save update: %s", exc)
            return False


KEY = load_config()


def sync_version():
    """Read the version from version.txt (written by Electron) or package.json."""
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        app_path = os.environ.get("SEVEN_APP_PATH", "")
        found = None

        for vp in (os.path.join(app_path, "version.txt") if app_path else None,
                   os.path.join(base, "version.txt"),
                   os.path.join(os.path.dirname(base), "version.txt")):
            if vp and os.path.exists(vp):
                try:
                    with open(vp, "r", encoding="utf-8") as fh:
                        found = fh.read().strip().lstrip("\ufeff") or None
                except Exception:
                    continue
                if found:
                    break

        if not found:
            for p in (os.path.join(app_path, "package.json") if app_path else None,
                      os.path.join(base, "package.json"),
                      os.path.join(os.path.dirname(base), "package.json")):
                if p and os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as fh:
                            found = json.loads(fh.read().lstrip("\ufeff")).get("version", "") or None
                    except Exception:
                        continue
                    if found:
                        break

        if found and found != KEY.get("version", ""):
            KEY["version"] = found
            save_config()
    except Exception as exc:
        _log.warning("version sync error: %s", exc)


sync_version()
