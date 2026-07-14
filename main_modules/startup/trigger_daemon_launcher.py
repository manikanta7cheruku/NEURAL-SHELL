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
    Launch trigger_daemon.py as a detached background process.
    Survives Seven closing. Auto-kills old instances first.
    """
    try:
        _daemon = os.path.join(os.getcwd(), "trigger_daemon.py")

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + f"[TRIGGER] trigger_daemon.py not found at {_daemon}")
            return

        # Find venv Python
        _project_root = os.getcwd()
        _venv_pythonw = os.path.join(_project_root, "venv", "Scripts", "pythonw.exe")
        _venv_python  = os.path.join(_project_root, "venv", "Scripts", "python.exe")

        if os.path.exists(_venv_pythonw):
            _pythonw = _venv_pythonw
        elif os.path.exists(_venv_python):
            _pythonw = _venv_python
        else:
            _pythonw = sys.executable
            print(Fore.YELLOW + f"[TRIGGER] venv not found, using {_pythonw}")

        print(Fore.CYAN + f"[TRIGGER] Python: {_pythonw}")
        print(Fore.CYAN + f"[TRIGGER] Daemon: {_daemon}")

        # Kill ALL existing trigger_daemon processes first
        try:
            import psutil
            _my_pid = os.getpid()
            _killed = 0
            for _proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    _cmd = ' '.join(_proc.info['cmdline'] or [])
                    if 'trigger_daemon' in _cmd and _proc.info['pid'] != _my_pid:
                        print(Fore.YELLOW + f"[TRIGGER] Killing old daemon PID {_proc.info['pid']}")
                        _proc.kill()
                        _proc.wait(timeout=3)
                        _killed += 1
                except Exception:
                    pass
            if _killed:
                print(Fore.YELLOW + f"[TRIGGER] Killed {_killed} old daemon(s)")
        except Exception as _ke:
            print(Fore.YELLOW + f"[TRIGGER] Kill check failed: {_ke}")

        # Launch as detached process
        _CREATE_NO_WINDOW         = 0x08000000
        _DETACHED_PROCESS         = 0x00000008
        _CREATE_NEW_PROCESS_GROUP = 0x00000200

        print(Fore.CYAN + "[TRIGGER] Spawning daemon...")

        proc = subprocess.Popen(
            [_pythonw, _daemon],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            start_new_session=True,
            cwd=_project_root,
        )

        print(Fore.GREEN + f"[TRIGGER] Daemon spawned PID {proc.pid}")

        # Verify it's actually running after 1 second
        import time
        time.sleep(1)

        try:
            import psutil
            if psutil.pid_exists(proc.pid):
                print(Fore.GREEN + f"[TRIGGER] Daemon confirmed running ✓")
            else:
                print(Fore.RED + f"[TRIGGER] Daemon PID {proc.pid} died immediately!")
        except Exception:
            pass

        # Register for auto-start at login
        _register_trigger_daemon_startup(_pythonw, _daemon)

    except Exception as _e:
        print(Fore.RED + f"[TRIGGER] Launch failed: {_e}")
        import traceback
        traceback.print_exc()

        # Always prefer venv Python — it has all required packages
        # Never use system Python which lacks hands.workspace etc.
        _project_root = os.getcwd()
        _venv_pythonw = os.path.join(_project_root, "venv", "Scripts", "pythonw.exe")
        _venv_python  = os.path.join(_project_root, "venv", "Scripts", "python.exe")

        if os.path.exists(_venv_pythonw):
            _pythonw = _venv_pythonw
            print(Fore.CYAN + f"[SYSTEM] Using venv pythonw: {_pythonw}")
        elif os.path.exists(_venv_python):
            _pythonw = _venv_python
            print(Fore.CYAN + f"[SYSTEM] Using venv python: {_pythonw}")
        else:
            # Fallback to current executable
            _python  = sys.executable
            _pythonw = _python.replace("python.exe", "pythonw.exe")
            if not os.path.exists(_pythonw):
                _pythonw = _python
            print(Fore.YELLOW + f"[SYSTEM] venv not found, using: {_pythonw}")

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + "[SYSTEM] trigger_daemon.py not found")
            return

        # Kill ALL existing trigger_daemon instances before starting fresh
        # Ensures clean state — no stale daemons from previous sessions
        try:
            import psutil
            _my_pid = os.getpid()
            for _proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
                try:
                    _cmd = ' '.join(_proc.info['cmdline'] or [])
                    if 'trigger_daemon' in _cmd and _proc.info['pid'] != _my_pid:
                        print(Fore.YELLOW + f"[SYSTEM] Killing old daemon "
                              f"(PID {_proc.info['pid']})")
                        _proc.kill()
                        _proc.wait(timeout=3)
                except Exception:
                    pass
        except Exception:
            pass    

        # Now check if correct daemon already running via mutex
        _already_running = False
        try:
            import ctypes
            _test = ctypes.windll.kernel32.CreateMutexW(
                None, False, "Global\\SevenTriggerDaemon_SingleInstance"
            )
            _err = ctypes.windll.kernel32.GetLastError()
            if _test:
                ctypes.windll.kernel32.CloseHandle(_test)
            if _err == 183:  # ERROR_ALREADY_EXISTS
                _already_running = True
        except Exception:
            pass

        if _already_running:
            print(Fore.CYAN + "[SYSTEM] Trigger daemon already running (correct Python)")
            _register_trigger_daemon_startup(_pythonw, _daemon)
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
    Always re-registers to keep paths current.
    Falls back to Startup folder if schtasks fails.
    """
    try:
        task_name = "SevenTriggerDaemon"

        cmd = [
            "schtasks", "/create", "/f",
            "/tn", task_name,
            "/tr", f'"{pythonw_path}" "{daemon_path}"',
            "/sc", "onlogon",
            "/rl", "limited",
            "/delay", "0000:30",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        if result.returncode == 0:
            print(Fore.GREEN + "[SYSTEM] Trigger daemon registered for auto-start at login ✓")
        else:
            print(Fore.YELLOW + f"[SYSTEM] schtasks failed: {result.stderr.strip()}")
            _register_startup_folder_trigger(pythonw_path, daemon_path)

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Trigger daemon registration error: {e}")
        _register_startup_folder_trigger(pythonw_path, daemon_path)


def _register_startup_folder_trigger(pythonw_path, daemon_path):
    """Fallback: Startup folder .bat file. No admin rights needed."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        startup_folder = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)

        bat_path = os.path.join(startup_folder, "SevenTriggerDaemon.bat")
        with open(bat_path, 'w') as f:
            f.write(
                f'@echo off\n'
                f'start "" /B "{pythonw_path}" "{daemon_path}"\n'
            )
        print(Fore.GREEN + f"[SYSTEM] Trigger daemon added to Startup folder ✓")

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Startup folder fallback failed: {e}")

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
        # Check multiple roots — cwd may differ from project root
        _roots = list(dict.fromkeys([project_root, os.getcwd()]))
        electron_exe = None
        for _root in _roots:
            for _rel in [
                os.path.join("node_modules", "electron", "dist", "electron.exe"),
                os.path.join("node_modules", ".bin", "electron.cmd"),
                os.path.join("frontend", "node_modules", "electron", "dist", "electron.exe"),
            ]:
                _c = os.path.join(_root, _rel)
                if os.path.exists(_c):
                    electron_exe = _c
                    break
            if electron_exe:
                break

        if not electron_exe:
            print(Fore.YELLOW + "[SYSTEM] Electron not found — overlay daemon disabled")
            print(Fore.YELLOW + f"[SYSTEM] Searched: {_roots}")
            return

        print(Fore.CYAN + f"[SYSTEM] Electron found: {electron_exe}")

        daemon_js = None
        for _root in _roots:
            _c = os.path.join(_root, "electron", "overlay_daemon.js")
            if os.path.exists(_c):
                daemon_js = _c
                break

        if not daemon_js:
            print(Fore.YELLOW + f"[SYSTEM] overlay_daemon.js not found in: {_roots}")
            return

        print(Fore.CYAN + f"[SYSTEM] overlay_daemon.js: {daemon_js}")

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
    Always re-registers to keep paths current.
    Falls back to Startup folder if schtasks fails.
    """
    try:
        task_name = "SevenOverlayDaemon"

        cmd = [
            "schtasks", "/create", "/f",
            "/tn", task_name,
            "/tr", f'"{electron_exe}" "{daemon_js}"',
            "/sc", "onlogon",
            "/rl", "limited",
            "/delay", "0000:45",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=0x08000000
        )
        if result.returncode == 0:
            print(Fore.GREEN + "[SYSTEM] Overlay daemon registered for auto-start at login ✓")
        else:
            print(Fore.YELLOW + f"[SYSTEM] schtasks failed: {result.stderr.strip()}")
            _register_startup_folder_overlay(electron_exe, daemon_js)

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Overlay daemon registration error: {e}")
        _register_startup_folder_overlay(electron_exe, daemon_js)


def _register_startup_folder_overlay(electron_exe, daemon_js):
    """Fallback: Startup folder .bat file. No admin rights needed."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        )
        startup_folder = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)

        bat_path = os.path.join(startup_folder, "SevenOverlayDaemon.bat")
        with open(bat_path, 'w') as f:
            f.write(
                f'@echo off\n'
                f'start "" /B "{electron_exe}" "{daemon_js}"\n'
            )
        print(Fore.GREEN + f"[SYSTEM] Overlay daemon added to Startup folder ✓")

    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Startup folder fallback failed: {e}")