"""
main_modules/startup/battery_monitor.py

Background thread that watches battery level.
Alerts at 30%, 20%, 10%, 5% when unplugged.
Speaks alerts AND shows Windows notifications.
"""

import time
import threading
from colorama import Fore


def start_battery_monitor():
    """Start the battery monitor as a daemon thread."""
    threading.Thread(target=_battery_monitor_loop, daemon=True).start()
    print(Fore.CYAN + "[SYSTEM] Battery monitor active")


def _battery_monitor_loop():
    _alerted_30 = False
    _alerted_20 = False
    _alerted_10 = False
    _alerted_5  = False

    while True:
        try:
            time.sleep(300)  # Check every 5 minutes
            import psutil
            bat = psutil.sensors_battery()
            if bat is None:
                continue

            # Reset alerts if plugged in
            if bat.power_plugged:
                _alerted_30 = _alerted_20 = _alerted_10 = _alerted_5 = False
                continue

            pct = int(bat.percent)

            if pct <= 5 and not _alerted_5:
                _alert(f"Battery at {pct} percent. Shutting down soon. Plug in immediately.",
                       "Seven - BATTERY CRITICAL")
                _alerted_5 = True
            elif pct <= 10 and not _alerted_10:
                _alert(f"Battery at {pct} percent. Getting critical. Plug in now.",
                       "Seven - Battery Critical")
                _alerted_10 = True
            elif pct <= 20 and not _alerted_20:
                _alert(f"Battery at {pct} percent. Should plug in soon.",
                       "Seven - Battery Low")
                _alerted_20 = True
            elif pct <= 30 and not _alerted_30:
                _alert(f"Battery at {pct} percent. Just a heads up.",
                       "Seven - Battery Notice")
                _alerted_30 = True
        except Exception:
            pass


def _alert(msg, title):
    """Speak + show Windows notification for battery alert."""
    try:
        import mouth as _m
        _m.speak(msg)
    except Exception:
        pass
    try:
        from winotify import Notification, audio
        t = Notification(app_id="Seven AI", title=title, msg=msg, duration="long")
        t.set_audio(audio.Default, loop=False)
        t.show()
    except Exception:
        pass