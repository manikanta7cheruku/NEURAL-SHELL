import os
import json
import threading
import requests
import tempfile

SERVER_URL  = "https://seven-server-u2rp.onrender.com"
TIMEOUT     = 8
CHECK_DELAY = 15

def _get_cache_file():
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        path = os.path.normpath(os.path.join(appdata, "SEVEN", "pending_update.json"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_update.json")

_DOWNLOAD_CACHE_FILE = _get_cache_file()

_state = {
    "update_available":  False,
    "checking":          False,
    "downloading":       False,
    "download_progress": 0,
    "download_path":     None,
    "error":             None,
    "info":              None,
}


def _get_cache_file():
    """Get pending_update.json path — always uses APPDATA."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        folder = os.path.normpath(os.path.join(appdata, "SEVEN"))
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "pending_update.json")
    # Fallback
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "pending_update.json")


def _load_pending_download():
    """On startup — check if a download was completed before restart."""
    try:
        cache_file = _get_cache_file()
        print("[UPDATER] Cache file: " + cache_file)
        if not os.path.exists(cache_file):
            print("[UPDATER] No pending download found")
            return
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        path = data.get("download_path", "")
        if path and os.path.exists(path):
            _state["download_path"]     = path
            _state["download_progress"] = 100
            _state["update_available"]  = True
            _state["info"]              = data.get("info")
            print("[UPDATER] Pending download restored: " + path)
        else:
            print("[UPDATER] Cached path gone: " + path)
            os.remove(cache_file)
    except Exception as e:
        print("[UPDATER] Load pending error: " + str(e))


def _save_pending_download(path, info):
    """Save download path so it survives app restart."""
    try:
        cache_file = _get_cache_file()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"download_path": path, "info": info}, f, indent=2)
        print("[UPDATER] Saved pending download: " + cache_file)
    except Exception as e:
        print("[UPDATER] Save pending error: " + str(e))


def _clear_pending_download():
    """Clear after successful install."""
    try:
        cache_file = _get_cache_file()
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print("[UPDATER] Cleared pending download cache")
    except Exception as e:
        print("[UPDATER] Clear pending error: " + str(e))


# Load pending download state on startup
_load_pending_download()


def get_state():
    return dict(_state)


def _read_current_version():
    """
    Read app version.
    Priority:
      1. version.txt (written by Electron on startup — most reliable)
      2. package.json (dev mode fallback)
    """
    try:
        import sys
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.environ.get("SEVEN_APP_PATH", "")

        # All places to look for version.txt
        version_txt_candidates = [
            os.path.join(app_path, "version.txt") if app_path else None,
            os.path.join(base, "version.txt"),
            os.path.join(os.path.dirname(base), "version.txt"),
        ]

        for vp in version_txt_candidates:
            if not vp:
                continue
            vp = os.path.normpath(vp)
            if os.path.exists(vp):
                with open(vp, "r", encoding="utf-8") as f:
                    v = f.read().strip().lstrip("\ufeff")
                if v:
                    print("[UPDATER] Version " + v + " (from version.txt)")
                    return v

        # Fallback: package.json for dev mode
        pkg_candidates = [
            os.path.join(app_path, "package.json") if app_path else None,
            os.path.join(base, "package.json"),
            os.path.join(os.path.dirname(base), "package.json"),
        ]

        for p in pkg_candidates:
            if not p:
                continue
            p = os.path.normpath(p)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().lstrip("\ufeff")
                    v = json.loads(content).get("version", "1.1.0")
                print("[UPDATER] Version " + v + " (from package.json)")
                return v

        print("[UPDATER] No version source found")
        return "1.1.0"
    except Exception as e:
        print("[UPDATER] Version read error: " + str(e))
        return "1.1.0"
    try:
        import sys
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.environ.get("SEVEN_APP_PATH", "")
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))

        candidates = [
            # Dev mode
            os.path.join(base, "package.json"),
            os.path.join(os.path.dirname(base), "package.json"),
            # Packaged — SEVEN_APP_PATH
            os.path.join(app_path, "package.json") if app_path else None,
            os.path.join(app_path, "..", "package.json") if app_path else None,
            # Packaged — relative to Python exe
            os.path.join(exe_dir, "package.json"),
            os.path.join(exe_dir, "..", "app", "package.json"),
            os.path.join(exe_dir, "..", "..", "app", "package.json"),
        ]

        candidates = [os.path.normpath(c) for c in candidates if c]

        for p in candidates:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read().lstrip("\ufeff")
                    v = json.loads(content).get("version", "1.1.0")
                print("[UPDATER] Version " + v + " from " + p)
                return v

        print("[UPDATER] package.json not found anywhere")
        return "1.1.0"
    except Exception as e:
        print("[UPDATER] Version read error: " + str(e))
        return "1.1.0"


def _get_tier():
    try:
        import config
        return config.KEY.get("license", {}).get("tier", "free")
    except Exception:
        return "free"


def _check_local_override():
    try:
        appdata = os.environ.get("APPDATA", "")
        p = os.path.normpath(os.path.join(appdata, "SEVEN", "update_override.json"))
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("[UPDATER] Override found: " + str(data.get("version", "")))
        return data
    except Exception:
        return None


def check_for_updates(force=False):
    if _state["checking"] and not force:
        return get_state()

    def _check():
        _state["checking"] = True
        _state["error"]    = None

        current = _read_current_version()
        tier    = _get_tier()

        override = _check_local_override()
        if override and override.get("update_available"):
            try:
                from packaging import version as pv
                ov = str(override.get("version", "0"))
                if pv.parse(ov) > pv.parse(current):
                    _state["update_available"] = True
                    _state["info"]             = override
                    _state["checking"]         = False
                    print("[UPDATER] Override active: " + ov)
                    return
            except Exception:
                pass

        try:
            url = SERVER_URL + "/api/updates/latest"
            print("[UPDATER] Checking server...")
            r = requests.get(
                url,
                params={"tier": tier, "current_version": current},
                timeout=TIMEOUT
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("update_available"):
                    _state["update_available"] = True
                    _state["info"]             = data
                    print("[UPDATER] Update available: " + str(data.get("version")))
                else:
                    _state["update_available"] = False
                    _state["info"]             = None
                    print("[UPDATER] Up to date")
            else:
                _state["error"] = "Server error: " + str(r.status_code)
        except requests.exceptions.ConnectionError:
            print("[UPDATER] Offline")
        except Exception as e:
            _state["error"] = str(e)
            print("[UPDATER] Error: " + str(e))
        finally:
            _state["checking"] = False

    t = threading.Thread(target=_check, daemon=True, name="UpdateCheck")
    t.start()
    return get_state()


def start_auto_check():
    def _delayed():
        import time
        time.sleep(CHECK_DELAY)
        check_for_updates()
        time.sleep(3)
        info = _state.get("info")
        if (
            _state.get("update_available")
            and info
            and info.get("download_mode") == "auto"
            and not _state.get("downloading")
            and not _state.get("download_path")
        ):
            start_download_thread()

    t = threading.Thread(target=_delayed, daemon=True, name="UpdateAutoCheck")
    t.start()


def download_update(progress_callback=None):
    info = _state.get("info")
    if not info:
        return False, None, "No update info"

    url = info.get("download_url")
    if not url:
        return False, None, "No download URL"

    _state["downloading"]       = True
    _state["download_progress"] = 0
    _state["error"]             = None

    try:
        ver      = str(info.get("version", "unknown"))
        filename = "SEVEN-Setup-" + ver + ".exe"
        dest     = os.path.join(tempfile.gettempdir(), filename)

        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()

        total      = int(r.headers.get("content-length", 0))
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
        _save_pending_download(dest, _state.get("info"))
        return True, dest, None

    except Exception as e:
        _state["downloading"] = False
        _state["error"]       = str(e)
        return False, None, str(e)


def start_download_thread(progress_callback=None):
    def _dl():
        download_update(progress_callback)

    t = threading.Thread(target=_dl, daemon=True, name="UpdateDownload")
    t.start()