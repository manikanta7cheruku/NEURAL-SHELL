"""
main_modules/startup/validator.py
Startup validation — checks all critical dependencies before Seven launches.
Moved from main.py to keep the controller lean.
"""

import os
import sys
import socket


def validate_startup():
    """
    Validate all critical dependencies before starting Seven.
    Returns (ok: bool, errors: list[str], warnings: list[str])
    """
    errors = []
    warnings = []

    # Check 1: Ollama
    try:
        s = socket.create_connection(("127.0.0.1", 11434), timeout=2)
        s.close()
        print("[STARTUP] Ollama: running")
    except Exception:
        print("[STARTUP] Ollama offline — checking installation to auto-start...")
        try:
            from backend.bootstrap import is_ollama_installed, start_ollama
            if is_ollama_installed():
                print("[STARTUP] Ollama is installed — starting service in background...")
                import threading
                threading.Thread(target=start_ollama, daemon=True, name="OllamaBoot").start()
            else:
                warnings.append(
                    "Ollama is not installed. LLM responses will be unavailable.\n"
                    "  Please complete the environment setup step to install it."
                )
        except Exception as _start_err:
            print(f"[STARTUP] Could not auto-start Ollama: {_start_err}")
            warnings.append("Ollama is not running. Please launch it manually.")

    # Check 2: config.json
    _appdata = os.environ.get('APPDATA', '')
    _cfg_path = os.path.join(_appdata, 'SEVEN', 'config.json')
    if not os.path.exists(_cfg_path):
        warnings.append(f"config.json not found at {_cfg_path}. Seven will create defaults.")
    else:
        try:
            import json as _json
            with open(_cfg_path, 'r') as _f:
                _json.load(_f)
            print("[STARTUP] config.json: valid")
        except Exception as _ce:
            errors.append(f"config.json is corrupted: {_ce}\n  Fix: Delete {_cfg_path} and restart.")

    # Check 3: Port 7777
    try:
        _ps = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _ps.settimeout(1)
        _result = _ps.connect_ex(("127.0.0.1", 7777))
        _ps.close()
        if _result == 0:
            print("[STARTUP] Port 7777 in use - attempting to free it...")
            try:
                import subprocess as _sp
                _kill = _sp.run(['netstat', '-ano'], capture_output=True, text=True)
                for _line in _kill.stdout.splitlines():
                    if '7777' in _line and 'LISTENING' in _line:
                        _parts = _line.strip().split()
                        _pid = _parts[-1]
                        if _pid and _pid.isdigit() and int(_pid) != os.getpid():
                            print(f"[STARTUP] Killing PID {_pid} on port 7777")
                            _sp.run(['taskkill', '/PID', _pid, '/F'], capture_output=True)
                import time as _pt
                _pt.sleep(1)
                _ps2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                _ps2.settimeout(1)
                _result2 = _ps2.connect_ex(("127.0.0.1", 7777))
                _ps2.close()
                if _result2 == 0:
                    errors.append("Port 7777 is still in use. Restart your computer.")
                else:
                    print("[STARTUP] Port 7777: freed successfully")
            except Exception as _kill_err:
                print(f"[STARTUP] Could not free port 7777: {_kill_err}")
                errors.append("Port 7777 is already in use. Restart your computer.")
        else:
            print("[STARTUP] Port 7777: available")
    except Exception as _pe:
        print(f"[STARTUP] Port check failed: {_pe}")

    # Check 4: Disk space
    try:
        import shutil
        _free = shutil.disk_usage(_appdata or os.getcwd()).free
        _free_mb = _free / (1024 * 1024)
        if _free_mb < 100:
            errors.append(f"Critical: Only {_free_mb:.0f}MB disk space available.")
        elif _free_mb < 500:
            warnings.append(f"Low disk space: {_free_mb:.0f}MB available.")
        else:
            print(f"[STARTUP] Disk space: {_free_mb:.0f}MB available")
    except Exception as _de:
        print(f"[STARTUP] Disk check failed: {_de}")

    # Check 5: Memory directory
    try:
        _mem_dir = os.path.join(_appdata, 'SEVEN', 'seven_data', 'memory')
        os.makedirs(_mem_dir, exist_ok=True)
        _test_file = os.path.join(_mem_dir, '.write_test')
        with open(_test_file, 'w') as _tf:
            _tf.write('test')
        os.remove(_test_file)
        print("[STARTUP] Memory directory: writable")
    except Exception as _me:
        errors.append(f"Memory directory not writable: {_me}")

    # Check 6: VC++ Runtime
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.CDLL("msvcp140.dll")
            print("[STARTUP] Visual C++ Runtime: found")
        except OSError:
            errors.append(
                "CRITICAL: Visual C++ Redistributable (2015-2022) is not installed.\n"
                "  Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
        except Exception:
            pass

    return len(errors) == 0, errors, warnings