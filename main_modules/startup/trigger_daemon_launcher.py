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
    Returns SEVEN project root directory.
    Uses __file__ location — always correct regardless of cwd.
    """
    this_file        = os.path.abspath(__file__)
    startup_dir      = os.path.dirname(this_file)
    main_modules_dir = os.path.dirname(startup_dir)
    project_root     = os.path.dirname(main_modules_dir)

    # In production, verify this is right by checking main.py exists
    if os.path.exists(os.path.join(project_root, "main.py")):
        return project_root

    # Fallback: check registry for install path
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\SevenAI"
        )
        install_dir = winreg.QueryValueEx(key, "InstallDir")[0]
        winreg.CloseKey(key)
        app_path = os.path.join(install_dir, "resources", "app")
        if os.path.exists(os.path.join(app_path, "main.py")):
            return app_path
    except Exception:
        pass

    return project_root


def _get_venv_python(project_root: str) -> str:
    """
    Find the correct Python executable for daemon spawning.

    Priority order:
      1. Packaged embedded Python (production install)
      2. Venv pythonw.exe (dev mode, no console = survives terminal close)
      3. Venv python.exe (dev fallback)
      4. Current interpreter (last resort)
    """
    candidates = [
        # Production: embedded Python in installed app
        os.path.join(project_root, "python", "pythonw.exe"),
        os.path.join(project_root, "python", "python.exe"),
        # Dev: venv
        os.path.join(project_root, "venv", "Scripts", "pythonw.exe"),
        os.path.join(project_root, "venv", "Scripts", "python.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            print(Fore.CYAN + f"[TRIGGER] Using Python: {c}")
            return c

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
    Register trigger_daemon for auto-start at Windows login.
    Uses XML Task Scheduler ONLY — never Registry Run (creates duplicates).
    Cleans up ALL alternate registrations first to prevent ghost daemons.
    """
    task_name = "SevenTriggerDaemon"

    _cleanup_duplicate_registrations(task_name)

    if _register_via_xml(task_name, python, daemon):
        print(Fore.GREEN + "[TRIGGER] Registered in Task Scheduler (XML) ✓")
        return

    print(Fore.RED + "[TRIGGER] CRITICAL: Task Scheduler registration failed. "
          "Daemon will not auto-start at login. Reinstall Seven or check admin rights.")


def _register_via_xml(task_name: str, exe_path: str, arg_path: str) -> bool:
    """
    Register a scheduled task via XML definition.
    XML is universally reliable and handles quoting correctly.
    Task triggers at user logon, runs highest privilege current user has.
    """
    import getpass
    import tempfile

    user = getpass.getuser()

    xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Seven AI</Author>
    <Description>Seven trigger daemon — global hotkeys, workspaces, arrangements</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{exe_path}</Command>
      <Arguments>"{arg_path}"</Arguments>
      <WorkingDirectory>{os.path.dirname(arg_path)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'''

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-16')
    try:
        tmp.write(xml)
        tmp.close()
        result = subprocess.run(
            ["schtasks", "/create", "/f", "/tn", task_name, "/xml", tmp.name],
            capture_output=True, text=True, timeout=15,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            return True
        print(Fore.YELLOW + f"[TRIGGER] XML register failed: {result.stderr.strip()}")
        return False
    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGER] XML register error: {e}")
        return False
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _cleanup_duplicate_registrations(task_name: str):
    """
    Remove ALL alternate registrations for the daemon.
    Prevents multiple daemon instances at login.
    Called before registering the primary method.

    Purges:
      - HKCU Run key entry
      - HKLM Run key entry (in case someone ran installer as admin)
      - Startup folder .bat file
      - Startup folder .lnk shortcut
    """
    import winreg

    for hive_name, hive in [
        ("HKCU", winreg.HKEY_CURRENT_USER),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE),
    ]:
        try:
            key = winreg.OpenKey(
                hive,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, task_name)
                print(Fore.CYAN + f"[TRIGGER] Removed {hive_name} Run entry: {task_name}")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        except Exception:
            pass

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        )
        startup = winreg.QueryValueEx(key, "Startup")[0]
        winreg.CloseKey(key)
        for ext in (".bat", ".lnk", ".cmd"):
            f = os.path.join(startup, f"{task_name}{ext}")
            if os.path.exists(f):
                try:
                    os.remove(f)
                    print(Fore.CYAN + f"[TRIGGER] Removed Startup file: {f}")
                except Exception:
                    pass
    except Exception:
        pass


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
    ALWAYS registers Task Scheduler entry even if daemon already running,
    so auto-start at login works after next reboot.
    """
    root = _get_project_root()

    electron_check = None
    for rel in [
        os.path.join("node_modules", "electron", "dist", "electron.exe"),
        os.path.join("node_modules", ".bin", "electron.cmd"),
        os.path.join("frontend", "node_modules", "electron", "dist", "electron.exe"),
    ]:
        c = os.path.join(root, rel)
        if os.path.exists(c):
            electron_check = c
            break

    daemon_js_check = os.path.join(root, "electron", "overlay_daemon.js")

    if electron_check and os.path.exists(daemon_js_check):
        _register_overlay_startup(electron_check, daemon_js_check)

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
    time.sleep(1)
    if _is_overlay_alive():
        print(Fore.GREEN + f"[OVERLAY] Overlay daemon ready ✓ (PID {pid})")
    else:
        print(Fore.CYAN + f"[OVERLAY] Warming up in background (PID {pid})")


def _register_overlay_startup(electron: str, daemon_js: str):
    """
    Register overlay_daemon for auto-start at login via XML Task Scheduler.
    Never uses Registry Run (creates duplicates).
    """
    task_name = "SevenOverlayDaemon"
    _cleanup_duplicate_registrations(task_name)

    if _register_via_xml(task_name, electron, daemon_js):
        print(Fore.GREEN + "[OVERLAY] Registered in Task Scheduler (XML) ✓")
        return

    print(Fore.RED + "[OVERLAY] CRITICAL: Task Scheduler registration failed. "
          "Overlay will not auto-start at login. Reinstall Seven or check admin rights.")