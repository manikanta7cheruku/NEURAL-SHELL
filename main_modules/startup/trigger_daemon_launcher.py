"""
main_modules/startup/trigger_daemon_launcher.py

Launches trigger_daemon.py as a hidden detached process.
Skips if daemon is already running.
Same pattern as daemon_launcher.py for schedule_daemon.
"""

import os
import sys
import subprocess
from colorama import Fore


def launch_trigger_daemon():
    """Launch trigger_daemon.py if not already running."""
    try:
        _daemon = os.path.join(os.getcwd(), "trigger_daemon.py")
        _python = sys.executable
        _pythonw = _python.replace("python.exe", "pythonw.exe")
        if not os.path.exists(_pythonw):
            _pythonw = _python

        # Check if already running via mutex (daemon self-prevents)
        # We just try to spawn — if another instance exists it exits immediately

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + "[SYSTEM] trigger_daemon.py not found")
            return

        _CREATE_NO_WINDOW = 0x08000000
        _DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [_pythonw, _daemon],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS
        )
        print(Fore.CYAN + "[SYSTEM] Trigger daemon launched")

    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Trigger daemon launch failed: {_de}")