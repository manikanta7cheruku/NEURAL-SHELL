"""
schedule_daemon.py
Runs at Windows login via Startup folder.
Fires reminders and battery alerts even when Seven is fully closed.
Includes direct voice playback via Seven's mouth.speaker module.
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime

# Immediate startup log - before anything else
# This fires even if the rest of the script crashes at import time
try:
    _EARLY_LOG = os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'SEVEN', 'schedule_daemon_debug.log'
    )
    os.makedirs(os.path.dirname(_EARLY_LOG), exist_ok=True)
    with open(_EARLY_LOG, 'a', encoding='utf-8') as _ef:
        _ef.write(f"\n[{datetime.now()}] STARTUP pid={os.getpid()} exe={sys.executable}\n")
except Exception:
    pass

# Hide console window immediately — must happen before any print()
# pythonw.exe has no console so this is a no-op there
# python.exe will flash briefly without this
if sys.platform == "win32":
    try:
        import ctypes
        _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _hwnd:
            ctypes.windll.user32.ShowWindow(_hwnd, 0)
            ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

# CRITICAL FIX: Force all underlying winotify/PowerShell subprocesses to spawn entirely hidden.
# This completely eliminates the black terminal flashing bug during daemon alerts.
_orig_popen = subprocess.Popen
def _hidden_popen(*args, **kwargs):
    if sys.platform == "win32":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x08000000 # CREATE_NO_WINDOW
    return _orig_popen(*args, **kwargs)
subprocess.Popen = _hidden_popen

APPDATA       = os.environ.get('APPDATA', os.path.expanduser('~'))
SEVEN_ROOT    = os.path.dirname(os.path.abspath(__file__))

# Debug log — writes every startup attempt with timestamp
# Check this file to see why daemon is not working
_DEBUG_LOG = os.path.join(APPDATA, 'SEVEN', 'schedule_daemon_debug.log')
def _dbg(msg):
    try:
        os.makedirs(os.path.join(APPDATA, 'SEVEN'), exist_ok=True)
        with open(_DEBUG_LOG, 'a', encoding='utf-8') as _f:
            _f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass
# Schedules are stored in APPDATA so daemon and Seven share the same file
SCHEDULE_FILE = os.path.join(APPDATA, 'SEVEN', 'schedules.json')
ALERT_FILE    = os.path.join(APPDATA, 'SEVEN', 'schedule_alert.json')
FIRED_FILE    = os.path.join(APPDATA, 'SEVEN', 'daemon_fired.json')
LOCK_FILE     = os.path.join(APPDATA, 'SEVEN', 'schedule_daemon.lock')
# PANEL_TRIGGER removed — panel no longer auto-opens from daemon

_battery_level = 100


# ── Helpers ──────────────────────────────────────────────────────────────────

def acquire_lock():
    """
    Prevent multiple daemon instances using Windows named mutex.
    Named mutex is the most reliable cross-process lock on Windows.
    Falls back to file lock if ctypes fails.
    """
    # Method 1: Windows named mutex - truly atomic, no race conditions
    try:
        import ctypes
        import ctypes.wintypes

        _mutex_name = "Global\\SevenScheduleDaemon_SingleInstance"
        _kernel32 = ctypes.windll.kernel32

        # Try to create mutex with this name
        # If another process already owns it, this returns a handle but
        # GetLastError() returns ERROR_ALREADY_EXISTS (183)
        _mutex = _kernel32.CreateMutexW(None, True, _mutex_name)
        _last_err = _kernel32.GetLastError()

        if _last_err == 183:  # ERROR_ALREADY_EXISTS
            print(f"[DAEMON] Already running (mutex exists). Exiting.")
            if _mutex:
                _kernel32.CloseHandle(_mutex)
            return False

        if not _mutex:
            print(f"[DAEMON] Could not create mutex. Falling back to file lock.")
            # Fall through to file lock method
        else:
            # Mutex created successfully - we are the only instance
            # Store handle so it stays alive for process lifetime
            acquire_lock._mutex_handle = _mutex
            print(f"[DAEMON] Mutex lock acquired. PID: {os.getpid()}")

            # Also write PID file for main.py to check
            try:
                os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
                with open(LOCK_FILE, 'w') as f:
                    f.write(str(os.getpid()))
            except Exception:
                pass

            return True

    except Exception as _mutex_err:
        print(f"[DAEMON] Mutex method failed: {_mutex_err}. Using file lock.")

    # Method 2: File lock fallback
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    old_pid = int(f.read().strip())
                try:
                    import psutil
                    if psutil.pid_exists(old_pid):
                        print(f"[DAEMON] Already running (PID {old_pid}). Exiting.")
                        return False
                except ImportError:
                    pass
            except Exception:
                pass
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass

        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        print(f"[DAEMON] File lock acquired. PID: {os.getpid()}")
        return True

    except FileExistsError:
        print(f"[DAEMON] File lock race condition. Exiting.")
        return False
    except Exception as e:
        print(f"[DAEMON] Lock error: {e}")
        return True

# Storage for mutex handle - must stay alive for process lifetime
acquire_lock._mutex_handle = None


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def load_schedules():
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def load_fired():
    try:
        if os.path.exists(FIRED_FILE):
            with open(FIRED_FILE, 'r') as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def save_fired(fired_ids):
    try:
        os.makedirs(os.path.dirname(FIRED_FILE), exist_ok=True)
        with open(FIRED_FILE, 'w') as f:
            json.dump(list(fired_ids), f)
    except Exception:
        pass


def is_seven_running():
    try:
        import requests
        r = requests.get("http://127.0.0.1:7777/api/status", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def daemon_speak(text):
    """Speak using Seven voice engine even when Seven UI is closed."""
    try:
        if SEVEN_ROOT not in sys.path:
            sys.path.insert(0, SEVEN_ROOT)
        from mouth.speaker import speak_text
        speak_text(text)
        print(f"[DAEMON] Spoke: {text}")
    except Exception as e:
        print(f"[DAEMON] Speak failed: {e}")


def call_seven_speak(msg):
    """Tell Seven to speak via API if it is running."""
    try:
        import requests as _r
        _r.post(
            "http://127.0.0.1:7777/api/system/battery-alert",
            params={"message": msg},
            timeout=2
        )
    except Exception:
        pass


def _send_overlay(msg: dict, timeout: float = 0.5) -> bool:
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


def fire_notification(message, stype):
    """
    Show Seven custom notification via overlay daemon.
    Works whether Seven is open or closed.
    Falls back to speaking if overlay daemon is not running.
    """
    _dbg(f"fire_notification called: stype={stype} message={message[:50]}")

    # Send to overlay daemon for custom notification
    _notif_success = _send_overlay({
        "type": "sched_notif",
        "data": {
            "type":    stype,
            "message": message,
            "holdMs":  8000,
        },
    }, timeout=1.0)

    if _notif_success:
        print(f"[DAEMON] Overlay notification shown: {message}")
        _dbg("Overlay notification SUCCESS")
    else:
        print(f"[DAEMON] Overlay daemon not available")
        _dbg("Overlay daemon not available")

    # Only speak when Seven is closed.
    # When Seven is running, hands/scheduler.py background thread
    # handles speaking via its own _fire_schedule callback.
    if not is_seven_running():
        daemon_speak(message)

    # Write alert file so Seven shows panel when reopened
    try:
        os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True)
        with open(ALERT_FILE, 'w') as f:
            json.dump({
                "active":  True,
                "message": message,
                "type":    stype,
                "id":      None
            }, f)
    except Exception:
        pass


# ── Battery monitoring ────────────────────────────────────────────────────────

def check_battery_alert():
    global _battery_level
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return
        pct     = int(battery.percent)
        plugged = battery.power_plugged

        if plugged:
            _battery_level = 100
            return

        if pct <= 5 and _battery_level != 5:
            fire_notification(
                f"Battery at {pct} percent. Shutting down soon. Plug in immediately.",
                "alarm"
            )
            _battery_level = 5
        elif pct <= 10 and _battery_level != 10:
            fire_notification(
                f"Battery at {pct} percent. Getting critical. Plug in now.",
                "alarm"
            )
            _battery_level = 10
        elif pct <= 20 and _battery_level != 20:
            fire_notification(
                f"Battery at {pct} percent. Should plug in soon.",
                "reminder"
            )
            _battery_level = 20
        elif pct <= 30 and _battery_level != 30:
            fire_notification(
                f"Battery at {pct} percent. Just a heads up.",
                "reminder"
            )
            _battery_level = 30
    except Exception:
        pass


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    _dbg(f"main() called. PID={os.getpid()}")
    if not acquire_lock():
        _dbg("Lock NOT acquired - another instance running. Exiting.")
        return

    _dbg("Lock acquired. Starting main loop.")
    print("[DAEMON] Seven schedule daemon started")
    fired = load_fired()
    _last_overdue_notif = 0  # unix timestamp — 30 min cooldown

    while True:
        try:
            seven_running = is_seven_running()

            # Always check battery regardless of Seven state
            check_battery_alert()

            # Always fire schedule notifications regardless of Seven state
            schedules = load_schedules()
            now = datetime.now()

            for schedule in schedules:
                if schedule.get("status") != "active":
                    continue

                sid = str(schedule.get("id", ""))
                if sid in fired:
                    continue

                try:
                    fire_time = datetime.fromisoformat(schedule["time"])
                except Exception:
                    continue

                    if now >= fire_time:
                        message = schedule.get("message", "Reminder")
                        stype   = schedule.get("type", "reminder")
                        _dbg(f"Schedule firing: id={sid} message={message[:50]}")
                        fire_notification(message, stype)
                    fired.add(sid)
                    save_fired(fired)

                    # Mark as fired in schedules.json
                    try:
                        with open(SCHEDULE_FILE, 'r') as _sf:
                            _all = json.load(_sf)
                        for _s in _all:
                            if str(_s.get("id", "")) == sid:
                                _recur = _s.get("recur", "none")
                                if _recur == "none":
                                    _s["status"] = "fired"
                        with open(SCHEDULE_FILE, 'w') as _sf:
                            json.dump(_all, _sf, indent=2)
                        print(f"[DAEMON] Marked schedule {sid} as fired")
                    except Exception as _me:
                        print(f"[DAEMON] Could not mark fired: {_me}")

            # Check overdue tasks — only notify when Seven is closed
            # When Seven is open it handles task display itself
            if not seven_running:
                try:
                    import sqlite3
                    _seven_data = os.path.join(APPDATA, 'SEVEN', 'seven_data')
                    _tasks_db   = os.path.join(_seven_data, 'tasks.db')

                    if os.path.exists(_tasks_db):
                        _tconn = sqlite3.connect(_tasks_db, timeout=5)
                        _tconn.row_factory = sqlite3.Row
                        _tconn.execute("PRAGMA journal_mode=WAL")

                        from datetime import date as _date_cls
                        _today = _date_cls.today().isoformat()

                        _overdue = _tconn.execute(
                            "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND completed = 0",
                            (_today,)
                        ).fetchone()[0]

                        _due_today = _tconn.execute(
                            "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND completed = 0",
                            (_today,)
                        ).fetchone()[0]

                        _tconn.close()

                        if _overdue > 0 and time.time() - _last_overdue_notif > 1800:
                            _task_msg = (
                                f"You have {_overdue} overdue task"
                                f"{'s' if _overdue != 1 else ''}."
                                + (f" Plus {_due_today} due today."
                                   if _due_today > 0 else "")
                            )
                            fire_notification(_task_msg, "reminder")
                            _last_overdue_notif = time.time()

                except Exception as _te:
                    print(f"[DAEMON] Task check error: {_te}")

        except KeyboardInterrupt:
            print("[DAEMON] Stopped")
            release_lock()
            break
        except Exception as e:
            print(f"[DAEMON] Error: {e}")

        time.sleep(15)


if __name__ == "__main__":
    try:
        main()
    finally:
        release_lock()