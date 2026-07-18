"""
=============================================================================
trigger_daemon.py

Independent background process for trigger activation.
Runs even when Seven UI is fully closed.

RESPONSIBILITIES:
  1. Global hotkey listener (keyboard hooks)
  2. Voice trigger listener ("Seven [word]" detection via Whisper)
  3. Audio trigger listener (snap/clap detection via YAMNet)
  4. Trigger execution (launches apps, restores workspaces)
  5. Reload triggers when DB changes (via signal file)

LIFECYCLE:
  Spawned by main.py at startup as detached process
  Registered in Windows Task Scheduler for auto-start at login
  Survives Seven quit (detached, independent)
  Single instance enforced via mutex

PROCESS ARCHITECTURE:
  Main thread: hotkey listener (blocking keyboard hook)
  Thread 2: voice listener (Whisper STT)
  Thread 3: audio listener (YAMNet classifier)
  Thread 4: DB reload poller

COMMUNICATION:
  Reads: seven_data/triggers.db (SQLite WAL)
  Reads: seven_data/trigger_reload.signal (daemon reloads triggers)
  Checks: port 7777 to know if Seven is running
  Sends: TCP 7891 to overlay_daemon for notifications + arrangement
=============================================================================
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import threading
from datetime import datetime

# Hide console window ONLY when running as pythonw.exe (background daemon)
# python.exe keeps console visible for debugging
if sys.platform == "win32":
    try:
        import ctypes
        if "pythonw" in sys.executable.lower():
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass

# Force UTF-8 encoding for all output — fixes Whisper checkmark character
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass

# Production logging — write all stdout/stderr to rotating log file
# so we can diagnose user issues even in silent pythonw.exe mode.
_LOG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')),
                        'SEVEN', 'logs')
try:
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, 'trigger_daemon.log')

    # Rotate if log exceeds 2MB — keep 3 backups
    if os.path.exists(_LOG_FILE) and os.path.getsize(_LOG_FILE) > 2 * 1024 * 1024:
        for i in range(2, 0, -1):
            _old = os.path.join(_LOG_DIR, f'trigger_daemon.log.{i}')
            _new = os.path.join(_LOG_DIR, f'trigger_daemon.log.{i+1}')
            if os.path.exists(_old):
                try:
                    if os.path.exists(_new):
                        os.remove(_new)
                    os.rename(_old, _new)
                except Exception:
                    pass
        try:
            os.rename(_LOG_FILE, os.path.join(_LOG_DIR, 'trigger_daemon.log.1'))
        except Exception:
            pass

    class _TeeStream:
        """Write to both original stream and log file with timestamp."""
        def __init__(self, original, log_path):
            self._orig = original
            self._log_path = log_path

        def write(self, data):
            try:
                if self._orig:
                    self._orig.write(data)
            except Exception:
                pass
            try:
                if data.strip():
                    with open(self._log_path, 'a', encoding='utf-8') as f:
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        for line in data.rstrip('\n').split('\n'):
                            f.write(f"[{ts}] {line}\n")
            except Exception:
                pass

        def flush(self):
            try:
                if self._orig:
                    self._orig.flush()
            except Exception:
                pass

    sys.stdout = _TeeStream(sys.stdout, _LOG_FILE)
    sys.stderr = _TeeStream(sys.stderr, _LOG_FILE)
except Exception:
    pass

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Also add SEVEN_APP_PATH if set by Electron
_app_path = os.environ.get("SEVEN_APP_PATH", "")
if _app_path and _app_path not in sys.path:
    sys.path.insert(0, _app_path)
    PROJECT_ROOT = _app_path

APPDATA      = os.environ.get('APPDATA', os.path.expanduser('~'))
LOCK_FILE    = os.path.join(APPDATA, 'SEVEN', 'trigger_daemon.lock')

# ── DB path resolution ────────────────────────────────────────────────────
# Priority 1: Local seven_data (dev mode — has actual triggers)
# Priority 2: APPDATA seven_data (installed mode)
# We check which one has the triggers table populated.

LOCAL_SEVEN_DATA = os.path.join(PROJECT_ROOT, 'seven_data')
LOCAL_DB         = os.path.join(LOCAL_SEVEN_DATA, 'triggers.db')
APPDATA_SEVEN    = os.path.join(APPDATA, 'SEVEN', 'seven_data')
APPDATA_DB       = os.path.join(APPDATA_SEVEN, 'triggers.db')


def _resolve_db_path():
    """
    Find the correct triggers.db.
    Returns the path that actually has the triggers table with data.
    In dev mode: local seven_data always wins.
    In production: APPDATA wins.
    """
    def _has_triggers(db_path):
        if not os.path.exists(db_path):
            return False
        try:
            import sqlite3 as _sq
            c = _sq.connect(db_path, timeout=2)
            count = c.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name='triggers'"
            ).fetchone()[0]
            c.close()
            return count > 0
        except Exception:
            return False

    # Dev mode: local DB exists and has triggers table → use it
    if _has_triggers(LOCAL_DB):
        print(f"[TRIGGER DAEMON] Using LOCAL DB: {LOCAL_DB}")
        return LOCAL_DB, LOCAL_SEVEN_DATA

    # Production: APPDATA DB has triggers table → use it
    if _has_triggers(APPDATA_DB):
        print(f"[TRIGGER DAEMON] Using APPDATA DB: {APPDATA_DB}")
        return APPDATA_DB, APPDATA_SEVEN

    # Neither has triggers table yet — default to local in dev, APPDATA in prod
    if os.path.exists(LOCAL_SEVEN_DATA):
        print(f"[TRIGGER DAEMON] Defaulting to LOCAL (no triggers yet): {LOCAL_DB}")
        return LOCAL_DB, LOCAL_SEVEN_DATA

    print(f"[TRIGGER DAEMON] Defaulting to APPDATA: {APPDATA_DB}")
    return APPDATA_DB, APPDATA_SEVEN


TRIGGERS_DB, SEVEN_DATA = _resolve_db_path()
RELOAD_SIGNAL = os.path.join(SEVEN_DATA, 'trigger_reload.signal')


# ─────────────────────────────────────────────────────────────────────────
# SINGLE INSTANCE LOCK
# ─────────────────────────────────────────────────────────────────────────

def acquire_lock():
    """Prevent multiple daemon instances using Windows mutex."""
    try:
        import ctypes
        _mutex_name = "Global\\SevenTriggerDaemon_SingleInstance"
        _kernel32   = ctypes.windll.kernel32
        _mutex      = _kernel32.CreateMutexW(None, True, _mutex_name)
        _last_err   = _kernel32.GetLastError()

        if _last_err == 183:  # ERROR_ALREADY_EXISTS
            print("[TRIGGER DAEMON] Already running. Exiting.")
            if _mutex:
                _kernel32.CloseHandle(_mutex)
            return False

        if not _mutex:
            return True

        acquire_lock._mutex_handle = _mutex
        print(f"[TRIGGER DAEMON] Mutex acquired. PID: {os.getpid()}")

        try:
            os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
            with open(LOCK_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

        return True

    except Exception as _e:
        print(f"[TRIGGER DAEMON] Mutex failed: {_e}")
        return True

acquire_lock._mutex_handle = None


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# DATABASE ACCESS
# ─────────────────────────────────────────────────────────────────────────

def load_triggers():
    """Load all enabled triggers from DB."""
    if not os.path.exists(TRIGGERS_DB):
        return []
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT * FROM triggers WHERE enabled = 1"
        ).fetchall()
        conn.close()

        triggers = []
        for row in rows:
            d = dict(row)
            d["enabled"] = bool(d.get("enabled", 1))
            d["silent"]  = bool(d.get("silent", 0))
            try:
                d["action_data"] = json.loads(d.get("action_data") or "{}")
            except Exception:
                d["action_data"] = {}
            triggers.append(d)

        return triggers
    except Exception as e:
        print(f"[TRIGGER DAEMON] DB load error: {e}")
        return []


def update_fire_stats(trigger_id):
    """Increment fire count for a trigger."""
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE triggers SET fire_count = fire_count + 1, last_fired = ? WHERE id = ?",
            (datetime.now().isoformat(), trigger_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TRIGGER DAEMON] Stats update error: {e}")


# ─────────────────────────────────────────────────────────────────────────
# SEVEN STATUS CHECK
# ─────────────────────────────────────────────────────────────────────────

def is_seven_running():
    """Check if Seven main backend is running on port 7777."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:7777/api/status", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────
# OVERLAY DAEMON COMMUNICATION
# ─────────────────────────────────────────────────────────────────────────

def _send_overlay(msg: dict, timeout: float = 0.3) -> bool:
    """Send TCP message to overlay_daemon on port 7891."""
    try:
        import socket as _sock
        s = _sock.create_connection(("127.0.0.1", 7891), timeout=timeout)
        s.settimeout(timeout)
        s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
        s.close()
        if data:
            resp = json.loads(data.decode("utf-8").strip())
            return resp.get("ok", False)
        return False
    except Exception:
        return False


def _is_overlay_alive() -> bool:
    """Ping overlay_daemon."""
    return _send_overlay({"type": "ping"}, timeout=0.3)


def _get_windows_by_workspace_apps(workspace_apps: list) -> tuple:
    """
    Find window handles by matching workspace app definitions.
    Uses exe_path for accurate matching — no fuzzy name matching.

    Args:
        workspace_apps: list of dicts from workspace DB, each with
                        exe_path, name, type, etc.

    Returns:
        (triggered_windows, other_windows) — list of dicts with
        hwnd, title, exe, triggered.
    """
    try:
        import win32gui
        import win32process
        import psutil
        import os as _os

        _SKIP_TITLES_SET = {
            "", "program manager", "microsoft text input application",
            "windows input experience", "nvidia geforce overlay",
            "nvidia geforce overlay dt", "settings",
        }
        _SKIP_EXE_SET = {
            "searchhost.exe", "shellexperiencehost.exe",
            "startmenuexperiencehost.exe", "textinputhost.exe",
            "runtimebroker.exe", "applicationframehost.exe",
            "msedgewebview2.exe", "nvidia overlay.exe",
            "nvcontainer.exe", "nvidia share.exe",
            "widgets.exe", "widgetservice.exe",
            "lockapp.exe", "systemsettings.exe",
        }

        visible = []

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            title_stripped = title.lower().strip() if title else ""
            if not title:
                return
            if title_stripped in _SKIP_TITLES_SET:
                return
            if "nvidia" in title_stripped and "overlay" in title_stripped:
                return

            # Try to get exe — never drop the window if psutil fails
            exe_name = "unknown"
            full_exe = ""
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc = psutil.Process(pid)
                    try:
                        exe_name = proc.name()
                    except Exception:
                        pass
                    try:
                        full_exe = (proc.exe() or "").lower()
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                return

            if exe_name.lower() in _SKIP_EXE_SET:
                return
            if exe_name.lower() == "electron.exe":
                return

            visible.append({
                "hwnd":     hwnd,
                "title":    title,
                "exe":      exe_name,
                "full_exe": full_exe,
                "triggered": False,
            })

        win32gui.EnumWindows(_cb, None)
        all_titles = visible

        triggered = []
        used = set()

        for ws_app in workspace_apps:
            exe_path = (ws_app.get("exe_path") or "").lower()
            exe_basename = _os.path.basename(exe_path).lower() if exe_path else ""
            app_type = (ws_app.get("type") or "").lower()
            display_name = ws_app.get("name", "")
            ws_window = ws_app.get("window", {}) or {}
            expected_title = (ws_window.get("title") or "").lower()

            match = None

            # Priority 1: exact full path match
            if exe_path:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if w["full_exe"] == exe_path:
                        match = w
                        break

            # Priority 2: exe basename match (e.g. Taskmgr.exe)
            if not match and exe_basename:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if w["exe"].lower() == exe_basename:
                        match = w
                        break

            # Priority 2a: expected title exact match (for elevated where exe=unknown)
            if not match and expected_title:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if w["title"].lower() == expected_title:
                        match = w
                        break

            # Priority 2b: expected title substring match
            if not match and expected_title:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if expected_title in w["title"].lower() or \
                       w["title"].lower() in expected_title:
                        match = w
                        break

            # Priority 2b: elevated process fallback — match by exact window title
            # (Task Manager, elevated PowerShell etc. can't be read via psutil
            #  when Seven isn't elevated)
            if not match and expected_title:
                for t in all_titles:
                    if t["hwnd"] in used:
                        continue
                    if t["title"].lower() == expected_title:
                        match = {
                            "hwnd":  t["hwnd"],
                            "title": t["title"],
                            "exe":   exe_basename or "unknown",
                            "full_exe": "",
                            "triggered": False,
                        }
                        break

            # Priority 3: chrome profile match — score windows by tab title relevance
            if not match and app_type == "chrome":
                profile = (ws_app.get("profile_name") or "").lower()
                tabs = ws_app.get("tabs", []) or []
                tab_titles = [(t.get("title", "") or "").lower() for t in tabs]

                best = None
                best_score = 0
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if "chrome" not in w["exe"].lower():
                        continue
                    wtitle = w["title"].lower()
                    score = 0
                    if profile and profile in wtitle:
                        score += 10
                    for tt in tab_titles:
                        if tt and len(tt) > 6 and tt[:20] in wtitle:
                            score += 5
                            break
                    if score == 0:
                        score = 1
                    if score > best_score:
                        best_score = score
                        best = w
                if best:
                    match = best

            # Priority 4: explorer folder match by title
            if not match and app_type == "explorer":
                folder = _os.path.basename(ws_app.get("folder_path", "")).lower()
                if folder:
                    for w in visible:
                        if w["hwnd"] in used:
                            continue
                        if "explorer.exe" in w["exe"].lower() and folder in w["title"].lower():
                            match = w
                            break

            if match:
                m = dict(match)
                m["triggered"] = True
                m.pop("full_exe", None)
                triggered.append(m)
                used.add(match["hwnd"])

        other = []
        for w in visible:
            if w["hwnd"] in used:
                continue
            w2 = dict(w)
            w2.pop("full_exe", None)
            other.append(w2)

        return triggered, other

    except Exception as e:
        print(f"[TRIGGER DAEMON] Workspace-app enumeration failed: {e}")
        import traceback; traceback.print_exc()
        return [], []


def _get_windows_for_arrange(app_names: list) -> tuple:
    """
    Find window handles for triggered apps ONLY.
    Returns (triggered_windows, other_windows).

    STRICT MATCHING: only returns windows whose exe or title clearly
    matches an app name in app_names. Never returns unrelated windows
    as "triggered" — that would maximize the user's Task Manager etc.
    """
    try:
        import win32gui
        import win32process
        import psutil

        _SKIP_TITLES_SET = {
            "", "program manager", "microsoft text input application",
            "windows input experience", "nvidia geforce overlay",
            "nvidia geforce overlay dt", "settings",
        }
        _SKIP_EXE_SET = {
            "searchhost.exe", "shellexperiencehost.exe",
            "startmenuexperiencehost.exe", "textinputhost.exe",
            "runtimebroker.exe", "applicationframehost.exe",
            "msedgewebview2.exe", "nvidia overlay.exe",
            "nvcontainer.exe", "nvidia share.exe",
            "widgets.exe", "widgetservice.exe",
            "lockapp.exe", "systemsettings.exe",
        }

        visible = []
        _debug_counts = {"total": 0, "invisible": 0, "no_title": 0, "skipped_title": 0,
                         "too_small": 0, "skipped_exe": 0, "kept": 0, "electron": 0}

        def _cb(hwnd, _):
            _debug_counts["total"] += 1
            if not win32gui.IsWindowVisible(hwnd):
                _debug_counts["invisible"] += 1
                return
            title = win32gui.GetWindowText(hwnd)
            title_stripped = title.lower().strip() if title else ""
            if not title or title_stripped in _SKIP_TITLES_SET:
                return
            if "nvidia" in title_stripped and "overlay" in title_stripped:
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                exe = proc.name()
                if exe.lower() in _SKIP_EXE_SET:
                    return
                if exe.lower() == "electron.exe":
                    return
                # Skip zero-size / off-screen windows
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if w < 100 or h < 100:
                        return
                except Exception:
                    pass
                visible.append({"hwnd": hwnd, "title": title,
                                 "exe": exe, "triggered": False})
            except Exception:
                pass

        win32gui.EnumWindows(_cb, None)

        # STRICT matching — only exact or clear substring match
        triggered = []
        used = set()

        for app_name in app_names:
            if not app_name:
                continue
            name_low = app_name.lower().strip()
            name_key = name_low.replace(".exe", "").replace(" ", "")

            best = None
            best_score = 0
            for w in visible:
                if w["hwnd"] in used:
                    continue
                title_low = w["title"].lower()
                exe_low = w["exe"].lower().replace(".exe", "")

                score = 0
                # Exe name matches app name closely
                if exe_low == name_key or exe_low.startswith(name_key) \
                        or name_key.startswith(exe_low):
                    score = 5
                # App name found as whole word in title
                elif name_low in title_low:
                    score = 4
                # Exe name found in title (e.g. "chrome" in "GitHub - Chrome")
                elif exe_low in title_low and len(exe_low) >= 4:
                    score = 3

                if score > best_score:
                    best_score = score
                    best = w

            # Require MINIMUM score of 3 — no weak matches
            if best and best_score >= 3:
                best = dict(best)
                best["triggered"] = True
                triggered.append(best)
                used.add(best["hwnd"])
                print(f"[TRIGGER DAEMON] Matched '{app_name}' -> "
                      f"'{best['title']}' (score={best_score})")
            else:
                print(f"[TRIGGER DAEMON] No match for '{app_name}'")

        other = [w for w in visible if w["hwnd"] not in used]
        return triggered, other

    except Exception as e:
        print(f"[TRIGGER DAEMON] Window enumeration failed: {e}")
        import traceback; traceback.print_exc()
        return [], []


# ─────────────────────────────────────────────────────────────────────────
# TRIGGER EXECUTION
# ─────────────────────────────────────────────────────────────────────────

def execute_trigger(trigger):
    """
    Execute a trigger action.
    Shows notification INSTANTLY, then runs action in background.
    For workspace triggers: shows arrangement card after apps open.
    """
    action_type = trigger.get("action_type", "")
    action_data = trigger.get("action_data", {})
    name        = trigger.get("name", "unnamed")

    print(f"[TRIGGER DAEMON] Firing: {name} (type={action_type})")

    # ── Collect metadata for notification ──
    app_count  = 0
    tab_count  = 0
    app_names  = ""

    workspace_apps = []

    if action_type == "open_workspace":
        ws_id   = action_data.get("workspace_id")
        ws_name = action_data.get("workspace_name")
        try:
            conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            if ws_id:
                ws_row = conn.execute(
                    "SELECT apps FROM workspaces WHERE id = ?", (ws_id,)
                ).fetchone()
            elif ws_name:
                ws_row = conn.execute(
                    "SELECT apps FROM workspaces WHERE LOWER(name) = ?",
                    (ws_name.lower(),)
                ).fetchone()
            else:
                ws_row = None
            conn.close()

            if ws_row:
                workspace_apps = json.loads(ws_row["apps"] or "[]")
                app_count  = len(workspace_apps)
                names_list = []
                for a in workspace_apps:
                    n = a.get("name", "")
                    if " - " in n:
                        n = n.split(" - ")[-1].strip()
                    names_list.append(n)
                    tab_count += len(a.get("tabs", []))
                app_names = ",".join(names_list)
        except Exception as we:
            print(f"[TRIGGER DAEMON] Workspace lookup: {we}")

    elif action_type == "open_app":
        apps_list  = action_data.get("apps", [])
        single     = action_data.get("app", "")
        if single and not apps_list:
            apps_list = [single]
        app_count  = len(apps_list)
        app_names  = ",".join(apps_list)
        workspace_apps = [{"name": a, "exe_path": ""} for a in apps_list]

    threading.Thread(
        target=_execute_trigger_complete,
        args=(trigger, name, action_type, action_data,
              app_count, tab_count, app_names, workspace_apps),
        daemon=True,
    ).start()


def _execute_trigger_complete(trigger, name, action_type, action_data,
                               app_count, tab_count, app_names,
                               workspace_apps=None):
    """
    Complete trigger execution in a single thread.
    Notification → Action → Arrangement → Stats.
    No concurrent threads to prevent double-execution.
    """
    workspace_apps = workspace_apps or []
    # Step 1: Ensure overlay is ready
    _ensure_overlay_alive_safe()

    # Step 2: Show notification
    if not trigger.get("silent", False):
        _fire_notification(name, action_type, app_count, tab_count, app_names)

    # Step 3: Execute action
    result = None
    try:
        if action_type == "open_app":
            _exec_open_app(action_data)
        elif action_type == "open_url":
            _exec_open_url(action_data)
        elif action_type == "open_file":
            _exec_open_file(action_data)
        elif action_type == "open_folder":
            _exec_open_folder(action_data)
        elif action_type == "open_workspace":
            result = _exec_open_workspace(action_data)
        elif action_type == "run_command":
            _exec_run_command(action_data)
        elif action_type == "seven_action":
            _exec_seven_action(action_data)
        else:
            print(f"[TRIGGER DAEMON] Unknown action: {action_type}")
            return
    except Exception as e:
        print(f"[TRIGGER DAEMON] Action error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Sound
    if not trigger.get("silent", False):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    # Step 5: Feedback + arrangement card
    if action_type == "open_workspace" and result and not trigger.get("silent", False):
        opened  = result.get("opened", 0)
        skipped = result.get("skipped", 0)

        if opened == 0 and skipped > 0:
            _send_overlay({
                "type": "notif",
                "data": {
                    "title":    name,
                    "subtitle": "Already active",
                    "detail":   f"All {skipped} app{'s' if skipped != 1 else ''} already open",
                    "holdMs":   2500,
                },
            })
            time.sleep(0.8)
            _fire_arrangement_card(workspace_apps)

        elif opened > 0 and skipped > 0:
            _send_overlay({
                "type": "notif",
                "data": {
                    "title":    name,
                    "subtitle": "Workspace restored",
                    "detail":   f"{opened} opened · {skipped} already running",
                    "holdMs":   2200,
                },
            })
            time.sleep(1.5)
            _fire_arrangement_card(workspace_apps)

        elif opened > 0:
            time.sleep(1.8)
            _fire_arrangement_card(workspace_apps)

    elif action_type == "open_app" and not trigger.get("silent", False):
        if len(workspace_apps) >= 2:
            time.sleep(1.5)
            _fire_arrangement_card(workspace_apps)

    # Step 6: Update fire stats
    update_fire_stats(trigger.get("id"))


def _fire_arrangement_card(workspace_apps):
    """Send arrangement card using exe_path matching (accurate)."""
    if not workspace_apps:
        return
    if not _is_overlay_alive():
        print("[TRIGGER DAEMON] Overlay not alive — skipping arrangement card")
        return

    triggered_wins, other_wins = _get_windows_by_workspace_apps(workspace_apps)
    print(f"[TRIGGER DAEMON] Arrangement: {len(triggered_wins)} triggered, "
          f"{len(other_wins)} other")
    if triggered_wins:
        _send_overlay({
            "type": "arrange",
            "data": {
                "windows":    triggered_wins,
                "allWindows": other_wins,
            },
        })
    else:
        print("[TRIGGER DAEMON] No triggered windows found — no arrangement card")


def _ensure_overlay_alive() -> bool:
    """
    Check overlay daemon is running. If not, spawn it.
    Overlay daemon is owned by trigger_daemon_launcher at startup,
    but if it crashed we recover here.
    """
    if _is_overlay_alive():
        return True

    print("[TRIGGER DAEMON] Overlay daemon not responding — attempting spawn...")

    try:
        # Find Electron
        # Find Electron — check multiple roots since cwd may differ
        _roots_to_check = [
            PROJECT_ROOT,
            os.getcwd(),
            os.path.dirname(PROJECT_ROOT),
        ]
        # Remove duplicates while preserving order
        _checked_roots = []
        for _r in _roots_to_check:
            if _r not in _checked_roots:
                _checked_roots.append(_r)

        electron_exe = None
        for _rel in [
            os.path.join("node_modules", "electron", "dist", "electron.exe"),
            os.path.join("node_modules", ".bin", "electron.cmd"),
            os.path.join("frontend", "node_modules", "electron", "dist", "electron.exe"),
        ]:
            _c = os.path.join(PROJECT_ROOT, _rel)
            if os.path.exists(_c):
                electron_exe = _c
                break

        if not electron_exe:
            print(f"[TRIGGER DAEMON] Electron not found in {PROJECT_ROOT}")
            return False

        daemon_js = os.path.join(PROJECT_ROOT, "electron", "overlay_daemon.js")
        if not os.path.exists(daemon_js):
            print(f"[TRIGGER DAEMON] overlay_daemon.js not found: {daemon_js}")
            return False

        print(f"[TRIGGER DAEMON] Overlay: {electron_exe}")
    
        subprocess.Popen(
            [electron_exe, daemon_js],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008 | 0x00000200,
            close_fds=True,
            start_new_session=True,
        )

        # Wait up to 4 seconds for daemon to be ready
        for _ in range(40):
            time.sleep(0.1)
            if _is_overlay_alive():
                print("[TRIGGER DAEMON] Overlay daemon recovered")
                return True

        print("[TRIGGER DAEMON] Overlay daemon spawn timed out")
        return False

    except Exception as e:
        print(f"[TRIGGER DAEMON] Overlay spawn error: {e}")
        return False


# Single lock — only one thread spawns overlay at a time
_overlay_spawn_lock = threading.Lock()


def _ensure_overlay_alive_safe() -> bool:
    """
    Ensure overlay daemon is running on port 7891.
    Thread-safe — only one spawn attempt at a time.
    Auto-recovers if daemon crashed.
    """
    if _is_overlay_alive():
        return True

    if not _overlay_spawn_lock.acquire(blocking=True, timeout=8):
        return False

    try:
        if _is_overlay_alive():
            return True

        print("[TRIGGER DAEMON] Overlay daemon down — spawning...")

        # Use PROJECT_ROOT only — it's set from __file__ at module load
        # so it's always correct regardless of cwd
        _search_roots = [PROJECT_ROOT]

        electron_exe = None
        for _root in _search_roots:
            for _rel in [
                os.path.join("node_modules", "electron", "dist", "electron.exe"),
                os.path.join("node_modules", ".bin", "electron.cmd"),
                os.path.join("frontend", "node_modules", "electron", "dist", "electron.exe"),
            ]:
                _c = os.path.join(_root, _rel)
                if os.path.exists(_c):
                    electron_exe = _c
                    print(f"[TRIGGER DAEMON] Electron found: {_c}")
                    break
            if electron_exe:
                break

        if not electron_exe:
            print(f"[TRIGGER DAEMON] Electron not found in {PROJECT_ROOT}")
            print(f"[TRIGGER DAEMON] Searched: node_modules/electron/dist/electron.exe")
            return False

        daemon_js = os.path.join(PROJECT_ROOT, "electron", "overlay_daemon.js")
        if not os.path.exists(daemon_js):
            print(f"[TRIGGER DAEMON] overlay_daemon.js not found: {daemon_js}")
            return False

        print(f"[TRIGGER DAEMON] Spawning overlay: {electron_exe}")

        subprocess.Popen(
            [electron_exe, daemon_js],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008 | 0x00000200,
            close_fds=True,
            start_new_session=True,
        )

        for _ in range(150):
            time.sleep(0.1)
            if _is_overlay_alive():
                print("[TRIGGER DAEMON] Overlay daemon ready")
                return True

        print("[TRIGGER DAEMON] Overlay spawn timed out after 15s")
        return False

    finally:
        _overlay_spawn_lock.release()


def _fire_notification(name, action_type, app_count, tab_count, app_names):
    """Send notification to overlay_daemon. Auto-recovers if daemon crashed."""
    subtitle_map = {
        "open_app":       "App launched",
        "open_url":       "URL opened",
        "open_workspace": "Workspace restored",
        "open_file":      "File opened",
        "open_folder":    "Folder opened",
        "run_command":    "Command executed",
        "seven_action":   "Action completed",
    }
    subtitle = subtitle_map.get(action_type, "Trigger fired")

    parts = []
    if app_count > 0:
        parts.append(f"{app_count} app{'s' if app_count != 1 else ''}")
    if tab_count > 0:
        parts.append(f"{tab_count} tab{'s' if tab_count != 1 else ''}")
    detail  = "  ·  ".join(parts) if parts else ""
    hold_ms = 2000 if action_type == "open_workspace" else 3200

    _send_overlay({
        "type": "notif",
        "data": {
            "title":    name,
            "subtitle": subtitle,
            "detail":   detail,
            "holdMs":   hold_ms,
        },
    })


def _exec_open_app(data):
    """Launch application(s). Supports single or multiple apps."""
    apps_list  = data.get("apps", [])
    single_app = data.get("app", "")
    if single_app and not apps_list:
        apps_list = [single_app]

    if not apps_list:
        print("[TRIGGER DAEMON] No app specified")
        return

    for app_name in apps_list:
        if not app_name:
            continue

        # Method 1: hands.core.open_app
        try:
            from hands.core import open_app
            open_app(app_name)
            print(f"[TRIGGER DAEMON] Opened: {app_name}")
            continue
        except Exception as e:
            print(f"[TRIGGER DAEMON] hands.core failed for {app_name}: {e}")

        # Method 2: AppOpener
        try:
            import AppOpener
            AppOpener.open(app_name)
            print(f"[TRIGGER DAEMON] Opened via AppOpener: {app_name}")
            continue
        except Exception as e:
            print(f"[TRIGGER DAEMON] AppOpener failed for {app_name}: {e}")

        # Method 3: shell start
        try:
            subprocess.Popen(f'start {app_name}', shell=True)
            print(f"[TRIGGER DAEMON] Opened via start: {app_name}")
        except Exception as e:
            print(f"[TRIGGER DAEMON] start command failed for {app_name}: {e}")


def _exec_open_url(data):
    """Open URL(s) in default browser."""
    import webbrowser
    urls   = data.get("urls", [])
    single = data.get("url", "")
    if single and not urls:
        urls = [single]
    for url in urls:
        if url:
            webbrowser.open(url)
            print(f"[TRIGGER DAEMON] Opened URL: {url}")


def _exec_open_file(data):
    """Open file(s) with default application."""
    paths  = data.get("paths", [])
    single = data.get("path", "")
    if single and not paths:
        paths = [single]
    for path in paths:
        if path and os.path.exists(path):
            os.startfile(path)
            print(f"[TRIGGER DAEMON] Opened file: {path}")


def _exec_open_folder(data):
    """Open folder(s) in Explorer."""
    paths  = data.get("paths", [])
    single = data.get("path", "")
    if single and not paths:
        paths = [single]
    for path in paths:
        if path and os.path.exists(path):
            subprocess.Popen(['explorer', path])
            print(f"[TRIGGER DAEMON] Opened folder: {path}")


def _exec_open_workspace(data):
    """
    Restore a workspace by ID or name using smart_restore.
    Returns {"opened": N, "skipped": N} for caller to show feedback.
    """
    workspace_id   = data.get("workspace_id")
    workspace_name = data.get("workspace_name")

    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        if workspace_id:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
        elif workspace_name:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE LOWER(name) = ?",
                (workspace_name.lower(),)
            ).fetchone()
        else:
            conn.close()
            print("[TRIGGER DAEMON] No workspace ID or name provided")
            return {"opened": 0, "skipped": 0}

        conn.close()

        if not row:
            print(f"[TRIGGER DAEMON] Workspace not found: "
                  f"id={workspace_id} name={workspace_name}")
            return {"opened": 0, "skipped": 0}

        workspace = dict(row)
        try:
            apps = json.loads(workspace.get("apps") or "[]")
        except Exception:
            apps = []

        if not apps:
            print("[TRIGGER DAEMON] Workspace has no apps")
            return {"opened": 0, "skipped": 0}

        from hands.workspace import smart_restore
        opened, skipped = smart_restore(apps)
        print(f"[TRIGGER DAEMON] Smart restore: "
              f"{opened} opened, {skipped} already running")

        if is_seven_running() and workspace_id:
            try:
                import requests
                requests.post(
                    f"http://127.0.0.1:7777/api/workspaces/{workspace_id}/restore"
                    f"?stats_only=true",
                    timeout=2,
                )
            except Exception:
                pass

        print(f"[TRIGGER DAEMON] Workspace done: "
              f"{workspace.get('name')} ({len(apps)} apps)")

        return {"opened": opened, "skipped": skipped}

    except Exception as e:
        print(f"[TRIGGER DAEMON] Workspace restore error: {e}")
        import traceback
        traceback.print_exc()
        return {"opened": 0, "skipped": 0}


def _exec_run_command(data):
    """Execute a shell command."""
    cmd = data.get("command", "")
    if cmd:
        subprocess.Popen(cmd, shell=True)

def _set_brightness_direct(level: int):
    """Set screen brightness on laptop via WMI."""
    level = max(0, min(100, level))
    try:
        from hands.system import manage_system
        manage_system({"action": "brightness_set", "value": str(level)})
    except Exception as e:
        print(f"[TRIGGER DAEMON] Brightness failed: {e}")

def _exec_seven_action(data):
    """
    Execute internal Seven action.

    Priority:
      1. Direct deterministic system actions first
         (brightness, volume, mute)
      2. API/chat fallback only for unknown actions
    """
    action = data.get("action", "")
    if not action:
        return

    action_lower = action.lower().strip()

    try:
        import re
        from hands.system import manage_system

        # ── DIRECT SYSTEM ACTIONS FIRST ───────────────────────────────

        # Mute / unmute
        if "mute" in action_lower and "unmute" not in action_lower:
            result = manage_system({"action": "volume_mute"})
            print(f"[TRIGGER DAEMON] Mute direct: {result}")
            return

        # Volume set
        if "volume" in action_lower:
            nums = re.findall(r'\d+', action_lower)
            if nums:
                result = manage_system({"action": "volume_set", "value": nums[0]})
                print(f"[TRIGGER DAEMON] Volume {nums[0]}% direct: {result}")
                return
            if "max" in action_lower or "full" in action_lower:
                result = manage_system({"action": "volume_set", "value": "100"})
                print(f"[TRIGGER DAEMON] Volume 100% direct: {result}")
                return
            if "min" in action_lower or "low" in action_lower:
                result = manage_system({"action": "volume_set", "value": "10"})
                print(f"[TRIGGER DAEMON] Volume 10% direct: {result}")
                return

        # Brightness set
        if "brightness" in action_lower or "bright" in action_lower or "dim" in action_lower:
            nums = re.findall(r'\d+', action_lower)
            if nums:
                val = nums[0]
            elif "max" in action_lower or "full" in action_lower or "high" in action_lower:
                val = "100"
            elif "min" in action_lower or "low" in action_lower or "dim" in action_lower:
                val = "10"
            else:
                val = "100"

            result = manage_system({"action": "brightness_set", "value": val})
            print(f"[TRIGGER DAEMON] Brightness {val}% direct: {result}")
            return

    except Exception as e:
        print(f"[TRIGGER DAEMON] Direct system action failed: {e}")
        import traceback
        traceback.print_exc()

    # ── FALLBACK: SEND TO SEVEN CHAT API ─────────────────────────────
    if is_seven_running():
        try:
            import requests
            requests.post(
                "http://127.0.0.1:7777/api/chat",
                json={"text": action, "speaker_id": "default"},
                timeout=10
            )
            print(f"[TRIGGER DAEMON] Seven action via API fallback: {action}")
            return
        except Exception as e:
            print(f"[TRIGGER DAEMON] API fallback failed: {e}")

    print(f"[TRIGGER DAEMON] No direct handler and Seven not running: {action}")


# ─────────────────────────────────────────────────────────────────────────
# HOTKEY LISTENER
# ─────────────────────────────────────────────────────────────────────────

class HotkeyListener:
    """
    Global hotkey listener.
    Primary: pynput low-level keyboard hook (works everywhere).
    RegisterHotKey API was removed — it conflicts with Electron's
    globalShortcut and fails for special character combos like Shift+!.
    """

    def __init__(self):
        self._triggers        = []
        self._hotkey_map      = {}
        self._pressed_keys    = set()
        self._listener        = None
        self._running         = False
        self._last_fire       = 0
        self._mod_reset_timer = None

    def reload(self, triggers):
        self._triggers   = triggers
        self._hotkey_map = {}
        for t in triggers:
            hk = t.get("hotkey")
            if hk:
                normalized = _normalize_hotkey(hk)
                self._hotkey_map[normalized] = t
                print(f"[HOTKEY] Mapped: '{hk}' -> '{normalized}' "
                      f"-> '{t.get('name')}'")
        print(f"[HOTKEY] {len(self._hotkey_map)} hotkeys active")

    def start(self):
        if self._running:
            return
        self._running = True

        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    name = self._key_name(key)
                    if not name:
                        return
                    self._pressed_keys.add(name)
                    self._check_combo()
                    self._schedule_reset()
                except Exception:
                    pass

            def on_release(key):
                try:
                    name = self._key_name(key)
                    if name:
                        self._pressed_keys.discard(name)
                except Exception:
                    pass

            self._listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
                suppress=False,
            )
            self._listener.daemon = True
            self._listener.start()
            print("[HOTKEY] Listener started")

        except ImportError:
            print("[HOTKEY] pynput not installed — hotkeys disabled")
        except Exception as e:
            print(f"[HOTKEY] Start failed: {e}")

    def stop(self):
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _key_name(self, key):
        """Convert any pynput key to a normalized string name."""
        from pynput import keyboard as kb

        # Named special keys
        if isinstance(key, kb.Key):
            _map = {
                kb.Key.ctrl_l: "ctrl", kb.Key.ctrl_r: "ctrl",
                kb.Key.shift_l: "shift", kb.Key.shift_r: "shift",
                kb.Key.alt_l: "alt", kb.Key.alt_r: "alt",
                kb.Key.alt_gr: "alt",
                kb.Key.cmd: "win", kb.Key.cmd_l: "win", kb.Key.cmd_r: "win",
                kb.Key.space: "space", kb.Key.enter: "enter",
                kb.Key.tab: "tab", kb.Key.esc: "esc",
                kb.Key.backspace: "backspace", kb.Key.delete: "delete",
                kb.Key.home: "home", kb.Key.end: "end",
                kb.Key.page_up: "pageup", kb.Key.page_down: "pagedown",
                kb.Key.up: "up", kb.Key.down: "down",
                kb.Key.left: "left", kb.Key.right: "right",
                kb.Key.insert: "insert", kb.Key.menu: "menu",
                kb.Key.caps_lock: "capslock", kb.Key.num_lock: "numlock",
            }
            for i in range(1, 25):
                fk = getattr(kb.Key, f"f{i}", None)
                if fk:
                    _map[fk] = f"f{i}"
            return _map.get(key)

        # Virtual key code — most reliable when modifiers are held
        vk = getattr(key, 'vk', None)
        if vk is not None:
            # Letters A-Z
            if 65 <= vk <= 90:
                return chr(vk).lower()
            # Numbers 0-9 (top row)
            if 48 <= vk <= 57:
                return str(vk - 48)
            # Numpad 0-9
            if 96 <= vk <= 105:
                return f"num{vk - 96}"
            # Symbols by VK code
            _sym = {
                186: ";", 187: "=", 188: ",", 189: "-", 190: ".",
                191: "/", 192: "`", 219: "[", 220: "\\",
                221: "]", 222: "'",
            }
            if vk in _sym:
                return _sym[vk]

        # Character fallback — handles Shift+1 = '!' etc.
        ch = getattr(key, 'char', None)
        if ch and isinstance(ch, str) and len(ch) == 1 and ch.isprintable():
            return ch.lower()

        return None

    def _check_combo(self):
        """Check if currently pressed keys match any registered hotkey."""
        now = time.time()
        if now - self._last_fire < 0.3:
            return

        MODIFIERS = {"ctrl", "shift", "alt", "win"}
        mods = sorted(k for k in self._pressed_keys if k in MODIFIERS)
        keys = sorted(k for k in self._pressed_keys if k not in MODIFIERS)

        raw_combo = "+".join(mods + keys)
        if not raw_combo:
            return

        combo = _normalize_hotkey(raw_combo)
        trigger = self._hotkey_map.get(combo)

        if trigger:
            self._last_fire = now
            self._pressed_keys.clear()
            print(f"[HOTKEY] FIRED: {combo} -> {trigger['name']}")
            threading.Thread(
                target=execute_trigger,
                args=(trigger,),
                daemon=True,
            ).start()

    def _schedule_reset(self):
        """Clear pressed keys after 3s inactivity — prevents stuck state."""
        if self._mod_reset_timer:
            self._mod_reset_timer.cancel()
        self._mod_reset_timer = threading.Timer(3.0, self._reset_keys)
        self._mod_reset_timer.daemon = True
        self._mod_reset_timer.start()

    def _reset_keys(self):
        if self._pressed_keys:
            self._pressed_keys.clear()


# ─────────────────────────────────────────────────────────────────────────
# AUDIO LISTENER
# ─────────────────────────────────────────────────────────────────────────

class AudioListener:
    """
    Listens for snap/clap patterns using DSP or YAMNet.
    Only active if audio triggers are configured.
    """

    def __init__(self):
        self._detector  = None
        self._triggers  = []
        self._audio_map = {}
        self._running   = False

    def reload(self, triggers):
        self._triggers  = triggers
        self._audio_map = {}
        for t in triggers:
            pattern = t.get("audio_pattern")
            if pattern:
                self._audio_map[pattern] = t
        print(f"[AUDIO] Loaded {len(self._audio_map)} audio triggers")

    def start(self):
        if not self._audio_map:
            print("[AUDIO] No audio triggers configured — skipping")
            return

        self._running = True

        try:
            from ears.audio_triggers import TriggerDetector
            self._detector = TriggerDetector(sensitivity="high")
            self._detector.on_pattern = self._on_pattern
            self._detector.start()
            print("[AUDIO] Listener started (DSP mode)")
        except Exception as e:
            print(f"[AUDIO] Listener failed: {e}")

    def stop(self):
        self._running = False
        if self._detector:
            self._detector.stop()

    def suppress(self, ms=3000):
        if self._detector:
            self._detector.suppress(ms)

    def _on_pattern(self, count):
        pattern_key = f"{count}_tap"
        trigger = self._audio_map.get(pattern_key)
        if trigger:
            print(f"[AUDIO] Pattern {pattern_key} -> {trigger['name']}")
            threading.Thread(
                target=execute_trigger,
                args=(trigger,),
                daemon=True
            ).start()
        else:
            print(f"[AUDIO] Pattern {pattern_key} — no trigger assigned")


# ─────────────────────────────────────────────────────────────────────────
# DB RELOAD POLLER
# ─────────────────────────────────────────────────────────────────────────

class ReloadPoller:
    """Watches for trigger_reload.signal file to refresh triggers."""

    def __init__(self, on_reload):
        self._on_reload = on_reload
        self._running   = False
        self._thread    = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        print("[RELOAD] DB change poller started")

    def stop(self):
        self._running = False

    def _poll(self):
        while self._running:
            try:
                if os.path.exists(RELOAD_SIGNAL):
                    os.remove(RELOAD_SIGNAL)
                    print("[RELOAD] Signal detected — reloading triggers")
                    self._on_reload()
            except Exception:
                pass
            time.sleep(2)


# ─────────────────────────────────────────────────────────────────────────
# HOTKEY NORMALIZATION (shared between listener + conflict check)
# ─────────────────────────────────────────────────────────────────────────

# Shift+number produces these symbols — map them back to the number
_SHIFT_SYMBOLS = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "~": "`", "{": "[", "}": "]",
    "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".",
    "?": "/",
}


def _normalize_hotkey(hotkey: str) -> str:
    """
    Normalize hotkey string for consistent comparison.

    Handles:
      - Modifier order: 'Ctrl+Shift+F' == 'shift+ctrl+f' → 'ctrl+shift+f'
      - Shift symbols: 'Shift+!' → 'shift+1' (because keyboard sends VK for '1')
      - Case insensitive
    """
    MODIFIERS = {"ctrl", "shift", "alt", "win"}
    parts = [p.strip().lower() for p in hotkey.replace(" ", "").split("+") if p.strip()]

    mods = sorted(p for p in parts if p in MODIFIERS)
    keys = []
    for p in parts:
        if p in MODIFIERS:
            continue
        # If it's a shift-produced symbol, convert to the base key
        if p in _SHIFT_SYMBOLS:
            keys.append(_SHIFT_SYMBOLS[p])
            # Ensure shift is in modifiers since the symbol implies it
            if "shift" not in mods:
                mods.append("shift")
                mods.sort()
        else:
            keys.append(p)

    keys.sort()
    return "+".join(mods + keys)


# ─────────────────────────────────────────────────────────────────────────
# MAIN DAEMON LOOP
# ─────────────────────────────────────────────────────────────────────────

def main():
    if not acquire_lock():
        return

    print("[TRIGGER DAEMON] Starting...")
    print(f"[TRIGGER DAEMON] DB: {TRIGGERS_DB}")
    print(f"[TRIGGER DAEMON] PID: {os.getpid()}")

    # Load initial triggers
    triggers = load_triggers()
    print(f"[TRIGGER DAEMON] Loaded {len(triggers)} active triggers")

    # Initialize listeners
    hotkey_listener = HotkeyListener()
    audio_listener  = AudioListener()

    def reload_all():
        nonlocal triggers
        triggers = load_triggers()
        hotkey_listener.reload(triggers)
        audio_listener.reload(triggers)
        print(f"[TRIGGER DAEMON] Reloaded: {len(triggers)} triggers")

    reload_poller = ReloadPoller(on_reload=reload_all)

    # Load into listeners
    hotkey_listener.reload(triggers)
    audio_listener.reload(triggers)

    # Pre-warm overlay daemon at startup
    threading.Thread(target=_ensure_overlay_alive_safe, daemon=True).start()

    # Pre-load heavy modules so first trigger fires instantly
    def _preload():
        try:
            import hands.workspace
            import hands.system
            import hands.core
            print("[TRIGGER DAEMON] Modules pre-loaded")
        except Exception:
            pass
    threading.Thread(target=_preload, daemon=True).start()

    # Start all listeners
    hotkey_listener.start()
    audio_listener.start()
    reload_poller.start()

    print("[TRIGGER DAEMON] All listeners active. Waiting for triggers...")

    _last_health_log = time.time()
    try:
        while True:
            time.sleep(30)

            # Overlay health check
            if not _is_overlay_alive():
                print("[TRIGGER DAEMON] Overlay daemon down — respawning...")
                threading.Thread(
                    target=_ensure_overlay_alive_safe,
                    daemon=True
                ).start()

            # Self health check — verify hotkey listener alive
            if hotkey_listener._listener is None or not hotkey_listener._listener.running:
                print("[TRIGGER DAEMON] Hotkey listener dead — restarting listener")
                try:
                    hotkey_listener.stop()
                    time.sleep(0.5)
                    hotkey_listener.start()
                    hotkey_listener.reload(triggers)
                except Exception as _re:
                    print(f"[TRIGGER DAEMON] Listener restart failed: {_re}")
                    print("[TRIGGER DAEMON] Exiting for Task Scheduler restart")
                    sys.exit(1)

            # Heartbeat log every 30 minutes so users know daemon is alive
            if time.time() - _last_health_log > 1800:
                print(f"[TRIGGER DAEMON] Heartbeat OK. "
                      f"Hotkeys: {len(hotkey_listener._hotkey_map)}, "
                      f"Overlay: {'up' if _is_overlay_alive() else 'down'}")
                _last_health_log = time.time()

    except KeyboardInterrupt:
        print("[TRIGGER DAEMON] Stopping...")
        hotkey_listener.stop()
        audio_listener.stop()
        reload_poller.stop()
        release_lock()
        print("[TRIGGER DAEMON] Stopped.")


# ─────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[TRIGGER DAEMON] Interrupted by user")
    except Exception as _crash:
        # Log crash and exit with error code so Task Scheduler restarts us
        import traceback
        print(f"[TRIGGER DAEMON] FATAL CRASH: {_crash}")
        traceback.print_exc()
        try:
            release_lock()
        except Exception:
            pass
        sys.exit(1)
    finally:
        release_lock()