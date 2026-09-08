"""
main_modules/startup/daemon_launcher.py

Launches schedule_daemon.py and panel_server.py as hidden detached processes.
Uses robust packaged Python path resolution.
"""

import os
import sys
import subprocess
from colorama import Fore


def _get_app_python(app_root: str) -> str:
    """Resolve correct Python executable for background daemons."""
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    if app_path:
        for exe in ['pythonw.exe', 'python.exe']:
            c = os.path.join(app_path, 'python', exe)
            if os.path.exists(c):
                return c

    for exe in ['pythonw.exe', 'python.exe']:
        c = os.path.join(app_root, 'python', exe)
        if os.path.exists(c):
            return c

    # Dev mode fallback
    for c in [
        os.path.join(app_root, "venv", "Scripts", "pythonw.exe"),
        os.path.join(app_root, "venv", "Scripts", "python.exe"),
    ]:
        if os.path.exists(c):
            return c

    return sys.executable


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
        _python = _get_app_python(_app_root)

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + f"[DAEMON] schedule_daemon.py not found: {_daemon}")
            return

        # Check running instances
        _daemon_count = 0
        try:
            import psutil
            _py_lower = _python.lower()
            for _proc in psutil.process_iter(['pid', 'cmdline', 'exe']):
                try:
                    _cmd = " ".join(_proc.info['cmdline'] or [])
                    _exe = (_proc.info['exe'] or '').lower()
                    if "schedule_daemon" not in _cmd:
                        continue
                    if _exe == _py_lower:
                        _daemon_count += 1
                    else:
                        _proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

        if _daemon_count == 0:
            _env = os.environ.copy()
            _env['PYTHONPATH'] = os.pathsep.join([
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
                [_python, _daemon],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=0x08000000 | 0x00000008 | 0x00000200,
                close_fds=True,
                start_new_session=True,
                cwd=_app_root,
                env=_env,
            )
            print(Fore.GREEN + f"[SYSTEM] Schedule daemon started with {_python}")
        else:
            print(Fore.CYAN + f"[SYSTEM] Schedule daemon already running.")

    except Exception as _de:
        print(Fore.YELLOW + f"[SYSTEM] Schedule daemon launch error: {_de}")


def launch_panel_server():
    """
    Launch panel_server.py as independent background process on port 7778.
    """
    try:
        _app_root = (
            os.environ.get('SEVEN_APP_PATH') or
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))
        )
        _daemon = os.path.join(_app_root, "task_panel", "panel_server.py")
        _python = _get_app_python(_app_root)

        if not os.path.exists(_daemon):
            print(Fore.YELLOW + f"[PANEL-SRV] panel_server.py not found: {_daemon}")
            return

        import socket as _sock
        try:
            _s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            _s.settimeout(0.5)
            _res = _s.connect_ex(("127.0.0.1", 7778))
            _s.close()
            if _res == 0:
                print(Fore.CYAN + "[PANEL-SRV] Server already active on port 7778")
                return
        except Exception:
            pass

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

        subprocess.Popen(
            [_python, _daemon],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008 | 0x00000200,
            close_fds=True,
            start_new_session=True,
            cwd=_app_root,
            env=_env,
        )
        print(Fore.GREEN + f"[PANEL-SRV] Panel server started on port 7778")

    except Exception as _pe:
        print(Fore.YELLOW + f"[PANEL-SRV] Launch failed: {_pe}")