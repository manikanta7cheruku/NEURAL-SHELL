"""
main_modules/startup/daemon_launcher.py

Launches schedule_daemon.py as a hidden detached process.
Skips launch if daemon is already running.
"""

import os
import sys
import subprocess
from colorama import Fore


def launch_schedule_daemon():
    """Launch schedule_daemon.py if not already running."""
    try:
        _daemon = os.path.join(os.getcwd(), "schedule_daemon.py")
        _python = sys.executable
        _pythonw = _python.replace("python.exe", "pythonw.exe")
        if not os.path.exists(_pythonw):
            _pythonw = _python

        # Count running daemon instances
        _daemon_count = 0
        try:
            import psutil
            for _proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    _cmd = " ".join(_proc.info['cmdline'] or [])
                    if "schedule_daemon" in _cmd:
                        _daemon_count += 1
                except Exception:
                    pass
        except Exception:
            pass

        if _daemon_count == 0 and os.path.exists(_daemon):
            _CREATE_NO_WINDOW = 0x08000000
            _DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                [_pythonw, _daemon],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS
            )
            print(Fore.CYAN + "[SYSTEM] Schedule daemon started (hidden)")
        elif _daemon_count > 0:
            print(Fore.CYAN + f"[SYSTEM] Daemon already running ({_daemon_count} instance). Skipping.")

    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Daemon skipped: {_de}")