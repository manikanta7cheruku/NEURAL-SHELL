"""
main_modules/startup/trigger_daemon_launcher.py

Launches trigger_daemon.py as a hidden detached process.
Skips if daemon is already running.
Same pattern as daemon_launcher.py for schedule_daemon.
"""

import os
import sys
import socket
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

# ─────────────────────────────────────────────────────────────────────────
# OVERLAY DAEMON — Persistent Electron host for instant notifications
# ─────────────────────────────────────────────────────────────────────────

def launch_overlay_daemon():
    """
    Launch overlay_daemon.js — persistent Electron host that pre-loads
    notification and arrangement windows for instant (30-50ms) display.

    Skips if already running (checks TCP port 7891).
    Survives Seven quit.
    """
    try:
        # Check if already running by pinging TCP port
        if _is_overlay_daemon_alive():
            print(Fore.CYAN + "[SYSTEM] Overlay daemon already running")
            return

        project_root = os.getcwd()

        # Find Electron
        electron_candidates = [
            os.path.join(project_root, "node_modules", "electron", "dist", "electron.exe"),
            os.path.join(project_root, "node_modules", ".bin", "electron.cmd"),
            os.path.join(project_root, "frontend", "node_modules",
                         "electron", "dist", "electron.exe"),
        ]

        electron_exe = None
        for p in electron_candidates:
            if os.path.exists(p):
                electron_exe = p
                break

        if not electron_exe:
            print(Fore.YELLOW + "[SYSTEM] Electron not found — overlay daemon disabled")
            return

        daemon_js = os.path.join(project_root, "electron", "overlay_daemon.js")
        if not os.path.exists(daemon_js):
            print(Fore.YELLOW + f"[SYSTEM] overlay_daemon.js not found at {daemon_js}")
            return

        # Launch as fully detached process (survives Seven quit)
        _CREATE_NO_WINDOW         = 0x08000000
        _DETACHED_PROCESS         = 0x00000008
        _CREATE_NEW_PROCESS_GROUP = 0x00000200

        proc = subprocess.Popen(
            [electron_exe, daemon_js],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            start_new_session=True,
        )
        print(Fore.CYAN + f"[SYSTEM] Overlay daemon launched (PID {proc.pid})")

        # Register in Task Scheduler for auto-start at login
        _register_overlay_daemon_startup(electron_exe, daemon_js)

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Overlay daemon launch failed: {e}")


def _is_overlay_daemon_alive() -> bool:
    """Check if overlay daemon is responding on TCP 7891."""
    try:
        sock = socket.create_connection(("127.0.0.1", 7891), timeout=0.5)
        sock.sendall(b'{"type":"ping"}\n')
        sock.settimeout(0.5)
        data = sock.recv(256)
        sock.close()
        return b'"ok":true' in data or b'"ok": true' in data
    except Exception:
        return False


def _register_overlay_daemon_startup(electron_exe, daemon_js):
    """
    Register overlay_daemon.js in Windows Task Scheduler.
    Runs at every user login so notifications work even if Seven never opens.
    Only registers once.
    """
    try:
        task_name = "SevenOverlayDaemon"

        # Check if already registered
        check = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000
        )
        if check.returncode == 0:
            return

        cmd = [
            "schtasks", "/create", "/f",
            "/tn", task_name,
            "/tr", f'"{electron_exe}" "{daemon_js}"',
            "/sc", "onlogon",
            "/rl", "limited",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        if result.returncode == 0:
            print(Fore.GREEN + "[SYSTEM] Overlay daemon registered for auto-start at login")
        else:
            print(Fore.YELLOW + f"[SYSTEM] Overlay daemon auto-start reg failed: {result.stderr.strip()}")

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Overlay daemon registration error: {e}")