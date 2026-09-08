"""
PROJECT SEVEN - main.py (The Controller)
Version: 1.4.1 - Modular entry point

Thin entry point. All logic delegated to main_modules/.
System init → API server → voice loop.
"""
import sys
import os
import time
import threading
import subprocess

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Path setup ───────────────────────────────────────────────────────
_this_file_dir = os.path.dirname(os.path.abspath(__file__))
if _this_file_dir not in sys.path:
    sys.path.insert(0, _this_file_dir)

_app_path = os.environ.get('SEVEN_APP_PATH', '')
if _app_path and _app_path not in sys.path:
    sys.path.insert(0, _app_path)

# ── System init (VC++, numpy, logging) ──────────────────────────────
from main_modules.startup.system_init import (
    ensure_vcredist, apply_numpy_patch, setup_logging, setup_sentry
)
ensure_vcredist()
apply_numpy_patch()
logger = setup_logging()
setup_sentry()

import colorama
from colorama import Fore
colorama.init()

# ── Package check ────────────────────────────────────────────────────
def _packages_ready():
    python = sys.executable
    if _app_path:
        _emb = os.path.join(_app_path, 'python', 'python.exe')
        if os.path.exists(_emb):
            python = _emb
    cflags = 0x08000000 if sys.platform == 'win32' else 0
    for pkg in ['numpy', 'fastapi', 'uvicorn', 'pyttsx3', 'speech_recognition']:
        result = subprocess.run(
            [python, '-c', f'import {pkg.replace("-","_")}'],
            capture_output=True, creationflags=cflags
        )
        if result.returncode != 0:
            print(f"[SYSTEM] Missing package: {pkg}")
            return False
    print("[SYSTEM] Core packages ready.")
    return True

# ── Electron mode detection ──────────────────────────────────────────
def _detect_electron_mode():
    if os.environ.get('SEVEN_ELECTRON_MODE') == '1':
        return True
    if _app_path:
        if os.path.exists(os.path.join(_app_path, 'python', 'python311.dll')):
            return True
    return False

IS_ELECTRON_MODE = _detect_electron_mode()
print(f"[SYSTEM] Electron mode: {IS_ELECTRON_MODE}")

if not _packages_ready():
    print("[SYSTEM] Core packages not installed - pre-setup mode")
    from backend.startup import run_minimal_server
    run_minimal_server(host="127.0.0.1", port=7777)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        os._exit(0)

# ── Startup validation ──────────────────────────────────────────────
from main_modules.startup.validator import validate_startup
_startup_ok, _startup_errors, _startup_warnings = validate_startup()
for _w in _startup_warnings:
    print(f"[STARTUP] WARNING: {_w}")
if not _startup_ok:
    for _e in _startup_errors:
        print(f"[STARTUP] ERROR: {_e}")
    time.sleep(5)
    os._exit(1)

# ── App entry ────────────────────────────────────────────────────────
def start_app():
    import json as _json
    from backend.api_server import start_api_server, set_state as api_set_state

    # Kill zombie Python on port 7777
    try:
        import socket as _s
        _t = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        _t.settimeout(0.5)
        if _t.connect_ex(("127.0.0.1", 7777)) == 0:
            print(Fore.YELLOW + "[SYSTEM] Port 7777 occupied — killing zombie...")
            try:
                _out = subprocess.check_output(['netstat', '-ano'],
                    creationflags=0x08000000, text=True, timeout=5)
                for _line in _out.split('\n'):
                    if ':7777' in _line and 'LISTENING' in _line:
                        _zpid = _line.split()[-1].strip()
                        if _zpid.isdigit() and int(_zpid) != os.getpid():
                            subprocess.run(['taskkill', '/pid', _zpid, '/f'],
                                creationflags=0x08000000,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=3)
                time.sleep(1.0)
            except Exception:
                pass
        _t.close()
    except Exception:
        pass

    # Start API server
    try:
        start_api_server(host="127.0.0.1", port=7777)
        print(Fore.GREEN + "[SYSTEM] API server up on port 7777")
    except Exception as _e:
        print(Fore.RED + f"[SYSTEM] API server failed: {_e}")
        time.sleep(3)
        try:
            start_api_server(host="127.0.0.1", port=7777)
        except Exception:
            os._exit(1)

    time.sleep(0.8)

    # Check setup status
    _appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    _cfg_file = os.path.join(_appdata, 'SEVEN', 'config.json')
    _is_setup_done = False
    try:
        if os.path.exists(_cfg_file):
            with open(_cfg_file, 'r', encoding='utf-8') as _f:
                _is_setup_done = _json.load(_f).get('setup_complete', False)
    except Exception:
        pass

    if not _is_setup_done:
        print(Fore.CYAN + "[SYSTEM] Setup not complete — onboarding mode")
        try:
            while True:
                time.sleep(1)
                try:
                    with open(_cfg_file, 'r', encoding='utf-8') as _f:
                        if _json.load(_f).get('setup_complete', False):
                            os._exit(0)
                except Exception:
                    pass
        except KeyboardInterrupt:
            os._exit(0)
        return

    # Full mode
    print(Fore.GREEN + "[SYSTEM] Setup complete. Starting full Seven...")

    try:
        import telemetry
        telemetry.start_telemetry()
    except Exception:
        pass

    try:
        from backend.admin_server import start_admin_server
        start_admin_server()
    except Exception:
        pass

    import config

    class DummyUI:
        def update_status(self, text, color):
            try:
                api_set_state("status_text", text)
                api_set_state("status_color", color)
            except Exception:
                pass
        def close(self):
            os._exit(0)

    from main_modules.startup.context import SevenContext
    ctx = SevenContext()
    ctx.app_ui = DummyUI()
    ctx.api_set_state = api_set_state
    ctx.config = config

    from main_modules.startup.voice_loop import run_voice_loop
    _safe_mode_file = os.path.join(_appdata, 'SEVEN', 'safe_mode.flag')

    logic_thread = threading.Thread(
        target=run_voice_loop,
        args=(ctx, config, ctx.app_ui, api_set_state, _safe_mode_file),
        daemon=True
    )
    logic_thread.start()

    from main_modules.startup.battery_monitor import start_battery_monitor
    start_battery_monitor()

    try:
        while True:
            time.sleep(5)
            if not logic_thread.is_alive():
                logger.critical("Voice loop crashed. Restarting.")
                logic_thread = threading.Thread(
                    target=run_voice_loop,
                    args=(ctx, config, ctx.app_ui, api_set_state, _safe_mode_file),
                    daemon=True
                )
                logic_thread.start()
    except KeyboardInterrupt:
        os._exit(0)


if __name__ == "__main__":
    start_app()