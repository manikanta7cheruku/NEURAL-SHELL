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
from datetime import datetime

APPDATA       = os.environ.get('APPDATA', os.path.expanduser('~'))
SEVEN_ROOT    = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(SEVEN_ROOT, 'seven_data', 'schedules.json')
ALERT_FILE    = os.path.join(APPDATA, 'SEVEN', 'schedule_alert.json')
FIRED_FILE    = os.path.join(APPDATA, 'SEVEN', 'daemon_fired.json')
LOCK_FILE     = os.path.join(APPDATA, 'SEVEN', 'schedule_daemon.lock')

_battery_level = 100


# ── Helpers ──────────────────────────────────────────────────────────────────

def acquire_lock():
    """Prevent multiple daemon instances."""
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    old_pid = int(f.read().strip())
                try:
                    import psutil
                    if psutil.pid_exists(old_pid):
                        print(f"[DAEMON] Already running with PID {old_pid}")
                        return False
                except Exception:
                    pass
            except Exception:
                pass
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        print(f"[DAEMON] Lock error: {e}")
        return True


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