"""
=============================================================================
PROJECT SEVEN - backend/updater.py
Update checker and downloader

PURPOSE:
    - Checks Railway server for new releases
    - Compares with current version in package.json
    - Downloads .exe to temp folder with progress tracking
    - Signals Electron to run installer and quit
=============================================================================
"""

import os
import json
import threading
import requests
import tempfile
from packaging import version as pkg_version

# ── Config ──
SERVER_URL  = "https://vii-server-production.up.railway.app"
TIMEOUT     = 8
CHECK_DELAY = 15   # seconds after app start before first check

# ── State shared across threads ──
_state = {
    "update_available":  False,
    "checking":          False,
    "downloading":       False,
    "download_progress": 0,       # 0-100
    "download_path":     None,    # path to downloaded .exe
    "error":             None,
    "info":              None,    # full update dict from server
}


def get_state():
    return dict(_state)


def _read_current_version():
    """Read version from root package.json."""
    try:
        pkg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "package.json"
        )
        with open(pkg_path, "r") as f:
            return json.load(f).get("version", "1.1.0")
    except Exception:
        return "1.1.0"


def _get_tier():
    """Read current license tier from config."""
    try:
        import config
        return config.KEY.get("license", {}).get("tier", "free")
    except Exception:
        return "free"


def _is_lifetime():
    """
    Returns True if current license is lifetime
    (expires_at is None/empty in license cache).
    Lifetime users always get updates.
    """
    try:
        import config
        expires = config.KEY.get("license", {}).get("expires_at", None)
        return expires is None or expires == ""
    except Exception:
        return False


def check_for_updates(force=False):
    """
    Check Railway server for a new release.
    Runs on a background thread automatically.
    Returns result dict immediately if already checked (cached).
    """
    if _state["checking"] and not force:
        return get_state()

    def _check():
        _state["checking"] = True
        _state["error"]    = None

        current = _read_current_version()
        tier    = _get_tier()

        try:
            r = requests.get(
                f"{SERVER_URL}/api/updates/latest",
                params={"tier": tier, "current_version": current},
                timeout=TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("update_available"):
                    _state["update_available"] = True
                    _state["info"] = data
                else:
                    _state["update_available"] = False
                    _state["info"] = None
            else:
                _state["error"] = f"Server returned {r.status_code}"
        except requests.exceptions.ConnectionError:
            # Offline — not an error, just skip
            pass
        except Exception as e:
            _state["error"] = str(e)
        finally:
            _state["checking"] = False

    t = threading.Thread(target=_check, daemon=True, name="UpdateCheck")
    t.start()
    return get_state()


def start_auto_check():
    """
    Start background update checker.
    Waits CHECK_DELAY seconds after app start, then checks.
    Called once from main.py on startup.
    """
    def _delayed():
        import time
        time.sleep(CHECK_DELAY)
        check_for_updates()

    t = threading.Thread(target=_delayed, daemon=True, name="UpdateAutoCheck")
    t.start()


def download_update(progress_callback=None):
    """
    Download the update .exe to system temp folder.
    progress_callback(percent: int) called as download progresses.
    Returns (success: bool, path: str, error: str)
    """
    info = _state.get("info")
    if not info:
        return False, None, "No update info available"

    url = info.get("download_url")
    if not url:
        return False, None, "No download URL"

    _state["downloading"]       = True
    _state["download_progress"] = 0
    _state["error"]             = None

    try:
        version = info.get("version", "unknown")
        filename = f"SEVEN-Setup-{version}.exe"
        dest = os.path.join(tempfile.gettempdir(), filename)

        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int((downloaded / total) * 100)
                        _state["download_progress"] = pct
                        if progress_callback:
                            progress_callback(pct)

        _state["download_progress"] = 100
        _state["download_path"]     = dest
        _state["downloading"]       = False
        return True, dest, None

    except Exception as e:
        _state["downloading"] = False
        _state["error"]       = str(e)
        return False, None, str(e)


def start_download_thread(progress_callback=None):
    """Start download in background thread. State tracks progress."""
    def _dl():
        download_update(progress_callback)

    t = threading.Thread(target=_dl, daemon=True, name="UpdateDownload")
    t.start()