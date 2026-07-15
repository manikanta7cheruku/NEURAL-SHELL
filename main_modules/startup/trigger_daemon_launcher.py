"""
main_modules/startup/trigger_daemon_launcher.py

Launches trigger_daemon.py and overlay_daemon.js as detached processes.
Both survive Seven closing — fully independent.
Auto-kills stale instances before spawning fresh ones.
"""

import os
import sys
import socket
import subprocess
import time
from colorama import Fore


# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────

def _get_project_root() -> str:
    """
    Always returns the SEVEN project root directory.
    Works regardless of cwd — uses this file's absolute location.
    trigger_daemon_launcher.py is at:
      SEVEN/main_modules/startup/trigger_daemon_launcher.py
    So project root is 2 levels up.
    """
    this_file = os.path.abspath(__file__)
    startup_dir     = os.path.dirname(this_file)
    main_modules_dir = os.path.dirname(startup_dir)
    project_root    = os.path.dirname(main_modules_dir)
    return project_root


def _get_venv_python(project_root: str) -> str:
    """
    Return venv pythonw.exe for daemon spawning.
    pythonw.exe has no console window and is fully independent —
    it survives parent process exit without being killed.
    python.exe is a console app and gets killed when the terminal closes.
    """
    venv_pythonw = os.path.join(project_root, "venv", "Scripts", "pythonw.exe")
    if os.path.exists(venv_pythonw):
        return venv_pythonw

    venv_python = os.path.join(project_root, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python

    return sys.executable


def _kill_existing(name_fragment: str, correct_python: str = ""):
    """
    Kill all processes whose command line contains name_fragment.
    If correct_python is given, only kills processes NOT using that Python.
    This preserves the correct daemon if already running.
    """
    my_pid = os.getpid()
    correct_lower = correct_python.lower() if correct_python else ""

    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'cmdline', 'exe']):
            try:
                cmd = " ".join(proc.info['cmdline'] or [])
                exe = (proc.info['exe'] or "").lower()

                if name_fragment not in cmd:
                    continue
                if proc.info['pid'] == my_pid:
                    continue

                # If we know the correct Python, only kill wrong-Python daemons
                if correct_lower and exe == correct_lower:
                    print(Fore.CYAN + f"[DAEMON] Correct daemon already running "
                          f"PID {proc.info['pid']} — keeping")
                    continue

                print(Fore.YELLOW + f"[DAEMON] Killing wrong daemon "
                      f"PID {proc.info['pid']} exe={exe}")
                proc.kill()
                proc.wait(timeout=3)

            except Exception:
                pass
    except ImportError:
        pass
    except Exception:
        pass


def _spawn_detached(cmd: list, cwd: str) -> int:
    """
    Spawn a fully detached background process.
    Returns PID or 0 on failure.
    """
    _CREATE_NO_WINDOW         = 0x08000000
    _DETACHED_PROCESS         = 0x00000008
    _CREATE_NEW_PROCESS_GROUP = 0x00000200

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
        start_new_session=True,
        cwd=cwd,
    )
    return proc.pid


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return False


def _is_overlay_alive() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 7891), timeout=0.5)
        s.sendall(b'{"type":"ping"}\n')
        s.settimeout(0.5)
        data = s.recv(256)
        s.close()
        return b'"ok":true' in data or b'"ok": true' in data
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────
# TRIGGER DAEMON
# ─────────────────────────────────────────────────────────────────────────

def launch_trigger_daemon():
    """
    Launch trigger_daemon.py as a detached background process.
    Works whether Seven is open or closed.
    Survives Seven closing.
    """
    root   = _get_project_root()
    daemon = os.path.join(root, "trigger_daemon.py")
    python = _get_venv_python(root)

    print(Fore.CYAN + f"[TRIGGER] Root:   {root}")
    print(Fore.CYAN + f"[TRIGGER] Python: {python}")
    print(Fore.CYAN + f"[TRIGGER] Daemon: {daemon}")

    if not os.path.exists(daemon):
        print(Fore.RED + f"[TRIGGER] trigger_daemon.py not found: {daemon}")
        return

    if not os.path.exists(python):
        print(Fore.RED + f"[TRIGGER] Python not found: {python}")
        return

    # Kill wrong-Python daemons, keep correct one if already running
    _kill_existing("trigger_daemon", correct_python=python)
    time.sleep(0.3)

    # Check if correct daemon already running after killing wrong ones
    already_running = False
    try:
        import psutil
        python_lower = python.lower()
        for proc in psutil.process_iter(['pid', 'cmdline', 'exe']):
            try:
                cmd = " ".join(proc.info['cmdline'] or [])
                exe = (proc.info['exe'] or "").lower()
                if "trigger_daemon" in cmd and exe == python_lower:
                    already_running = True
                    print(Fore.CYAN + f"[TRIGGER] Correct daemon already running "
                          f"PID {proc.info['pid']} ✓")
                    break
            except Exception:
                pass
    except Exception:
        pass

    if already_running:
        _register_trigger_startup(python, daemon)
        return

    # Spawn fresh daemon
    try:
        pid = _spawn_detached([python, daemon], cwd=root)
        print(Fore.CYAN + f"[TRIGGER] Spawned PID {pid}")
    except Exception as e:
        print(Fore.RED + f"[TRIGGER] Spawn failed: {e}")
        return

    # Quick check — don't block Seven startup
    time.sleep(0.5)
    if _pid_alive(pid):
        print(Fore.GREEN + f"[TRIGGER] Daemon running ✓ (PID {pid})")
    else:
        print(Fore.RED + f"[TRIGGER] Daemon died — check venv packages")
        return

    _register_trigger_startup(python, daemon)


def _register_trigger_startup(python: str, daemon: str):
    """
    Register trigger_daemon in Windows Task Scheduler.
    After this runs once, Windows auto-starts the daemon at every login.
    Seven never needs to be open for hotkeys to work.
    """
    try:
        result = subprocess.run(
            [
                "schtasks", "/create", "/f",
                "/tn", "SevenTriggerDaemon",
                "/tr", f'"{python}" "{daemon}"',
                "/sc", "onlogon",
                "/rl", "limited",
                "/delay", "0000:30",
            ],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            print(Fore.GREEN + "[TRIGGER] Registered in Task Scheduler ✓")
            print(Fore.GREEN + "[TRIGGER] Daemon will auto-start at every Windows login")
        else:
            print(Fore.YELLOW + f"[TRIGGER] Task Scheduler failed: {result.stderr.strip()}")
            _register_trigger_startup_folder(python, daemon)
            return
    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGER] Task Scheduler error: {e}")
        _register_trigger_startup_folder(python, daemon)


def _register_trigger_startup_folder(python: str, daemon: str):
    """Fallback: add to Windows Startup folder."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        startup = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)
        bat = os.path.join(startup, "SevenTriggerDaemon.bat")
        with open(bat, "w") as f:
            f.write(f'@echo off\nstart "" /B "{python}" "{daemon}"\n')
        print(Fore.GREEN + "[TRIGGER] Added to Startup folder ✓")
    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGER] Startup registration failed: {e}")


# ─────────────────────────────────────────────────────────────────────────
# OVERLAY DAEMON
# ─────────────────────────────────────────────────────────────────────────

def launch_overlay_daemon():
    """
    Launch overlay_daemon.js as a detached Electron process.
    Pre-warms notification and arrangement windows on TCP port 7891.
    Survives Seven closing.
    """
    if _is_overlay_alive():
        print(Fore.CYAN + "[OVERLAY] Already running ✓")
        return

    root = _get_project_root()

    # Find Electron executable
    electron = None
    for rel in [
        os.path.join("node_modules", "electron", "dist", "electron.exe"),
        os.path.join("node_modules", ".bin", "electron.cmd"),
        os.path.join("frontend", "node_modules", "electron", "dist", "electron.exe"),
    ]:
        c = os.path.join(root, rel)
        if os.path.exists(c):
            electron = c
            break

    if not electron:
        print(Fore.YELLOW + "[OVERLAY] Electron not found — overlay disabled")
        return

    daemon_js = os.path.join(root, "electron", "overlay_daemon.js")
    if not os.path.exists(daemon_js):
        print(Fore.YELLOW + f"[OVERLAY] overlay_daemon.js not found: {daemon_js}")
        return

    print(Fore.CYAN + f"[OVERLAY] Electron: {electron}")
    print(Fore.CYAN + f"[OVERLAY] Script:   {daemon_js}")

    pid = _spawn_detached([electron, daemon_js], cwd=root)
    print(Fore.CYAN + f"[OVERLAY] Spawned PID {pid}")

    # Check once after 1s — don't block Seven startup
    # Overlay continues warming up in background regardless
    time.sleep(1)
    if _is_overlay_alive():
        print(Fore.GREEN + f"[OVERLAY] Overlay daemon ready ✓ (PID {pid})")
    else:
        print(Fore.CYAN + f"[OVERLAY] Warming up in background (PID {pid})")

    _register_overlay_startup(electron, daemon_js)


def _register_overlay_startup(electron: str, daemon_js: str):
    """Register overlay_daemon in Windows Task Scheduler."""
    try:
        result = subprocess.run(
            [
                "schtasks", "/create", "/f",
                "/tn", "SevenOverlayDaemon",
                "/tr", f'"{electron}" "{daemon_js}"',
                "/sc", "onlogon",
                "/rl", "limited",
                "/delay", "0000:45",
            ],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            print(Fore.GREEN + "[OVERLAY] Registered for auto-start at login ✓")
        else:
            _register_overlay_startup_folder(electron, daemon_js)
    except Exception:
        _register_overlay_startup_folder(electron, daemon_js)


def _register_overlay_startup_folder(electron: str, daemon_js: str):
    """Fallback: add to Windows Startup folder."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        startup = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)
        bat = os.path.join(startup, "SevenOverlayDaemon.bat")
        with open(bat, "w") as f:
            f.write(f'@echo off\nstart "" /B "{electron}" "{daemon_js}"\n')
        print(Fore.GREEN + "[OVERLAY] Added to Startup folder ✓")
    except Exception as e:
        print(Fore.YELLOW + f"[OVERLAY] Startup registration failed: {e}")