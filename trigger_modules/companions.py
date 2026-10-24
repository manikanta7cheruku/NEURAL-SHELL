"""
trigger_modules/companions.py
Keeps the other background helpers alive when the Seven window has never been opened.

At login Windows starts only this daemon (Run key) and the overlay (scheduled task). The reminder daemon and the
Alt+Shift+T panel host used to be started by the Seven app alone, so after a reboot reminders and the side panel
stayed off until the user opened Seven. This daemon always runs, so it brings them up and checks on them now and then.
"""
import os
import subprocess

from trigger_modules.config import PROJECT_ROOT
from trigger_modules.overlay import find_electron

_DETACHED = 0x08000000 | 0x00000008 | 0x00000200   # no window, detached, new process group


def _running(fragment: str) -> bool:
    try:
        import psutil
        for p in psutil.process_iter(['cmdline']):
            try:
                if fragment in " ".join(p.info['cmdline'] or []):
                    return True
            except Exception:
                continue
    except Exception:
        return True   # without psutil we cannot tell, so never start a second copy
    return False


def _ensure_schedule_daemon():
    if _running("schedule_daemon.py"):
        return
    try:
        from main_modules.startup.daemon_launcher import launch_schedule_daemon
        launch_schedule_daemon()
        print("[TRIGGER DAEMON] Reminder daemon started")
    except Exception as e:
        print(f"[TRIGGER DAEMON] Reminder daemon not started: {e}")


def _ensure_panel_host():
    if _running("--panel-host"):
        return
    electron = find_electron()
    app_path = os.environ.get('SEVEN_APP_PATH') or PROJECT_ROOT
    host_js = os.path.join(app_path, "electron", "panel_host.js")
    if not electron or not os.path.exists(host_js):
        return
    cmd = [electron]
    if electron.lower().endswith("seven.exe"):
        data = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'SEVEN', 'panel_user_data')
        os.makedirs(data, exist_ok=True)
        cmd += [f"--user-data-dir={data}", "--"]
    cmd += [host_js, "--panel-host"]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                         creationflags=_DETACHED, close_fds=True, cwd=app_path,
                         env={**os.environ, "SEVEN_APP_PATH": app_path})
        print("[TRIGGER DAEMON] Task panel host started")
    except Exception as e:
        print(f"[TRIGGER DAEMON] Task panel host not started: {e}")


def ensure_companions():
    """Start the reminder daemon and the panel host if either is missing. Cheap enough to call every few minutes."""
    _ensure_schedule_daemon()
    _ensure_panel_host()
