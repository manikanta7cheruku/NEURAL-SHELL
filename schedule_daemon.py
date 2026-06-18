"""
schedule_daemon.py
Runs at Windows login via Task Scheduler.
Fires reminders and battery alerts even when Seven is fully closed.
"""

import json
import os
import time
import sys
from datetime import datetime

APPDATA       = os.environ.get('APPDATA', os.path.expanduser('~'))

# Path to Seven's root folder (daemon lives in same folder)
SEVEN_ROOT = os.path.dirname(os.path.abspath(__file__))


def daemon_speak(text):
    """Speak text using Seven's voice engine."""
    try:
        # Add Seven's root to path so mouth.speaker can be imported
        if SEVEN_ROOT not in sys.path:
            sys.path.insert(0, SEVEN_ROOT)
        from mouth.speaker import speak_text
        speak_text(text)
    except Exception as e:
        print(f"[DAEMON] Speak failed: {e}")

SCHEDULE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'seven_data', 'schedules.json'
)
ALERT_FILE    = os.path.join(APPDATA, 'SEVEN', 'schedule_alert.json')
FIRED_FILE    = os.path.join(APPDATA, 'SEVEN', 'daemon_fired.json')

_battery_level = 100


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


def fire_notification(message, stype):
    # Show Windows notification
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
        print(f"[DAEMON] Fired: {message}")
    except Exception as e:
        print(f"[DAEMON] Notification failed: {e}")

    # Speak it (works even when Seven UI is closed)
    if not is_seven_running():
        daemon_speak(message)

    # Write to alert file so Seven shows banner when reopened
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

    # Write to alert file so Seven picks it up when reopened
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


def is_seven_running():
    try:
        import requests
        r = requests.get("http://127.0.0.1:7777/api/status", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def _call_seven_speak(msg):
    """Tell Seven to speak if it is running."""
    if is_seven_running():
        try:
            import requests as _req
            _req.post(
                "http://127.0.0.1:7777/api/system/battery-alert",
                params={"message": msg},
                timeout=2
            )
        except Exception:
            pass


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
            msg = f"Battery at {pct} percent. Shutting down soon. Plug in immediately."
            fire_notification(msg, "alarm")
            _call_seven_speak(msg)
            _battery_level = 5

        elif pct <= 10 and _battery_level != 10:
            msg = f"Battery at {pct} percent. Getting critical. Plug in now."
            fire_notification(msg, "alarm")
            _call_seven_speak(msg)
            _battery_level = 10

        elif pct <= 20 and _battery_level != 20:
            msg = f"Battery at {pct} percent. Should plug in soon."
            fire_notification(msg, "reminder")
            _call_seven_speak(msg)
            _battery_level = 20

        elif pct <= 30 and _battery_level != 30:
            msg = f"Battery at {pct} percent. Just a heads up."
            fire_notification(msg, "reminder")
            _call_seven_speak(msg)
            _battery_level = 30

    except Exception:
        pass


def main():
    print("[DAEMON] Schedule daemon started")
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
            break
        except Exception as e:
            print(f"[DAEMON] Error: {e}")

        time.sleep(15)


if __name__ == "__main__":
    main()