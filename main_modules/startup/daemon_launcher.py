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
        _app_root = (
            os.environ.get('SEVEN_APP_PATH') or
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))
        )
        _daemon = os.path.join(_app_root, "schedule_daemon.py")

        # Always use the packaged embedded Python
        # sys.executable may point to venv or system Python
        # which does not have the correct packages installed
        _embedded_pythonw = os.path.join(_app_root, 'python', 'pythonw.exe')
        _embedded_python  = os.path.join(_app_root, 'python', 'python.exe')

        if os.path.exists(_embedded_pythonw):
            _pythonw = _embedded_pythonw
        elif os.path.exists(_embedded_python):
            _pythonw = _embedded_python
        else:
            # Dev mode fallback - use venv
            _pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(_pythonw):
                _pythonw = sys.executable

        print(Fore.CYAN + f"[DAEMON] Using Python: {_pythonw}")
        print(Fore.CYAN + f"[DAEMON] Daemon path: {_daemon}")

        # Kill any schedule_daemon using wrong Python
        # then count remaining correct ones
        _daemon_count = 0
        try:
            import psutil
            _pythonw_lower = _pythonw.lower()
            for _proc in psutil.process_iter(['pid', 'cmdline', 'exe']):
                try:
                    _cmd = " ".join(_proc.info['cmdline'] or [])
                    _exe = (_proc.info['exe'] or '').lower()
                    if "schedule_daemon" not in _cmd:
                        continue
                    if _exe == _pythonw_lower:
                        # Correct Python - keep it
                        _daemon_count += 1
                        print(Fore.CYAN + f"[DAEMON] Correct daemon PID {_proc.info['pid']} running")
                    else:
                        # Wrong Python - kill it
                        print(Fore.YELLOW + f"[DAEMON] Killing wrong daemon PID {_proc.info['pid']} exe={_exe}")
                        _proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

        if _daemon_count == 0 and os.path.exists(_daemon):
            _CREATE_NO_WINDOW         = 0x08000000
            _DETACHED_PROCESS         = 0x00000008
            _CREATE_NEW_PROCESS_GROUP = 0x00000200

            # Build correct env for daemon
            _env = os.environ.copy()
            _env['PYTHONPATH']          = os.pathsep.join([
                _app_root,
                os.path.join(_app_root, 'python', 'Lib', 'site-packages'),
                os.path.join(_app_root, 'python', 'Lib'),
                os.path.join(_app_root, 'python'),
                os.path.join(_app_root, 'python', 'DLLs'),
            ])
            _env['SEVEN_APP_PATH']      = _app_root
            _env['SEVEN_ELECTRON_MODE'] = '1'
            _env['PYTHONUNBUFFERED']    = '1'
            _env['PYTHONIOENCODING']    = 'utf-8'

            subprocess.Popen(
                [_pythonw, _daemon],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                start_new_session=True,
                cwd=_app_root,
                env=_env,
            )
            print(Fore.CYAN + f"[SYSTEM] Schedule daemon started: {_pythonw}")
        elif _daemon_count > 0:
            print(Fore.CYAN + f"[SYSTEM] Schedule daemon already running ({_daemon_count}). Skipping.")

    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Daemon skipped: {_de}")


def launch_panel_server():
    """
    Launch panel_server.py as independent background process.
    Registered in Task Scheduler so it survives Seven closing.
    """
    try:
        _app_root = (
            os.environ.get('SEVEN_APP_PATH') or
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))
        )
        _daemon = os.path.join(_app_root, "task_panel", "panel_server.py")

        _embedded_python = os.path.join(_app_root, 'python', 'python.exe')
        if os.path.exists(_embedded_python):
            _python = _embedded_python
        else:
            _python = sys.executable

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + f"[PANEL-SRV] panel_server.py not found: {_daemon}")
            return

        # Check if already running on port 7778
        import socket as _sock
        try:
            _s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            _s.settimeout(1)
            _result = _s.connect_ex(("127.0.0.1", 7778))
            _s.close()
            if _result == 0:
                print(Fore.CYAN + "[PANEL-SRV] Already running on port 7778")
                return
        except Exception:
            pass

        # Kill any stale instances
        try:
            import psutil
            for _proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    _cmd = " ".join(_proc.info['cmdline'] or [])
                    if "panel_server" in _cmd:
                        _proc.kill()
                        print(Fore.YELLOW + f"[PANEL-SRV] Killed stale PID {_proc.info['pid']}")
                except Exception:
                    pass
        except Exception:
            pass

        # Build environment
        _env = os.environ.copy()
        _env['PYTHONPATH'] = os.pathsep.join([
            _app_root,
            os.path.join(_app_root, 'python', 'Lib', 'site-packages'),
            os.path.join(_app_root, 'python', 'Lib'),
            os.path.join(_app_root, 'python'),
            os.path.join(_app_root, 'python', 'DLLs'),
        ])
        _env['SEVEN_APP_PATH']    = _app_root
        _env['PYTHONUNBUFFERED']  = '1'
        _env['PYTHONIOENCODING']  = 'utf-8'

        _CREATE_NO_WINDOW         = 0x08000000
        _DETACHED_PROCESS         = 0x00000008
        _CREATE_NEW_PROCESS_GROUP = 0x00000200

        subprocess.Popen(
            [_python, _daemon],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW | _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            start_new_session=True,
            cwd=_app_root,
            env=_env,
        )
        print(Fore.GREEN + f"[PANEL-SRV] Started: {_python}")

        # Register in Task Scheduler so it auto-starts at login
        _register_panel_task(_python, _daemon)

    except Exception as _pe:
        print(Fore.YELLOW + f"[PANEL-SRV] Failed: {_pe}")


def _register_panel_task(python_exe: str, daemon_path: str):
    """Register panel_server.py in Windows Task Scheduler."""
    import getpass
    import tempfile

    task_name = "SevenPanelServer"

    try:
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0

        # Check if already registered correctly
        _check = subprocess.run(
            ["schtasks", "/query", "/tn", task_name, "/fo", "LIST"],
            capture_output=True, text=True, timeout=5,
            startupinfo=_si, creationflags=0x08000000
        )
        if _check.returncode == 0 and python_exe.lower() in _check.stdout.lower():
            print(Fore.CYAN + "[PANEL-SRV] Task Scheduler already registered")
            return

        user = getpass.getuser()
        xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Author>Seven AI</Author></RegistrationInfo>
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>{user}</UserId><Delay>PT90S</Delay></LogonTrigger>
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
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure><Interval>PT2M</Interval><Count>5</Count></RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>"{daemon_path}"</Arguments>
      <WorkingDirectory>{os.path.dirname(daemon_path)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''

        _tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.xml', delete=False, encoding='utf-16'
        )
        _tmp.write(xml)
        _tmp.close()

        subprocess.run(
            ["schtasks", "/create", "/f", "/tn", task_name, "/xml", _tmp.name],
            capture_output=True, text=True, timeout=15,
            startupinfo=_si, creationflags=0x08000000
        )
        os.unlink(_tmp.name)
        print(Fore.GREEN + "[PANEL-SRV] Registered in Task Scheduler")
    except Exception as _e:
        print(Fore.YELLOW + f"[PANEL-SRV] Task Scheduler registration failed: {_e}")