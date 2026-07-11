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
    """
    Launch trigger_daemon.py as a truly independent process.
    Survives Seven quit. Also registers in Windows Task Scheduler
    for auto-start at login.
    """
    try:
        _daemon = os.path.join(os.getcwd(), "trigger_daemon.py")
        _python = sys.executable
        _pythonw = _python.replace("python.exe", "pythonw.exe")
        if not os.path.exists(_pythonw):
            _pythonw = _python

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + "[SYSTEM] trigger_daemon.py not found")
            return

        # Check if already running
        _already_running = False
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmd = " ".join(proc.info['cmdline'] or [])
                    if "trigger_daemon" in cmd and str(proc.pid) != str(os.getpid()):
                        _already_running = True
                        break
                except Exception:
                    pass
        except Exception:
            pass

        if _already_running:
            print(Fore.CYAN + "[SYSTEM] Trigger daemon already running")
            return

        # Launch as fully detached process
        # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP ensures it survives parent exit
        _CREATE_NO_WINDOW        = 0x08000000
        _DETACHED_PROCESS        = 0x00000008
        _CREATE_NEW_PROCESS_GROUP = 0x00000200

        proc = subprocess.Popen(
            [_pythonw, _daemon],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            start_new_session=True,
        )
        proc.detach = True  # marker, doesn't do anything but documents intent
        print(Fore.CYAN + f"[SYSTEM] Trigger daemon launched (PID {proc.pid})")

        # Register in Windows Task Scheduler for auto-start at login
        _register_trigger_daemon_startup(_pythonw, _daemon)

    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Trigger daemon launch failed: {_de}")


def _register_trigger_daemon_startup(pythonw_path, daemon_path):
    """
    Register trigger_daemon.py in Windows Task Scheduler.
    Runs at every user login so triggers work even if Seven never opens.
    Only registers once — subsequent calls are no-ops.
    """
    try:
        task_name = "SevenTriggerDaemon"

        # Check if already registered
        check = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        if check.returncode == 0:
            # Already registered
            return

        # Register new task
        cmd = [
            "schtasks", "/create", "/f",
            "/tn", task_name,
            "/tr", f'"{pythonw_path}" "{daemon_path}"',
            "/sc", "onlogon",
            "/rl", "limited",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        if result.returncode == 0:
            print(Fore.GREEN + "[SYSTEM] Trigger daemon registered for auto-start at login")
        else:
            print(Fore.YELLOW + f"[SYSTEM] Trigger daemon auto-start registration failed: {result.stderr.strip()}")

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Trigger daemon registration error: {e}")