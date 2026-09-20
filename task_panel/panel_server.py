"""
PROJECT SEVEN - task_panel/panel_server.py
Lightweight FastAPI server for the Task Panel.
Port: 7778
Runs independently — does not need Seven to be running.
Reads/writes tasks.db directly via SQLite WAL mode.
"""

import sqlite3
import os
import sys
import json
import subprocess
import webbrowser
from datetime import datetime, date

# Add project root to path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ─────────────────────────────────────────────────────────────────────────
# ROTATING LOG FILE FOR PANEL SERVER (DEBUG ANYWHERE)
# ─────────────────────────────────────────────────────────────────────────
_LOG_DIR = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'SEVEN', 'logs'
)
try:
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, 'panel_server.log')
    # Rotate if log exceeds 2MB
    if os.path.exists(_LOG_FILE) and os.path.getsize(_LOG_FILE) > 2 * 1024 * 1024:
        try:
            os.rename(_LOG_FILE, os.path.join(_LOG_DIR, 'panel_server.log.old'))
        except Exception:
            pass
    class _TeeStream:
        def __init__(self, original, log_path):
            self._orig = original
            self._log_path = log_path

        def write(self, data):
            if self._orig:
                try:
                    self._orig.write(data)
                except Exception:
                    pass
            if data and data.strip():
                try:
                    with open(self._log_path, 'a', encoding='utf-8') as f:
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        for line in data.rstrip('\n').split('\n'):
                            f.write(f"[{ts}] {line}\n")
                except Exception:
                    pass

        def flush(self):
            if self._orig:
                try:
                    self._orig.flush()
                except Exception:
                    pass

        def isatty(self):
            if hasattr(self._orig, 'isatty'):
                try:
                    return self._orig.isatty()
                except Exception:
                    return False
            return False

        def fileno(self):
            if hasattr(self._orig, 'fileno'):
                try:
                    return self._orig.fileno()
                except Exception:
                    return 1
            return 1

        def readable(self):
            return False

        def writable(self):
            return True

        def seekable(self):
            return False

        def __getattr__(self, name):
            return getattr(self._orig, name)

    sys.stdout = _TeeStream(sys.stdout, _LOG_FILE)
    sys.stderr = _TeeStream(sys.stderr, _LOG_FILE)
    print(f"\n[PANEL SERVER START] Logging active at: {_LOG_FILE}")
except Exception as e:
    print(f"Failed to setup logging: {e}")

# ── DB Path ──────────────────────────────────────────────────────────────────

def _get_seven_data():
    try:
        from seven_paths import paths
        return paths._seven_data
    except Exception as e:
        _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(_appdata, "SEVEN", "seven_data")

SEVEN_DATA_DIR = _get_seven_data()
RELOAD_SIGNAL = os.path.join(SEVEN_DATA_DIR, "trigger_reload.signal")

def _get_tasks_db():
    db_path = os.path.join(SEVEN_DATA_DIR, "tasks.db")
    print(f"[PANEL DB] Loaded tasks.db: {db_path}")
    return db_path

TASKS_DB = _get_tasks_db()

# ── Panel trigger file — daemon writes this to auto-show panel ────────────────
PANEL_TRIGGER = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "SEVEN", "panel_trigger.json"
)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Seven Panel API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class FrontendLog(BaseModel):
    level: str
    message: str

@app.post("/panel/log")
def log_frontend(body: FrontendLog):
    """Bridges UI logs directly into panel_server.log"""
    print(f"[UI_{body.level.upper()}] {body.message}")
    return {"status": "ok"}

@app.get("/panel/debug/logs")
def get_debug_logs():
    """Allows UI to pull and display backend logs directly"""
    try:
        log_path = os.path.join(_LOG_DIR, 'panel_server.log')
        if not os.path.exists(log_path):
            return {"logs": "No log file found."}
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return {"logs": "".join(lines[-100:])}  # return last 100 lines
    except Exception as e:
        return {"logs": f"Error reading logs: {str(e)}"}
# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    conn = sqlite3.connect(TASKS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _row(row) -> dict:
    d = dict(row)
    d["completed"] = bool(d.get("completed", 0))
    raw = d.get("subtasks", "[]") or "[]"
    try:
        d["subtasks"] = json.loads(raw)
    except Exception:
        d["subtasks"] = []
    raw_tags = d.get("tags", "") or ""
    d["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
    return d

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/panel/health")
def health():
    return {"status": "ok", "db": os.path.exists(TASKS_DB)}


@app.get("/panel/tasks")
def get_tasks():
    """All pending tasks ordered by priority then due date."""
    if not os.path.exists(TASKS_DB):
        return []
    try:
        with _conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE completed = 0
                ORDER BY
                    CASE priority WHEN 'high' THEN 1
                                  WHEN 'medium' THEN 2
                                  WHEN 'low' THEN 3 END ASC,
                    due_date ASC NULLS LAST,
                    created_at ASC
                """
            ).fetchall()
        return [_row(r) for r in rows]
    except Exception as e:
        print(f"[PANEL] get_tasks error: {e}")
        return []


@app.get("/panel/stats")
def get_stats():
    if not os.path.exists(TASKS_DB):
        return {"pending": 0, "due_today": 0, "overdue": 0}
    try:
        today = date.today().isoformat()
        with _conn() as conn:
            pending   = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed=0").fetchone()[0]
            due_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date=? AND completed=0", (today,)
            ).fetchone()[0]
            overdue   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date<? AND completed=0", (today,)
            ).fetchone()[0]
        return {"pending": pending, "due_today": due_today, "overdue": overdue}
    except Exception as e:
        print(f"[PANEL] stats error: {e}")
        return {"pending": 0, "due_today": 0, "overdue": 0}


@app.put("/panel/tasks/{task_id}/complete")
def complete_task(task_id: int):
    """Mark task as complete. Tries Seven API first, falls back to direct DB."""
    # Try Seven API first (keeps both UIs in sync)
    try:
        import requests as _r
        resp = _r.put(
            f"http://127.0.0.1:7777/api/tasks/{task_id}",
            json={"completed": True},
            timeout=2
        )
        if resp.status_code == 200:
            return {"success": True, "source": "seven"}
    except Exception:
        pass

    # Direct DB fallback
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE tasks SET completed=1, completed_at=? WHERE id=?",
                (datetime.now().isoformat(), task_id)
            )
            conn.commit()
        return {"success": True, "source": "direct"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.put("/panel/tasks/{task_id}/subtasks")
def update_subtasks(task_id: int, body: dict):
    """Update subtasks list for a task."""
    subtasks = body.get("subtasks", [])
    subtasks_json = json.dumps(subtasks) if subtasks else "[]"

    # Try Seven API first
    try:
        import requests as _r
        resp = _r.put(
            f"http://127.0.0.1:7777/api/tasks/{task_id}",
            json={"subtasks": subtasks},
            timeout=2
        )
        if resp.status_code == 200:
            return {"success": True, "source": "seven"}
    except Exception:
        pass

    # Direct DB fallback
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE tasks SET subtasks=? WHERE id=?",
                (subtasks_json, task_id)
            )
            conn.commit()
        return {"success": True, "source": "direct"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/panel/trigger")
def check_trigger():
    """
    Electron polls this every 3 seconds.
    Returns trigger data if daemon wrote a trigger file.
    Clears trigger after reading.
    """
    if os.path.exists(PANEL_TRIGGER):
        try:
            with open(PANEL_TRIGGER, "r") as f:
                data = json.load(f)
            os.remove(PANEL_TRIGGER)
            return {"triggered": True, "data": data}
        except Exception:
            return {"triggered": False}
    return {"triggered": False}


class QuickTaskCreate(BaseModel):
    text: str

@app.get("/panel/triggers")
def get_triggers_direct():
    """
    Direct SQLite read of triggers.db — fallback when Seven's main
    backend (port 7777) is not running. Read-only: toggling, editing,
    deleting, and firing a trigger all still require the main app.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        return []

    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT * FROM triggers ORDER BY "
            "CASE WHEN hotkey IS NOT NULL THEN 0 "
            "WHEN voice_phrase IS NOT NULL THEN 1 "
            "WHEN audio_pattern IS NOT NULL THEN 2 "
            "ELSE 3 END, name ASC"
        ).fetchall()
        conn.close()

        result = []
        for r in rows:
            d = dict(r)
            d["enabled"] = bool(d.get("enabled", 1))
            d["silent"] = bool(d.get("silent", 0))
            try:
                d["action_data"] = json.loads(d.get("action_data") or "{}")
            except Exception:
                d["action_data"] = {}
            result.append(d)
        return result
    except Exception as e:
        print(f"[PANEL] triggers fallback error: {e}")
        return []


@app.put("/panel/triggers/{trigger_id}")
def update_trigger_direct(trigger_id: int, body: dict):
    """
    Direct SQLite update of triggers.db — fallback when Seven's main
    backend (port 7777) is not running. Supports updating enabled state
    and other trigger fields.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        raise HTTPException(status_code=500, detail="Triggers database not found")

    # Validate trigger_id exists
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Build update query dynamically based on provided fields
    updates = []
    params = []

    if 'name' in body and body['name'] is not None:
        if not body['name'].strip():
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        updates.append("name = ?")
        params.append(body['name'].strip())

    if 'action_type' in body and body['action_type'] is not None:
        # Validate action_type
        valid_action_types = {
            'open_app', 'open_url', 'open_file', 'open_folder',
            'open_workspace', 'run_command', 'seven_action'
        }
        if body['action_type'] not in valid_action_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action_type. Must be one of: {', '.join(valid_action_types)}"
            )
        updates.append("action_type = ?")
        params.append(body['action_type'])

    if 'action_data' in body and body['action_data'] is not None:
        updates.append("action_data = ?")
        params.append(json.dumps(body['action_data']))

    if 'hotkey' in body:
        updates.append("hotkey = ?")
        params.append(body['hotkey'] if body['hotkey'] else None)

    if 'voice_phrase' in body:
        updates.append("voice_phrase = ?")
        params.append(body['voice_phrase'].lower().strip() if body['voice_phrase'] else None)

    if 'audio_pattern' in body:
        updates.append("audio_pattern = ?")
        params.append(body['audio_pattern'] if body['audio_pattern'] else None)

    if 'enabled' in body and body['enabled'] is not None:
        updates.append("enabled = ?")
        params.append(1 if body['enabled'] else 0)

    if 'silent' in body and body['silent'] is not None:
        updates.append("silent = ?")
        params.append(1 if body['silent'] else 0)

    if 'icon' in body and body['icon'] is not None:
        updates.append("icon = ?")
        params.append(body['icon'])

    if not updates:
        # No fields to update
        return {"success": True}

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(trigger_id)

    # Create a fresh connection for the update operation
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            f"UPDATE triggers SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        conn.close()

        # Signal daemon to reload triggers (if daemon is running)
        try:
            with open(RELOAD_SIGNAL, "w") as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            print(f"[PANEL] Failed to write reload signal: {e}")

        return {"success": True}
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/panel/triggers/{trigger_id}")
def delete_trigger_direct(trigger_id: int):
    """
    Direct SQLite delete of triggers.db — fallback when Seven's main
    backend (port 7777) is not running.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        raise HTTPException(status_code=500, detail="Triggers database not found")

    # Validate trigger_id exists
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Create a fresh connection for the delete operation
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
        conn.commit()
        conn.close()

        # Signal daemon to reload triggers (if daemon is running)
        try:
            with open(RELOAD_SIGNAL, "w") as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            print(f"[PANEL] Failed to write reload signal: {e}")

        return {"success": True}
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


def _set_brightness_level(level: int) -> tuple:
    """Set screen brightness to specified percentage (0-100) instantly on laptops and desktop monitors."""
    level = max(0, min(100, int(level)))
    methods_tried = []

    # Method 1: screen_brightness_control library
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return True, f"Brightness set to {level}% via SBC"
    except Exception as e:
        methods_tried.append(f"sbc: {e}")

    # Method 2: Direct Windows Dxva2 DDC/CI API (for desktop monitors via HDMI/DisplayPort)
    try:
        import ctypes
        from ctypes import wintypes

        monitors = []
        def _enum_proc(hmon, hdc, lprect, lparam):
            monitors.append(hmon)
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM
        )
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_enum_proc), 0)

        dxva2 = ctypes.windll.dxva2
        class PHYSICAL_MONITOR(ctypes.Structure):
            _fields_ = [
                ("hPhysicalMonitor", wintypes.HANDLE),
                ("szPhysicalMonitorDescription", wintypes.WCHAR * 128)
            ]

        success_mon = 0
        for hmon in monitors:
            num_monitors = wintypes.DWORD()
            if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(num_monitors)) and num_monitors.value > 0:
                p_monitors = (PHYSICAL_MONITOR * num_monitors.value)()
                if dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, num_monitors.value, p_monitors):
                    for pm in p_monitors:
                        if dxva2.SetVCPFeature(pm.hPhysicalMonitor, 0x10, level):
                            success_mon += 1
                        dxva2.DestroyPhysicalMonitor(pm.hPhysicalMonitor)
        if success_mon > 0:
            return True, f"Brightness set to {level}% on {success_mon} monitor(s) via DDC/CI"
    except Exception as e:
        methods_tried.append(f"dxva2: {e}")

    # Method 3: PowerShell WMI (laptops and integrated displays)
    try:
        ps_cmd = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
            timeout=3
        )
        return True, f"Brightness set to {level}% via WMI"
    except Exception as e:
        methods_tried.append(f"wmi: {e}")

    return False, f"Failed to set brightness ({'; '.join(methods_tried)})"


def _set_volume_level(level: int) -> tuple:
    """Set system audio volume percentage instantly."""
    level = max(0, min(100, int(level)))
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        return True, f"Volume set to {level}%"
    except Exception:
        pass

    try:
        ps_script = f"""
        $obj = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}
        1..{level // 2} | ForEach-Object {{ $obj.SendKeys([char]175) }}
        """
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
            timeout=3
        )
        return True, f"Volume set to ~{level}%"
    except Exception as e:
        return False, f"Failed to set volume: {e}"


def _send_win_key(vk_code: int, name: str) -> tuple:
    """Send a Windows virtual key event instantly."""
    try:
        import ctypes
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)
        return True, f"Executed: {name}"
    except Exception as e:
        return False, f"Key action failed: {e}"


def _execute_seven_action_direct(action_data: dict, trigger_name: str = "") -> tuple:
    """Fast, direct execution for system, media, and hardware actions."""
    import re
    import ctypes

    raw = (
        action_data.get("action")
        or action_data.get("name")
        or action_data.get("command")
        or action_data.get("target")
        or trigger_name
        or ""
    )
    raw_str = str(raw).strip().lower()
    value = action_data.get("value")

    # 1. Screen Brightness
    if "bright" in raw_str:
        nums = re.findall(r'\d+', raw_str)
        level = None
        if nums:
            level = int(nums[0])
        elif value is not None:
            try:
                level = int(value)
            except Exception:
                pass

        if level is not None:
            return _set_brightness_level(level)
        elif "up" in raw_str:
            return _set_brightness_level(80)
        elif "down" in raw_str:
            return _set_brightness_level(30)
        else:
            return _set_brightness_level(50)

    # 2. Volume & Mute
    if "mute" in raw_str:
        return _send_win_key(0xAD, "Mute Toggle")

    if "vol" in raw_str or "sound" in raw_str or "audio" in raw_str:
        nums = re.findall(r'\d+', raw_str)
        level = None
        if nums:
            level = int(nums[0])
        elif value is not None:
            try:
                level = int(value)
            except Exception:
                pass

        if level is not None:
            return _set_volume_level(level)
        elif "up" in raw_str:
            return _send_win_key(0xAF, "Volume Up")
        elif "down" in raw_str:
            return _send_win_key(0xAE, "Volume Down")
        else:
            return _set_volume_level(50)

    # 3. Media Controls
    if any(k in raw_str for k in ("play", "pause", "media")):
        return _send_win_key(0xB3, "Play/Pause")
    if "next" in raw_str:
        return _send_win_key(0xB0, "Next Track")
    if any(k in raw_str for k in ("prev", "previous", "back")):
        return _send_win_key(0xB1, "Previous Track")
    if "stop" in raw_str:
        return _send_win_key(0xB2, "Stop Track")

    # 4. System Controls
    if any(k in raw_str for k in ("lock", "lock_pc", "lock_workstation")):
        ctypes.windll.user32.LockWorkStation()
        return True, "Workstation locked"
    if any(k in raw_str for k in ("sleep", "suspend")):
        ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
        return True, "PC put to sleep"
    if any(k in raw_str for k in ("restart", "reboot")):
        subprocess.Popen("shutdown /r /t 0", shell=True)
        return True, "PC restarting"
    if any(k in raw_str for k in ("shutdown", "power_off")):
        subprocess.Popen("shutdown /s /t 0", shell=True)
        return True, "PC shutting down"
    if any(k in raw_str for k in ("taskmgr", "task_manager", "task manager")):
        subprocess.Popen("taskmgr.exe", shell=True)
        return True, "Task Manager opened"
    if any(k in raw_str for k in ("screen", "snip", "screenshot")):
        subprocess.Popen("explorer.exe ms-screenclip:", shell=True)
        return True, "Snipping Tool opened"
    if any(k in raw_str for k in ("recycle", "trash", "empty_recycle_bin")):
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return True, "Recycle bin emptied"

    return False, f"Unhandled seven_action: {raw_str}"


def _execute_action_direct(action_type: str, action_data: dict, trigger_name: str = "") -> tuple:
    """
    Direct, sub-millisecond offline action executor.
    Executes instantly without loading heavy AI/NLP modules.
    """
    try:
        if action_type == "open_app":
            apps = action_data.get("apps") or []
            if not isinstance(apps, list):
                apps = [apps]

            single = action_data.get("path") or action_data.get("app") or action_data.get("exe") or action_data.get("target")

            apps_to_launch = []
            for a in apps:
                if not a:
                    continue
                if isinstance(a, dict):
                    p = a.get("path") or a.get("exe") or a.get("name")
                    if p:
                        apps_to_launch.append(str(p).strip())
                else:
                    apps_to_launch.append(str(a).strip())

            if single:
                if isinstance(single, dict):
                    single_str = single.get("path") or single.get("exe") or single.get("name")
                else:
                    single_str = str(single).strip()

                if single_str and single_str not in apps_to_launch:
                    apps_to_launch.insert(0, single_str)

            if not apps_to_launch:
                return False, "No application specified"

            launched = []
            for app_str in apps_to_launch:
                if not app_str:
                    continue
                try:
                    os.startfile(app_str)
                    launched.append(app_str)
                except Exception:
                    try:
                        cmd = f'start "" "{app_str}"' if " " in app_str else f'start {app_str}'
                        subprocess.Popen(cmd, shell=True)
                        launched.append(app_str)
                    except Exception as le:
                        print(f"[PANEL FIRE] Launch failed for {app_str}: {le}")
            return True, f"Launched: {', '.join(launched)}"

        elif action_type == "open_url":
            url = action_data.get("url") or action_data.get("target") or action_data.get("link")
            if not url:
                return False, "No URL specified"
            url_str = str(url).strip()
            if not (url_str.startswith("http://") or url_str.startswith("https://")):
                url_str = "https://" + url_str
            webbrowser.open(url_str)
            return True, f"Opened URL: {url_str}"

        elif action_type == "open_file":
            file_path = action_data.get("path") or action_data.get("file") or action_data.get("target")
            if not file_path:
                return False, "No file path specified"
            file_str = str(file_path).strip()
            if not os.path.exists(file_str):
                return False, f"File not found: {file_str}"
            os.startfile(file_str)
            return True, f"Opened file: {file_str}"

        elif action_type == "open_folder":
            folder = action_data.get("path") or action_data.get("folder") or action_data.get("target")
            if not folder:
                return False, "No folder path specified"
            folder_str = str(folder).strip()
            if not os.path.exists(folder_str):
                return False, f"Folder not found: {folder_str}"
            os.startfile(folder_str)
            return True, f"Opened folder: {folder_str}"

        elif action_type == "run_command":
            cmd = action_data.get("command") or action_data.get("cmd") or action_data.get("script")
            if not cmd:
                return False, "No command specified"
            cmd_str = str(cmd).strip()
            subprocess.Popen(cmd_str, shell=True)
            return True, f"Executed command: {cmd_str}"

        elif action_type == "open_workspace":
            ws_id = action_data.get("workspace_id")
            ws_name = action_data.get("workspace_name") or action_data.get("name")

            triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")
            ws_data = None
            if os.path.exists(triggers_db):
                try:
                    with sqlite3.connect(triggers_db, timeout=10) as conn:
                        conn.row_factory = sqlite3.Row
                        if ws_id:
                            row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
                        elif ws_name:
                            row = conn.execute("SELECT * FROM workspaces WHERE LOWER(name) = ?", (ws_name.lower().strip(),)).fetchone()
                        else:
                            row = None
                        if row:
                            ws_data = dict(row)
                except Exception as wse:
                    print(f"[PANEL] Workspace fetch error: {wse}")

            if ws_data:
                try:
                    from workspace_modules.restore import restore_workspace
                    restore_workspace(ws_data)
                    return True, f"Restored workspace: {ws_data.get('name')}"
                except Exception as restore_err:
                    apps_json = ws_data.get("apps", "[]")
                    apps = json.loads(apps_json) if isinstance(apps_json, str) else apps_json
                    launched = []
                    for a in apps:
                        p = a.get("exe") or a.get("path") or a.get("name")
                        if p:
                            try:
                                os.startfile(p)
                                launched.append(p)
                            except Exception:
                                try:
                                    subprocess.Popen(p, shell=True)
                                    launched.append(p)
                                except Exception:
                                    pass
                    return True, f"Launched apps for {ws_data.get('name')}: {launched}"

            return False, "Workspace not found"

        elif action_type == "seven_action":
            return _execute_seven_action_direct(action_data, trigger_name)

        return False, f"Unknown action type: {action_type}"

    except Exception as e:
        print(f"[PANEL] _execute_action_direct error: {e}")
        return False, str(e)


@app.post("/panel/triggers/{trigger_id}/fire")
def fire_trigger_direct(trigger_id: int):
    """
    Direct SQLite fire of trigger — executes immediately with 0 delay.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        raise HTTPException(status_code=500, detail="Triggers database not found")

    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

        trigger = dict(row)
        trigger["enabled"] = bool(trigger.get("enabled", 1))
        trigger["silent"] = bool(trigger.get("silent", 0))
        try:
            trigger["action_data"] = json.loads(trigger.get("action_data") or "{}")
        except Exception:
            trigger["action_data"] = {}

        conn.execute(
            "UPDATE triggers SET fire_count = fire_count + 1, last_fired = ? WHERE id = ?",
            (datetime.now().isoformat(), trigger_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    import threading

    def _async_fire():
        action_type = trigger.get("action_type", "")
        action_data = trigger.get("action_data", {})
        trigger_name = trigger.get("name", "")
        print(f"[PANEL FIRE] Executing trigger #{trigger_id} '{trigger_name}' ({action_type})")
        try:
            ok, msg = _execute_action_direct(action_type, action_data, trigger_name)
            print(f"[PANEL FIRE] Result: ok={ok}, msg={msg}")
        except Exception as ex:
            import traceback
            print(f"[PANEL FIRE CRASH] Traceback:")
            traceback.print_exc()

    threading.Thread(target=_async_fire, daemon=True).start()
    return {"success": True, "message": f"Trigger #{trigger_id} fired"}


@app.post("/panel/tasks")
def quick_create_task(body: QuickTaskCreate):
    """Create a task directly from the panel without Seven running."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Empty task text")

    try:
        now = datetime.now().isoformat()
        with _conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (text, due_date, due_time, priority,"
                " completed, created_at, completed_at, tags,"
                " description, subtasks)"
                " VALUES (?, NULL, NULL, 'medium', 0, ?, NULL, NULL, NULL, '[]')",
                (body.text.strip(), now)
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()
        return {"success": True, "task": _row(row)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/panel/tasks/{task_id}")
def update_task_direct(task_id: int, body: dict):
    """
    Direct SQLite update of tasks.db — fallback when Seven's main
    backend (port 7777) is not running.
    """
    if not os.path.exists(TASKS_DB):
        raise HTTPException(status_code=500, detail="Tasks database not found")

    updates = []
    params = []

    if 'text' in body and body['text'] is not None:
        if not body['text'].strip():
            raise HTTPException(status_code=400, detail="Task text cannot be empty")
        updates.append("text = ?")
        params.append(body['text'].strip())

    if 'due_date' in body:
        updates.append("due_date = ?")
        params.append(body['due_date'] or None)

    if 'due_time' in body:
        updates.append("due_time = ?")
        params.append(body['due_time'] or None)

    if 'priority' in body and body['priority'] is not None:
        if body['priority'] not in ("low", "medium", "high"):
            raise HTTPException(status_code=400, detail="Invalid priority")
        updates.append("priority = ?")
        params.append(body['priority'])

    if 'tags' in body:
        updates.append("tags = ?")
        params.append(body['tags'] or None)

    if 'description' in body:
        updates.append("description = ?")
        params.append(body['description'] or None)

    if 'subtasks' in body:
        updates.append("subtasks = ?")
        params.append(json.dumps(body['subtasks']) if body['subtasks'] else "[]")

    if 'completed' in body and body['completed'] is not None:
        updates.append("completed = ?")
        params.append(1 if body['completed'] else 0)
        updates.append("completed_at = ?")
        params.append(datetime.now().isoformat() if body['completed'] else None)

    if not updates:
        return {"success": True}

    params.append(task_id)

    try:
        with _conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/panel/tasks/{task_id}")
def delete_task_direct(task_id: int):
    """
    Direct SQLite delete of task — fallback when Seven's main
    backend (port 7777) is not running.
    """
    if not os.path.exists(TASKS_DB):
        raise HTTPException(status_code=500, detail="Tasks database not found")

    try:
        with _conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/panel/schedules")
def get_schedules():
    """Get active schedules for panel display."""
    try:
        sched_file = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "SEVEN", "schedules.json"
        )
        if not os.path.exists(sched_file):
            return []
        with open(sched_file, "r") as f:
            scheds = json.load(f)
        active = [s for s in scheds if s.get("status") == "active"]
        active.sort(key=lambda s: s.get("time", ""))
        return active[:5]
    except Exception:
        return []


@app.delete("/panel/schedules/{sched_id}")
def cancel_schedule_direct(sched_id: int):
    """Cancel a schedule directly from schedules.json when Seven is offline."""
    try:
        sched_file = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "SEVEN", "schedules.json"
        )
        if not os.path.exists(sched_file):
            raise HTTPException(status_code=404, detail="Schedules file not found")

        with open(sched_file, "r") as f:
            scheds = json.load(f)

        updated = False
        for s in scheds:
            if s.get("id") == sched_id:
                s["status"] = "cancelled"
                s["updated_at"] = datetime.now().isoformat()
                updated = True
                break

        if updated:
            with open(sched_file, "w") as f:
                json.dump(scheds, f, indent=2)

            # Emit a reload trigger so schedule daemon updates lists
            try:
                signal_file = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")),
                    "SEVEN", "schedule_reload.signal"
                )
                with open(signal_file, "w") as f:
                    f.write(datetime.now().isoformat())
            except Exception:
                pass

            return {"success": True}

        raise HTTPException(status_code=404, detail="Schedule not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print(f"[PANEL SERVER] Starting on port 7778")
    print(f"[PANEL SERVER] Tasks DB: {TASKS_DB}")
    uvicorn.run(app, host="127.0.0.1", port=7778, log_level="warning")