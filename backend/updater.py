"""
PROJECT SEVEN - backend/updater.py
Dual-Pathway Update Verification & Delivery Subsystem.

Primary: Query Render Master DB (allows selective tier deployments).
Fallback: Query GitHub CDN directly (ensures high availability).
"""

import os
import json
import threading
import requests
import tempfile
from colorama import Fore

TIMEOUT        = 10
CHECK_DELAY    = 15       # First check after 15 seconds
RECHECK_DELAY  = 7200     # Recheck every 2 hours
_version_logged = False   # Log version only once

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
    # Fallback to current directory
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "pending_update.json")


def _load_pending_download():
    """On startup — check if a download was completed before restart."""
    try:
        cache_file = _get_cache_file()
        if not os.path.exists(cache_file):
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
    """Read local version.txt with fallback to package.json."""
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.environ.get("SEVEN_APP_PATH", "")

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
                    return v

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
                return v

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
    except Exception as e:
        print(f"[UPDATER] Override check failed: {e}")
        return None


def check_for_updates(force=False):
    """
    Check for updates.
    Tries Render Server first. Falls back to GitHub Releases directly if offline.
    """
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

        # ── Pathway 1: Render Server Check (Staged/Tiered Releases) ──
        try:
            RENDER_UPDATE_URL = "https://seven-server-a825.onrender.com/api/updates/latest"
            print(f"[UPDATER] Checking Render server for {tier} tier...")

            r = None
            try:
                r = requests.get(
                    RENDER_UPDATE_URL,
                    params={"tier": tier, "current_version": current},
                    timeout=TIMEOUT,
                )
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                print("[UPDATER] Render server waking up, retrying...")
                import time
                time.sleep(5)
                r = requests.get(
                    RENDER_UPDATE_URL,
                    params={"tier": tier, "current_version": current},
                    timeout=45,
                )

            if r is not None and r.status_code == 200:
                data = r.json()
                if data.get("update_available"):
                    raw_changelog = data.get("changelog", [])
                    if isinstance(raw_changelog, str):
                        changelog = [
                            line.strip()
                            for line in raw_changelog.splitlines()
                            if line.strip()
                        ]
                    elif isinstance(raw_changelog, list):
                        changelog = [str(c).strip() for c in raw_changelog if str(c).strip()]
                    else:
                        changelog = []

                    _state["update_available"] = True
                    _state["info"] = {
                        "version":       data.get("version", "").strip().lstrip("vV"),
                        "changelog":     changelog,
                        "download_url":  data.get("download_url"),
                        "download_mode": data.get("download_mode", "manual"),
                        "size_mb":       data.get("size_mb", 0),
                        "published_at":  data.get("published_at", ""),
                        "is_critical":   bool(data.get("is_critical", False)),
                    }
                    print("[UPDATER] Update available from Render: " + data.get("version", ""))
                    _state["checking"] = False
                    return
        except Exception as se:
            print(f"[UPDATER] Render check skipped: {se}")

        # ── Pathway 2: GitHub Releases CDN (Fallback/High-Availability) ──
        try:
            GITHUB_RELEASES_URL = "https://api.github.com/repos/manikanta7cheruku/seven-releases/releases/latest"
            print("[UPDATER] Checking GitHub releases fallback...")

            r = requests.get(
                GITHUB_RELEASES_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=TIMEOUT,
            )

            if r.status_code == 200:
                release = r.json()
                latest_version = release.get("tag_name", "").lstrip("v")

                if not latest_version:
                    print("[UPDATER] No version tag found in release")
                    _state["checking"] = False
                    return

                try:
                    from packaging import version as pv
                    is_newer = pv.parse(latest_version) > pv.parse(current)
                except Exception:
                    is_newer = latest_version != current

                if is_newer:
                    assets = release.get("assets", [])
                    download_url = ""
                    size_bytes = 0
                    for asset in assets:
                        name = asset.get("name", "")
                        if name.endswith(".exe") and "Setup" in name:
                            download_url = asset.get("browser_download_url", "")
                            size_bytes = asset.get("size", 0)
                            break

                    body = release.get("body", "")
                    changelog = []
                    for line in body.splitlines():
                        line = line.strip()
                        if line.startswith("- ") or line.startswith("* "):
                            changelog.append(line[2:].strip())
                    if not changelog:
                        for line in body.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#"):
                                changelog.append(line)
                    if not changelog and body.strip():
                        changelog = [body.strip()[:200]]

                    _state["update_available"] = True
                    _state["info"] = {
                        "version":       latest_version,
                        "changelog":     changelog,
                        "download_url":  download_url,
                        "download_mode": "manual",
                        "size_mb":       round(size_bytes / (1024 * 1024), 1) if size_bytes else 0,
                        "published_at":  release.get("published_at", ""),
                        "is_critical":   "critical" in release.get("body", "").lower(),
                    }
                    print("[UPDATER] Fallback Update available on GitHub: " + latest_version)
                else:
                    _state["update_available"] = False
                    _state["info"]             = None
                    print("[UPDATER] Up to date: " + current)

            elif r.status_code == 403:
                print("[UPDATER] GitHub rate limited — will retry later")
            elif r.status_code == 404:
                print("[UPDATER] No releases found on GitHub")
                _state["update_available"] = False
            else:
                _state["error"] = "GitHub API error: " + str(r.status_code)
                print("[UPDATER] GitHub error: " + str(r.status_code))

        except requests.exceptions.ConnectionError:
            print("[UPDATER] Offline — skipping check")
        except requests.exceptions.Timeout:
            print("[UPDATER] Update check timed out")
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
        global _version_logged

        # Log version once at startup
        v = _read_current_version()
        if not _version_logged:
            print(f"[UPDATER] Version {v}")
            _version_logged = True

        time.sleep(CHECK_DELAY)
        check_for_updates()

        # Auto-download if applicable
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

        # Recheck every 2 hours — silently
        while True:
            time.sleep(RECHECK_DELAY)
            check_for_updates()

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