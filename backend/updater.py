"""
PROJECT SEVEN - backend/updater.py
Dual-Pathway Update Verification & Delivery Subsystem.

Primary: the Render server decides what each user is offered (staged and tier releases, withdrawing a bad release).
Fallback: GitHub Releases, only when the Render server cannot be reached at all.
Every download is checked (a real installer of the right version, and the published SHA-256 when there is one) before it
can be installed.

Two kinds of update (see docs/operations/updates.md):
    patch   only the files that changed since the version this PC has (a few MB), when the release offers one for exactly
            this version; checked file by file and applied with a backup that is put back if anything fails
    full    the whole installer, for every other case
Installing is backend/update_install.py: it waits for Seven to exit, installs, checks the version on disk and records the
result, which the next start reads (get_state()["last_result"]).
"""

import os
import re
import time
import hashlib
from time import strftime as _strftime
import json
import threading
import requests
import tempfile
import shutil

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
    "last_checked":      None,
    "check_failed":      False,    # the last check could not reach any update service
    "download_bytes":    0,        # what is on this PC so far, and what the whole download is, in bytes
    "download_total":    0,
    "download_speed":    0,        # bytes per second, smoothed
    "download_eta":      None,     # seconds left, or None while it is still being worked out
    "update_kind":       "full",   # "patch" (changed files only) or "full" (the whole installer)
    "last_result":       None,     # what the last install did: {status: ok|failed, from, to, detail, log}
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


def _newer(candidate, current):
    try:
        from packaging import version as pv
        return pv.parse(str(candidate)) > pv.parse(str(current))
    except Exception:
        return str(candidate) != str(current)


def _stage_dir(version):
    return os.path.join(tempfile.gettempdir(), "seven-update", "stage-" + str(version))


def _load_pending_download():
    """On startup: pick up a download that finished before the restart, unless Seven has since been updated."""
    try:
        cache_file = _get_cache_file()
        if not os.path.exists(cache_file):
            return
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        path = data.get("download_path", "")
        info = data.get("info") or {}
        kind = data.get("kind", "full")
        if not _newer(info.get("version", "0"), _read_current_version()):       # already installed: nothing is pending
            _forget_files(path, kind, info)
            os.remove(cache_file)
            return
        if kind == "patch":
            ok = bool(path) and os.path.isfile(os.path.join(_stage_dir(info.get("version", "")), "patch.json"))
        else:
            ok = bool(path) and os.path.exists(path) and _verify_pending(path, info)
            if path and os.path.exists(path) and not ok:
                os.remove(path)
        if ok:
            _state.update(download_path=path, download_progress=100, update_available=True, info=info, update_kind=kind)
            print("[UPDATER] Pending download restored: " + path)
        else:
            os.remove(cache_file)
    except Exception as e:
        print("[UPDATER] Load pending error: " + str(e))


def _forget_files(path, kind, info):
    try:
        if path and os.path.exists(path):
            os.remove(path)
        if kind == "patch":
            shutil.rmtree(_stage_dir(info.get("version", "")), ignore_errors=True)
    except OSError:
        pass


def _verify_pending(path, info):
    try:
        return verify_file(path, (info or {}).get("sha256", ""))[0]
    except Exception:
        return False


def _save_pending_download(path, info):
    """Save download path so it survives app restart."""
    try:
        cache_file = _get_cache_file()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"download_path": path, "info": info, "kind": _state.get("update_kind", "full")}, f, indent=2)
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


def get_state():
    """The state for the Updates page, plus what Download would fetch for this PC ("patch" or "full") and how big that is."""
    state = dict(_state)
    info = state.get("info") or {}
    kind = state["update_kind"] if state.get("download_path") or state.get("downloading") else plan(info) if info else "full"
    state["plan"] = kind
    state["download_size_mb"] = (info.get("patch") or {}).get("size_mb") if kind == "patch" else info.get("size_mb", 0)
    return state


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


RENDER_UPDATE_URL   = "https://seven-server-a825.onrender.com/api/updates/latest"
GITHUB_RELEASES_URL = "https://api.github.com/repos/manikanta7cheruku/seven-releases/releases/latest"
RENDER_ATTEMPTS     = (10, 30, 45)   # Render's free tier sleeps; the first call after a quiet spell can take about a minute
DOWNLOAD_ATTEMPTS   = 3
MIN_INSTALLER_BYTES = 1024 * 1024    # anything smaller is an error page, not an installer


# ── Release notes ─────────────────────────────────────────────────────────

_GROUPS = (
    ("new",      re.compile(r"^(new|added|features?|what'?s new)\b", re.I)),
    ("improved", re.compile(r"^(improved|improvements?|changed|changes|updated)\b", re.I)),
    ("fixed",    re.compile(r"^(fixed|fixes|bug ?fix(es)?|corrections?)\b", re.I)),
)
_LABELS = {"new": "New", "improved": "Improved", "fixed": "Fixed"}


def _lines(raw):
    if isinstance(raw, str):
        raw = raw.splitlines()
    out = []
    for line in raw or []:
        text = str(line).strip().lstrip("-*• ").strip()
        if text:
            out.append(text)
    return out


def _clean_notes(raw):
    """The notes the server sends: {"new": [...], "improved": [...], "fixed": [...]}, tolerant of anything else."""
    notes = {}
    if isinstance(raw, dict):
        for key in _LABELS:
            items = _lines(raw.get(key))
            if items:
                notes[key] = items
    return notes


def _flat(notes, extra):
    lines = [f"{_LABELS[k]}: {item}" for k in _LABELS for item in notes.get(k, [])]
    return lines + [line for line in extra if line not in lines]


def parse_release_body(body):
    """
    Turn a GitHub release description into (summary, notes, loose_lines).
    A line of plain text before any heading is the summary. Headings called New / Improved / Fixed start a group
    and the bullets under them fill it. Bullets with no heading are kept as plain lines.
    """
    summary, notes, loose, current = "", {}, [], None
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = re.sub(r"^#{1,6}\s*|[:*_]+", "", line).strip() if (line.startswith("#") or line.endswith(":")) else None
        if heading is not None:
            current = next((key for key, rx in _GROUPS if rx.match(heading)), None)
            continue
        if line[0] in "-*•":
            text = line.lstrip("-*• ").strip()
            if current:
                notes.setdefault(current, []).append(text)
            elif text:
                loose.append(text)
        elif not summary and current is None:
            summary = line[:300]
    return summary, notes, loose


# ── Integrity ─────────────────────────────────────────────────────────────

def verify_file(path, sha256=""):
    """Is this file a real installer, and (when a checksum is known) the exact file that was published?"""
    try:
        size = os.path.getsize(path)
        if size < MIN_INSTALLER_BYTES:
            return False, "The downloaded file is too small to be the installer."
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                return False, "The downloaded file is not a Windows installer."
        if sha256:
            digest = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest().lower() != sha256.strip().lower():
                return False, "The download does not match the published checksum, so Seven will not install it."
        return True, ""
    except OSError as e:
        return False, f"Could not read the downloaded file: {e}"


def installer_version(path):
    """The version stamped into an installer (Windows file properties), or "" when it has none. An installer built without
    bumping the version says 1.3.2 while the dashboard says 1.3.3: Seven would install it, still be 1.3.2, and offer the
    update again for ever."""
    try:
        import ctypes
        from ctypes import wintypes
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return ""
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(path, 0, size, buf):
            return ""
        ptr, length = ctypes.c_void_p(), wintypes.UINT()
        if not ctypes.windll.version.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)) or length.value < 52:
            return ""
        fixed = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32 * 13)).contents
        ms, ls = fixed[4], fixed[5]                                             # dwProductVersionMS / LS
        v = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}"
        return "" if v == "0.0.0" else v
    except Exception:
        return ""


def check_installer_version(path, expected):
    """(ok, message). An installer that carries no version is trusted (older builds); one that carries another version is not."""
    found = installer_version(path)
    if found and expected and found != str(expected):
        return False, (f"This installer is version {found}, but the update says {expected}. It was probably built before "
                       "the version number was changed. Seven will not install it.")
    return True, ""


def _blocked_file():
    return os.path.join(os.path.dirname(_get_cache_file()), "patch_blocked.json")


def _patch_blocked(version):
    """A changed-files update that this PC could not take (its files are not exactly the build the patch was made from) is not tried
    again for that version: the full installer is used."""
    try:
        with open(_blocked_file(), encoding="utf-8") as f:
            return str(version) in json.load(f).get("versions", [])
    except (OSError, ValueError):
        return False


def _block_patch(version):
    try:
        with open(_blocked_file(), encoding="utf-8") as f:
            versions = json.load(f).get("versions", [])
    except (OSError, ValueError):
        versions = []
    if str(version) not in versions:
        versions.append(str(version))
    with open(_blocked_file(), "w", encoding="utf-8") as f:
        json.dump({"versions": versions}, f)


def plan(info):
    """"patch" when the release has changed-files-only package for exactly the version installed here, and this is an
    installed Seven that can take it; "full" otherwise."""
    patch = (info or {}).get("patch") or {}
    if patch.get("url") and patch.get("from") == _read_current_version() and not _patch_blocked((info or {}).get("version", "")):
        try:
            from backend import update_install
            if update_install.install_dir():
                return "patch"
        except Exception:
            pass
    return "full"


def verify_downloaded():
    """Called just before installing. Returns (ok, message)."""
    path = _state.get("download_path")
    info = _state.get("info") or {}
    if _state.get("update_kind") == "patch":
        if not path or not os.path.isfile(os.path.join(_stage_dir(info.get("version", "")), "patch.json")):
            return False, "The downloaded update is missing. Please download it again."
        return True, ""
    if not path or not os.path.exists(path):
        return False, "The downloaded file is missing. Please download the update again."
    ok, why = verify_file(path, info.get("sha256", ""))
    return (ok, why) if not ok else check_installer_version(path, info.get("version", ""))


def _discard_download():
    path = _state.get("download_path")
    for p in (path, (path or "") + ".part"):
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    if _state.get("update_kind") == "patch":
        shutil.rmtree(_stage_dir((_state.get("info") or {}).get("version", "")), ignore_errors=True)
    _state["download_path"] = None
    _state["download_progress"] = 0
    _clear_pending_download()


# ── Checking ──────────────────────────────────────────────────────────────

def _auto_enabled():
    """Settings, Updates, 'Check for updates automatically'. A manual 'Check now' always works."""
    try:
        import config
        return bool(config.KEY.get("updates", {}).get("auto_check", True))
    except Exception:
        return True


def _fetch_render(tier, current):
    """Ask the Render server. Retries while it wakes up. Returns its JSON answer, or None when it could not be reached."""
    for i, timeout in enumerate(RENDER_ATTEMPTS):
        reason = ""
        try:
            r = requests.get(RENDER_UPDATE_URL, params={"tier": tier, "current_version": current}, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code < 500 and r.status_code != 429:
                return None                       # a real "no", retrying will not change it
            reason = f"HTTP {r.status_code}"
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            reason = type(e).__name__
        except ValueError:
            return None
        if i < len(RENDER_ATTEMPTS) - 1:
            print(f"[UPDATER] Render server not ready ({reason}), trying again...")
            time.sleep(3)
    return None


def _patch_info(raw):
    """The changed-files-only package the server offers, or None: {from, url, sha256, size_mb}."""
    if not isinstance(raw, dict) or not raw.get("url") or not raw.get("from"):
        return None
    url = str(raw["url"])
    if not url.lower().startswith("https://"):
        return None
    return {"from": str(raw["from"]).strip().lstrip("vV"), "url": url, "sha256": str(raw.get("sha256", "") or "").strip().lower(),
            "size_mb": raw.get("size_mb", 0)}


def _info_from_server(data):
    notes = _clean_notes(data.get("notes"))
    loose = _lines(data.get("changelog"))
    # The server's flat changelog repeats the grouped notes with a label in front; keep only what is not repeated.
    grouped = {f"{_LABELS[k]}: {item}" for k in notes for item in notes[k]}
    extra = [line for line in loose if line not in grouped]
    return {
        "version":       str(data.get("version", "")).strip().lstrip("vV"),
        "summary":       str(data.get("summary", "") or "").strip(),
        "notes":         notes,
        "changelog":     _flat(notes, extra),
        "download_url":  data.get("download_url"),
        "download_mode": data.get("download_mode", "manual"),
        "size_mb":       data.get("size_mb", 0),
        "published_at":  data.get("published_at", ""),
        "is_critical":   bool(data.get("is_critical", False)),
        "sha256":        str(data.get("sha256", "") or "").strip().lower(),
        "patch":         _patch_info(data.get("patch")),
        "source":        "server",
    }


def _info_from_github(release, latest_version):
    download_url, size_bytes = "", 0
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".exe") and "Setup" in name:
            download_url = asset.get("browser_download_url", "")
            size_bytes = asset.get("size", 0)
            break
    body = release.get("body", "") or ""
    summary, notes, loose = parse_release_body(body)
    if not notes and not loose and body.strip():
        loose = [line for line in (l.strip() for l in body.splitlines()) if line and not line.startswith("#")][:20]
    match = re.search(r"sha-?256\W{0,6}([0-9a-fA-F]{64})", body, re.I)
    return {
        "version":       latest_version,
        "summary":       summary,
        "notes":         notes,
        "changelog":     _flat(notes, loose),
        "download_url":  download_url,
        "download_mode": "manual",
        "size_mb":       round(size_bytes / (1024 * 1024), 1) if size_bytes else 0,
        "published_at":  release.get("published_at", ""),
        "is_critical":   bool(re.search(r"\[critical\]", body, re.I)),
        "sha256":        match.group(1).lower() if match else "",
        "source":        "github",
    }


def _no_update():
    _state["update_available"] = False
    _state["info"] = None
    if not _state["downloading"] and _state.get("download_path"):
        _discard_download()          # the release was withdrawn after it was downloaded


def check_for_updates(force=False):
    """
    Check for updates (in the background; poll get_state()).
    The Render server decides what each user is offered, so staged releases and withdrawing a bad release work.
    GitHub is only asked when the Render server cannot be reached at all.
    """
    if _state["checking"] and not force:
        return get_state()

    def _check():
        _state["checking"] = True
        _state["error"]    = None
        try:
            current = _read_current_version()
            tier    = _get_tier()

            override = _check_local_override()
            if override and override.get("update_available"):
                try:
                    from packaging import version as pv
                    if pv.parse(str(override.get("version", "0"))) > pv.parse(current):
                        _state["update_available"] = True
                        _state["info"]             = override
                        _state["check_failed"]     = False
                        print("[UPDATER] Override active: " + str(override.get("version")))
                        return
                except Exception:
                    pass

            # ── Render server ──
            print(f"[UPDATER] Checking Render server for {tier} tier...")
            data = _fetch_render(tier, current)
            if data is not None:
                _state["check_failed"] = False
                if data.get("update_available") and data.get("version"):
                    _state["update_available"] = True
                    _state["info"] = _info_from_server(data)
                    print("[UPDATER] Update available from Render: " + _state["info"]["version"])
                else:
                    _no_update()
                    print("[UPDATER] Up to date: " + current)
                return

            # ── GitHub (only when Render is unreachable) ──
            print("[UPDATER] Render unreachable, checking GitHub releases...")
            try:
                r = requests.get(GITHUB_RELEASES_URL, headers={"Accept": "application/vnd.github.v3+json"}, timeout=TIMEOUT)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                _state["check_failed"] = True
                print("[UPDATER] Offline, skipping check")
                return

            if r.status_code == 200:
                release = r.json()
                latest_version = release.get("tag_name", "").lstrip("vV")
                _state["check_failed"] = False
                if not latest_version:
                    return
                try:
                    from packaging import version as pv
                    is_newer = pv.parse(latest_version) > pv.parse(current)
                except Exception:
                    is_newer = latest_version != current
                if is_newer:
                    _state["update_available"] = True
                    _state["info"] = _info_from_github(release, latest_version)
                    print("[UPDATER] Update available on GitHub: " + latest_version)
                else:
                    _no_update()
                    print("[UPDATER] Up to date: " + current)
            elif r.status_code == 404:
                _state["check_failed"] = False
                _no_update()
            else:
                _state["check_failed"] = True
                print("[UPDATER] GitHub error: " + str(r.status_code))
        except Exception as e:
            _state["check_failed"] = True
            print("[UPDATER] Error: " + str(e))
        finally:
            _state["checking"] = False
            _state["last_checked"] = _strftime("%Y-%m-%dT%H:%M:%S")

    t = threading.Thread(target=_check, daemon=True, name="UpdateCheck")
    t.start()
    return get_state()


def start_auto_check():
    def _delayed():
        global _version_logged

        # Log version once at startup
        v = _read_current_version()
        if not _version_logged:
            print(f"[UPDATER] Version {v}")
            _version_logged = True

        time.sleep(CHECK_DELAY)
        while True:
            if _auto_enabled():
                check_for_updates()
                # Auto-download if the release asks for it
                time.sleep(3)
                for _ in range(90):                      # wait for the check to finish (a sleeping server can be slow)
                    if not _state.get("checking"):
                        break
                    time.sleep(2)
                info = _state.get("info")
                if (
                    _state.get("update_available")
                    and info
                    and info.get("download_mode") == "auto"
                    and not _state.get("downloading")
                    and not _state.get("download_path")
                ):
                    start_download_thread()
            time.sleep(RECHECK_DELAY)

    t = threading.Thread(target=_delayed, daemon=True, name="UpdateAutoCheck")
    t.start()


# ── Downloading ───────────────────────────────────────────────────────────

def _progress(done, total, started, base):
    """Bytes, percentage, a smoothed speed and the time left, for the Updates page."""
    now = time.time()
    elapsed = max(now - started, 0.001)
    speed = (done - base) / elapsed
    old = _state.get("download_speed") or 0
    speed = speed if not old else old * 0.7 + speed * 0.3
    _state.update(download_bytes=done, download_total=total, download_speed=int(speed),
                  download_eta=int((total - done) / speed) if total and speed > 1024 else None)
    if total > 0:
        _state["download_progress"] = min(99, int(done * 100 / total))


def _stream_to(url, part_path, progress_callback):
    """Download to part_path, continuing from what is already there when the server allows it (a connection that drops
    at 90% of a large file costs seconds, not minutes)."""
    have = os.path.getsize(part_path) if os.path.exists(part_path) else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    r = requests.get(url, stream=True, timeout=60, headers=headers)
    if r.status_code == 416:                                       # asked for more than exists: the file is complete
        r.close()
        return
    r.raise_for_status()
    resumed = r.status_code == 206 and have > 0
    if not resumed:
        have = 0
    length = int(r.headers.get("content-length", 0) or 0)
    total = have + length
    done, started = have, time.time()
    with open(part_path, "ab" if resumed else "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                _progress(done, total, started, have)
                if progress_callback and total > 0:
                    progress_callback(_state["download_progress"])
    if total and done != total:
        raise IOError(f"incomplete download ({done} of {total} bytes)")


def _download_target(info):
    """(kind, url, dest, sha256): what to fetch for this release on this PC."""
    ver = str(info.get("version", "unknown"))
    kind = plan(info)
    if kind == "patch":
        patch = info["patch"]
        dest = os.path.join(tempfile.gettempdir(), "seven-update", f"SEVEN-Patch-{patch['from']}-to-{ver}.zip")
        return kind, patch["url"], dest, patch.get("sha256", "")
    return kind, info.get("download_url"), os.path.join(tempfile.gettempdir(), "SEVEN-Setup-" + ver + ".exe"), info.get("sha256", "")


def _finish_patch(zip_path, info, sha256):
    """Unpack and prove the changed files before anything is installed."""
    from backend import update_package
    update_package.extract_and_verify(zip_path, _stage_dir(info["version"]), sha256)


def download_update(progress_callback=None):
    info = _state.get("info")
    if not info:
        return False, None, "No update info"

    kind, url, dest, sha256 = _download_target(info)
    if not url:
        return False, None, "No download URL"
    if not str(url).lower().startswith("https://"):
        _state["error"] = "This update's download link is not secure, so Seven will not use it."
        return False, None, _state["error"]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    _state.update(update_kind=kind, download_bytes=0, download_total=0, download_speed=0, download_eta=None)

    # Already downloaded (for instance before a restart) and proven to be the right file: nothing to do.
    if kind == "full" and sha256 and os.path.exists(dest) and verify_file(dest, sha256)[0]:
        _state.update(download_path=dest, download_progress=100, downloading=False, error=None)
        _save_pending_download(dest, info)
        return True, dest, None

    _state["downloading"]       = True
    _state["download_progress"] = 0
    _state["error"]             = None

    reason = ""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            _stream_to(url, part, progress_callback)
            if kind == "patch":
                _finish_patch(part, info, sha256)
            else:
                ok, why = verify_file(part, sha256)
                if ok:
                    ok, why = check_installer_version(part, info.get("version", ""))
                if not ok:
                    raise IOError(why)
            os.replace(part, dest)
            _state["download_progress"] = 100
            _state["download_path"]     = dest
            _state["downloading"]       = False
            _state["download_eta"]      = 0
            _save_pending_download(dest, info)
            return True, dest, None
        except Exception as e:
            reason = str(e)
            print(f"[UPDATER] Download attempt {attempt} failed: {reason}")
            if _bad_file(reason):                                   # resuming would only repeat the mistake
                try:
                    if os.path.exists(part):
                        os.remove(part)
                except OSError:
                    pass
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(2 * attempt)

    _state["downloading"]       = False
    _state["download_progress"] = 0
    if _bad_file(reason):
        _state["error"] = reason
    else:
        _state["error"] = "The download did not finish. Check your connection and press Download to try again."
    return False, None, reason


def _bad_file(reason):
    return any(k in reason for k in ("checksum", "not a Windows", "too small", "damaged", "does not match", "installer is version"))


def start_download_thread(progress_callback=None):
    def _dl():
        download_update(progress_callback)

    t = threading.Thread(target=_dl, daemon=True, name="UpdateDownload")
    t.start()


def install_update():
    """Hand over to the script that installs the downloaded update after Seven exits. Returns {"quit": True} when it has
    started; raises ValueError with a sentence for the person when it cannot."""
    from backend import update_install
    ok, why = verify_downloaded()
    if not ok:
        _discard_download()
        _state["error"] = why
        raise ValueError(why)
    info = _state.get("info") or {}
    install = update_install.install_dir()
    if not install:
        raise ValueError("Updates install into the installed Seven. This copy runs from source.")
    current, target = _read_current_version(), str(info.get("version", ""))
    pids = [os.getpid(), os.getppid()]
    update_install.clear_result()
    if _state.get("update_kind") == "patch":
        script = update_install.patch_script(_stage_dir(target), _state["download_path"], install, current, target, pids)
    else:
        script = update_install.installer_script(_state["download_path"], install, current, target, pids)
    path = update_install.launch(script)
    print("[UPDATER] Update script started: " + path)
    return {"quit": True, "kind": _state.get("update_kind", "full"), "script": path}


def _load_result():
    """At start: what the last install did. A success is told once; a failure stays until it is dismissed."""
    try:
        from backend import update_install
        result = update_install.read_result()
        if not result:
            return
        current = _read_current_version()
        if result.get("status") == "ok" and result.get("to") == current:
            _state["last_result"] = {**result, "status": "ok"}
            _clear_pending_download()
        elif result.get("status") == "ok":
            _state["last_result"] = {**result, "status": "failed",
                                     "detail": f"Seven reports {current}, not {result.get('to')}, after the update."}
        else:
            _state["last_result"] = result
            if "[base-mismatch]" in str(result.get("detail", "")):
                _block_patch(result.get("to", ""))                     # next time: the full installer
                _discard_download()
                _state["last_result"] = {**result, "detail": str(result["detail"]).replace("[base-mismatch] ", "")}
    except Exception as e:
        print("[UPDATER] Result read error: " + str(e))


def dismiss_result():
    try:
        from backend import update_install
        update_install.clear_result()
    except Exception:
        pass
    _state["last_result"] = None


# Load pending download state on startup (after everything it uses is defined)
_load_pending_download()
_load_result()
