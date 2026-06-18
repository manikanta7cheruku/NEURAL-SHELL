"""
reminder_fire.py
Standalone script that fires a single reminder notification.
Called by Windows Task Scheduler when Seven is not running.
Can also reopen Seven if needed.
"""

import sys
import os
import json

def fire_reminder(message, stype="reminder"):
    """Show Windows notification for a reminder."""
    try:
        from winotify import Notification, audio
        type_icons = {
            "alarm":    "⏰",
            "reminder": "🔔",
            "timer":    "⏱",
            "event":    "📅",
        }
        icon = type_icons.get(stype, "🔔")
        toast = Notification(
            app_id="Seven AI",
            title=f"Seven - {stype.capitalize()}",
            msg=f"{icon} {message}",
            duration="long"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        print(f"[REMINDER] Fired: {message}")
    except Exception as e:
        print(f"[REMINDER] Notification failed: {e}")

    # Also write to alert file so Seven picks it up when reopened
    try:
        appdata = os.environ.get('APPDATA', '')
        alert_path = os.path.join(appdata, 'SEVEN', 'schedule_alert.json')
        with open(alert_path, 'w') as f:
            json.dump({
                "active":  True,
                "message": message,
                "type":    stype,
                "id":      None
            }, f)
    except Exception:
        pass


if __name__ == "__main__":
    # Called by Windows Task Scheduler with args:
    # reminder_fire.py "message text" "type"
    if len(sys.argv) >= 2:
        msg   = sys.argv[1]
        stype = sys.argv[2] if len(sys.argv) >= 3 else "reminder"
        fire_reminder(msg, stype)
    else:
        print("Usage: reminder_fire.py <message> <type>")