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
SERVER_URL  = "https://seven-server-u2rp.onrender.com"
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
    """Read version from root package.json. Handles Windows path encoding."""
    try:
        # Try multiple locations — works in both dev and packaged app
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(base, "package.json"),
            os.path.join(os.path.dirname(base), "package.json"),
            os.path.join(
                os.environ.get("SEVEN_APP_PATH", ""),
                "..", "package.json"
            ),
        ]
        for pkg_path in candidates:
            pkg_path = os.path.normpath(pkg_path)
            if os.path.exists(pkg_path):
                with open(pkg_path, "r", encoding="utf-8") as f:
                    version = json.load(f).get("version", "1.1.0")
                    print(f"[UPDATER] Version {version} from {pkg_path}")
                    return version
        print("[UPDATER] package.json not found — using default version")
        return "1.1.0"
    except Exception as e:
        print(f"[UPDATER] Version read error: {e}")
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


def _check_local_override():
    """
    Check for local update override file.
    Used when server is down — admin sets update via terminal.
    File: %APPDATA%\SEVEN\update_override.json
    """
    try:
        import json
        override = os.path.join(
            os.environ.get("APPDATA", ""),
            "SEVEN", "update_override.json"
        )
        if not os.path.exists(override):
            return None
        with open(override, "r") as f:
            data = json.load(f)
        print(f"[UPDATER] Local override found: v{data.get('version')}")
        return data
    except Exception:
        return None


def check_for_updates(force=False):
    """
    Check server for new release.
    Falls back to local override file if server unavailable.
    """
    if _state["checking"] and not force:
        return get_state()

    def _check():
        _state["checking"] = True
        _state["error"]    = None

        current = _read_current_version()
        tier    = _get_tier()

        # Check local override first (works without server)
        override = _check_local_override()
        if override and override.get("update_available"):
            from packaging import version as pv
            try:
                if pv.parse(override["version"]) > pv.parse(current):
                    _state["update_available"] = True
                    _state["info"]             = override
                    _state["checking"]         = False
                    print(f"[UPDATER] Override update: {override['version']}")
                    return
            except Exception:
                pass

        try:
            url = f"{SERVER_URL}/api/updates/latest"
            print(f"[UPDATER] Checking {url} tier={tier} current={current}")
            r = requests.get(
                url,
                params={"tier": tier, "current_version": current},
                timeout=TIMEOUT
            )
            print(f"[UPDATER] Response: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"[UPDATER] Data: {data}")
                if data.get("update_available"):
                    _state["update_available"] = True
                    _state["info"]             = data
                    print(f"[UPDATER] Update available: {data.get('version')}")
                else:
                    _state["update_available"] = False
                    _state["info"]             = None
                    print(f"[UPDATER] Already up to date")
            else:
                _state["error"] = f"Server returned {r.status_code}"
                print(f"[UPDATER] Error: {_state['error']}")
        except requests.exceptions.ConnectionError:
            print("[UPDATER] Offline — skipping update check")
        except Exception as e:
            _state["error"] = str(e)
            print(f"[UPDATER] Exception: {e}")
        finally:
            _state["checking"] = False

    t = threading.Thread(target=_check, daemon=True, name="UpdateCheck")
    t.start()
    return get_state()


def start_auto_check():
    """
    Start background update checker.
    Waits CHECK_DELAY seconds after startup then checks.
    If update found and mode is auto → starts download automatically.
    """
    def _delayed():
        import time
        time.sleep(CHECK_DELAY)
        check_for_updates()

        # Wait for check to complete
        time.sleep(3)

        # If auto download mode → start immediately
        info = _state.get("info")
        if (
            _state.get("update_available")
            and info
            and info.get("download_mode") == "auto"
            and not _state.get("downloading")
            and not _state.get("download_path")
        ):
            print("[UPDATER] Auto download mode — starting download")
            start_download_thread()

    t = threading.Thread(
        target=_delayed, daemon=True, name="UpdateAutoCheck"
    )
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