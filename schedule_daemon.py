"""
schedule_daemon.py
Lightweight background process that monitors schedules.json
and fires notifications even when Seven is not running.
Runs at Windows startup via Task Scheduler (registered at install time).
"""

import json
import os
import time
import sys
from datetime import datetime


APPDATA = os.environ.get('APPDATA', os.path.expanduser('~'))
SCHEDULE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'seven_data', 'schedules.json'
)
ALERT_FILE = os.path.join(APPDATA, 'SEVEN', 'schedule_alert.json')
FIRED_FILE  = os.path.join(APPDATA, 'SEVEN', 'daemon_fired.json')


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
    try:
        from winotify import Notification, audio
        icons = {"alarm": "Alarm", "reminder": "Reminder",
                 "timer": "Timer", "event": "Event"}
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

    # Write to alert file so Seven picks up when reopened
    try:
        os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True)
        with open(ALERT_FILE, 'w') as f:
            json.dump({"active": True, "message": message,
                       "type": stype, "id": None}, f)
    except Exception:
        pass


def is_seven_running():
    """Check if Seven backend is already running."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:7777/api/status", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def main():
    print("[DAEMON] Schedule daemon started")
    fired = load_fired()

    while True:
        try:
            # Skip if Seven is running - it handles its own schedules
            if not is_seven_running():
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

            time.sleep(15)

        except KeyboardInterrupt:
            print("[DAEMON] Stopped")
            break
        except Exception as e:
            print(f"[DAEMON] Error: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()