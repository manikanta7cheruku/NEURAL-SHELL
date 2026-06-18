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
# Schedules are stored in APPDATA so daemon and Seven share the same file
SCHEDULE_FILE = os.path.join(APPDATA, 'SEVEN', 'schedules.json')
ALERT_FILE    = os.path.join(APPDATA, 'SEVEN', 'schedule_alert.json')
FIRED_FILE    = os.path.join(APPDATA, 'SEVEN', 'daemon_fired.json')
LOCK_FILE     = os.path.join(APPDATA, 'SEVEN', 'schedule_daemon.lock')

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


def fire_notification(message, stype):
    """Show Windows notification, speak if Seven is closed, write alert file."""

    # Windows notification
    try:
        from winotify import Notification, audio
        icons = {
            "alarm":    "Alarm",
            "reminder": "Reminder",
            "timer":    "Timer",
            "event":    "Event",
        }
        toast = Notification(
            app_id="Seven AI",
            title=f"Seven - {icons.get(stype, 'Reminder')}",
            msg=message,
            duration="long"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        print(f"[DAEMON] Notification: {message}")
    except Exception as e:
        print(f"[DAEMON] Notification failed: {e}")

    # Speak: if Seven running use API, else use direct voice
    if is_seven_running():
        call_seven_speak(message)
    else:
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
    if not acquire_lock():
        return

    print("[DAEMON] Seven schedule daemon started")
    fired = load_fired()

    while True:
        try:
            if not is_seven_running():
                check_battery_alert()
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
                        fire_notification(message, stype)
                        fired.add(sid)
                        save_fired(fired)

                        # Mark as fired in schedules.json so Seven does not
                        # fire it again when it reopens
                        try:
                            with open(SCHEDULE_FILE, 'r') as _sf:
                                _all = json.load(_sf)
                            for _s in _all:
                                if str(_s.get("id", "")) == sid:
                                    _recur = _s.get("recur", "none")
                                    if _recur == "none":
                                        _s["status"] = "fired"
                                    # Recurring: leave active, scheduler advances time
                            with open(SCHEDULE_FILE, 'w') as _sf:
                                json.dump(_all, _sf, indent=2)
                            print(f"[DAEMON] Marked schedule {sid} as fired in schedules.json")
                        except Exception as _me:
                            print(f"[DAEMON] Could not mark fired in schedules.json: {_me}")

        except KeyboardInterrupt:
            print("[DAEMON] Stopped")
            release_lock()
            break
        except Exception as e:
            print(f"[DAEMON] Error: {e}")

        time.sleep(15)


if __name__ == "__main__":
    # Hide console window immediately
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except Exception:
            pass

    try:
        main()
    finally:
        release_lock()