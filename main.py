"""
PROJECT SEVEN - main.py (The Controller)
Version: 1.4.0 - Full modular monolith

Voice loop orchestrator.
All heavy lifting delegated to main_modules/.
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# numpy 2.0 removed numpy.iterable.
# sentence-transformers, faster-whisper, and chromadb embedding functions
# all call numpy.iterable internally. The embedded Python environment
# ships with numpy 2.x while the venv has 1.26.4.
# Patch at process start before any ML library loads.
try:
    import numpy as _np_patch
    if not hasattr(_np_patch, 'iterable'):
        _np_patch.iterable = lambda obj: hasattr(obj, '__iter__')
        print("[SYSTEM] numpy.iterable patched for numpy 2.x compatibility")
except Exception:
    pass

# ============================================================================
# PATH SETUP
# ============================================================================

_app_path = os.environ.get('SEVEN_APP_PATH', '')
if _app_path and _app_path not in sys.path:
    sys.path.insert(0, _app_path)

if _app_path:
    _embedded_python = os.path.join(_app_path, 'python', 'python.exe')
    _embedded_sp     = os.path.join(_app_path, 'python', 'Lib', 'site-packages')
    _embedded_lib    = os.path.join(_app_path, 'python', 'Lib')
    _embedded_dlls   = os.path.join(_app_path, 'python', 'DLLs')

    print(f"[SYSTEM] App path: {_app_path}")
    print(f"[SYSTEM] Site-packages exists: {os.path.exists(_embedded_sp)}")

    _running_embedded = (
        os.path.exists(_embedded_python) and
        os.path.normcase(sys.executable) == os.path.normcase(_embedded_python)
    )

    if not _running_embedded and os.path.exists(_embedded_python):
        _is_packaged = os.path.exists(
            os.path.join(_app_path, 'python', 'python311.dll')
        ) or os.path.exists(
            os.path.join(_app_path, 'python', 'python3.dll')
        )
        if _is_packaged:
            print(f"[SYSTEM] Wrong Python detected. Re-launching under embedded Python...")
            import subprocess
            result = subprocess.run(
                [_embedded_python] + sys.argv,
                env={**os.environ, 'SEVEN_RELAUNCHED': '1'}
            )
            sys.exit(result.returncode)

    for _p in [_embedded_sp, _embedded_lib, _embedded_dlls, os.path.join(_app_path, 'python')]:
        if os.path.exists(_p) and _p not in sys.path:
            sys.path.insert(0, _p)

_cwd = os.getcwd()
if _cwd not in sys.path:
    sys.path.insert(0, _cwd)

# In a packaged app cwd is NOT the app root.
# We must explicitly add the folder containing main.py
# so that main_modules, ears, brain, hands, memory are all importable.
_this_file_dir = os.path.dirname(os.path.abspath(__file__))
if _this_file_dir not in sys.path:
    sys.path.insert(0, _this_file_dir)
    print(f"[SYSTEM] Injected app root into sys.path: {_this_file_dir}")

# Force app root into sys.path so main_modules, ears, brain etc are always found
# This is the most critical path fix - without it all local imports fail
_app_root = _app_path if _app_path else os.path.dirname(os.path.abspath(__file__))
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)
print(f"[SYSTEM] App root in path: {_app_root}")


# ============================================================================
# PACKAGE CHECK
# ============================================================================

def _packages_ready():
    import subprocess
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    embedded_python = os.path.join(app_path, 'python', 'python.exe') if app_path else ''
    if app_path and os.path.exists(embedded_python):
        python = embedded_python
        print(f"[SYSTEM] Checking embedded Python: {embedded_python}")
    else:
        python = sys.executable
        print(f"[SYSTEM] Checking system Python: {python}")
    if app_path:
        sp = os.path.join(app_path, 'python', 'Lib', 'site-packages')
        print(f"[SYSTEM] Site-packages exists: {os.path.exists(sp)}")
    for pkg in ['fastapi', 'uvicorn', 'pyttsx3', 'speech_recognition']:
        result = subprocess.run([python, '-c', f'import {pkg.replace("-","_")}'], capture_output=True)
        if result.returncode != 0:
            print(f"[SYSTEM] Missing package: {pkg}")
            return False
    print("[SYSTEM] Core packages ready.")
    return True


def _detect_electron_mode():
    if os.environ.get('SEVEN_ELECTRON_MODE') == '1':
        return True
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    if app_path:
        if os.path.exists(os.path.join(app_path, 'python', 'python311.dll')):
            return True
        if os.path.exists(os.path.join(app_path, 'python', 'python3.dll')):
            return True
    if 'resources' in sys.executable.replace('\\', '/').lower() and 'app' in sys.executable.replace('\\', '/').lower():
        return True
    try:
        import tkinter as _tk_test
        _tk_test
        return False
    except ImportError:
        print("[SYSTEM] tkinter not available - forcing Electron mode")
        return True


IS_ELECTRON_MODE = _detect_electron_mode()
print(f"[SYSTEM] Electron mode: {IS_ELECTRON_MODE}")

if not _packages_ready():
    print("[SYSTEM] Core packages not installed - starting in pre-setup mode")
    from backend.startup import run_minimal_server
    run_minimal_server(host="127.0.0.1", port=7777)
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        os._exit(0)
    os._exit(0)


# ============================================================================
# STARTUP VALIDATION
# ============================================================================

def _validate_startup():
    """
    Validate all critical dependencies before starting Seven.
    Returns (ok: bool, errors: list[str], warnings: list[str])

    Critical failures abort startup.
    Warnings are logged but startup continues.
    """
    import socket
    errors   = []
    warnings = []

    # Check 1: Ollama running on port 11434
    # Non-fatal: Seven starts in degraded mode if Ollama is offline.
    # Layer 08 handles ConnectionError gracefully at response time.
    try:
        s = socket.create_connection(("127.0.0.1", 11434), timeout=2)
        s.close()
        print("[STARTUP] Ollama: running")
    except Exception:
        warnings.append(
            "Ollama is not running. Seven will start in degraded mode.\n"
            "  LLM responses will not work until Ollama is running.\n"
            "  Fix: Open the Ollama app or run 'ollama serve' in a terminal."
        )

    # Check 2: config.json accessible
    _appdata = os.environ.get('APPDATA', '')
    _cfg_path = os.path.join(_appdata, 'SEVEN', 'config.json')
    if not os.path.exists(_cfg_path):
        warnings.append(
            f"config.json not found at {_cfg_path}.\n"
            "  Seven will create a new one with defaults."
        )
    else:
        try:
            import json as _json
            with open(_cfg_path, 'r') as _f:
                _json.load(_f)
            print("[STARTUP] config.json: valid")
        except Exception as _ce:
            errors.append(
                f"config.json is corrupted: {_ce}\n"
                f"  Fix: Delete {_cfg_path} and restart Seven."
            )

    # Check 3: Port 7777 not already in use
    try:
        _ps = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _ps.settimeout(1)
        _result = _ps.connect_ex(("127.0.0.1", 7777))
        _ps.close()
        if _result == 0:
            errors.append(
                "Port 7777 is already in use.\n"
                "  Another Seven instance may be running.\n"
                "  Fix: Close the other instance or restart your computer."
            )
        else:
            print("[STARTUP] Port 7777: available")
    except Exception as _pe:
        print(f"[STARTUP] Port check failed: {_pe}")

    # Check 4: Disk space (warn if less than 500MB free)
    try:
        import shutil
        _free = shutil.disk_usage(_appdata or os.getcwd()).free
        _free_mb = _free / (1024 * 1024)
        if _free_mb < 100:
            errors.append(
                f"Critical: Only {_free_mb:.0f}MB disk space available.\n"
                "  Seven needs at least 100MB free to operate.\n"
                "  Free up disk space before starting."
            )
        elif _free_mb < 500:
            warnings.append(
                f"Low disk space: {_free_mb:.0f}MB available.\n"
                "  Recommended minimum is 500MB."
            )
        else:
            print(f"[STARTUP] Disk space: {_free_mb:.0f}MB available")
    except Exception as _de:
        print(f"[STARTUP] Disk check failed: {_de}")

    # Check 5: Memory directory writable
    try:
        _mem_dir = os.path.join(_appdata, 'SEVEN', 'seven_data', 'memory')
        os.makedirs(_mem_dir, exist_ok=True)
        _test_file = os.path.join(_mem_dir, '.write_test')
        with open(_test_file, 'w') as _tf:
            _tf.write('test')
        os.remove(_test_file)
        print("[STARTUP] Memory directory: writable")
    except Exception as _me:
        errors.append(
            f"Memory directory not writable: {_me}\n"
            "  Seven cannot save conversations or facts."
        )

    return len(errors) == 0, errors, warnings


# Run validation
print("[STARTUP] Validating dependencies...")
_startup_ok, _startup_errors, _startup_warnings = _validate_startup()

for _w in _startup_warnings:
    print(f"[STARTUP] WARNING: {_w}")

if not _startup_ok:
    print("\n" + "="*60)
    print("[STARTUP] SEVEN CANNOT START - CRITICAL ERRORS:")
    print("="*60)
    for _e in _startup_errors:
        print(f"\n  ERROR: {_e}")
    print("\n" + "="*60)
    print("[STARTUP] Fix the errors above and restart Seven.")
    print("="*60 + "\n")
    import time as _t
    _t.sleep(5)  # Give Electron time to read the output
    os._exit(1)

print("[STARTUP] All checks passed. Starting Seven...")

# Auto-trigger Ollama install on fresh install
# This runs in background so it does not block startup
# The setup wizard StepEnvironment polls /api/bootstrap/status for progress
def _auto_bootstrap():
    try:
        from backend.bootstrap import (
            is_ollama_installed,
            run_environment_setup,
        )
        import json as _bj
        _cfg_path = os.path.join(
            os.environ.get('APPDATA', ''), 'SEVEN', 'config.json'
        )
        _setup_done = False
        if os.path.exists(_cfg_path):
            try:
                with open(_cfg_path) as _f:
                    _setup_done = _bj.load(_f).get('setup_complete', False)
            except Exception:
                pass

        if not _setup_done and not is_ollama_installed():
            print("[STARTUP] Fresh install detected - auto-starting Ollama bootstrap")
            run_environment_setup()
        elif not is_ollama_installed():
            print("[STARTUP] Ollama missing - auto-starting bootstrap")
            run_environment_setup()
        else:
            print("[STARTUP] Ollama already installed - skipping auto-bootstrap")
    except Exception as _be:
        print(f"[STARTUP] Auto-bootstrap skipped: {_be}")

import threading as _bt
_bt.Thread(target=_auto_bootstrap, daemon=True, name="AutoBootstrap").start()

# ============================================================================
# FULL STARTUP
# ============================================================================

print("[SYSTEM] Packages ready - starting full Seven...")

import threading
import re

# Thread exception hook placeholder — real hook installed after logging setup below
# Do not reference 'logging' or 'logger' here — they are not imported yet

import colorama
from colorama import Fore
colorama.init()

import logging
import logging.handlers

def _setup_logging():
    """
    Configure rotating file logger for Seven.
    All modules that import this will share the same handlers.
    """
    _log_dir = os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'SEVEN', 'logs'
    )
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = os.path.join(_log_dir, 'seven.log')

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Rotating file handler - 5MB per file, keep 3 backups
    fh = logging.handlers.RotatingFileHandler(
        _log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # Console handler - INFO and above only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        '[%(levelname)s] %(name)s: %(message)s'
    ))

    # Silence noisy third-party loggers
    for noisy in [
        'chromadb', 'sentence_transformers', 'transformers','chromadb', 'sentence_transformers', 'transformers',
        'huggingface_hub', 'urllib3', 'urllib3.connectionpool',
        'urllib3.util', 'urllib3.util.retry', 'httpx',
        'uvicorn.access', 'sentry_sdk', 'sentry_sdk.errors',
        'sentry_sdk.transport', 'sentry_sdk.integrations',
        'huggingface_hub', 'urllib3', 'urllib3.connectionpool',
        'urllib3.util.retry', 'httpx', 'uvicorn.access',
        'sentry_sdk', 'sentry_sdk.errors', 'sentry_sdk.transport',
        'matplotlib', 'matplotlib.font_manager', 'matplotlib.pyplot',
        'comtypes', 'comtypes.client', 'comtypes._post_coinit',
        'comtypes._comobject', 'comtypes.client._managing',
        'comtypes.client._generate', 'h5py', 'h5py._conv',
        'numexpr', 'numexpr.utils', 'asyncio',
        'PIL', 'pyttsx3', 'speechbrain',
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if not root.handlers:
        root.addHandler(fh)
        root.addHandler(ch)

    return logging.getLogger('seven.main')

logger = _setup_logging()
logger.info("Seven starting up")

# Global exception hook - catches any unhandled exception anywhere
# Logs it with full traceback before Python would silently exit
def _global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Let KeyboardInterrupt through normally
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

sys.excepthook = _global_exception_handler

# Thread exception hook - catches crashes in background threads
def _thread_exception_handler(args):
    if args.exc_type == SystemExit:
        return
    logger.critical(
        f"Unhandled exception in thread {args.thread.name}",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )

threading.excepthook = _thread_exception_handler

# Sentry error tracking — captures crashes automatically
# Set SEVEN_SENTRY_DSN environment variable or add to config.json
# Get your DSN at sentry.io (free account)
def _setup_sentry():
    try:
        import sentry_sdk
        _dsn = None

        # Priority 1: environment variable
        _dsn = os.environ.get("SEVEN_SENTRY_DSN", "")

        # Priority 2: config.json
        if not _dsn:
            try:
                import json as _j
                _cfg = os.path.join(
                    os.environ.get('APPDATA', ''), 'SEVEN', 'config.json'
                )
                if os.path.exists(_cfg):
                    with open(_cfg) as _f:
                        _dsn = _j.load(_f).get("sentry_dsn", "")
            except Exception:
                pass

        if not _dsn:
            logger.info("Sentry not configured (no DSN). Skipping error tracking.")
            return

        sentry_sdk.init(
            dsn=_dsn,
            traces_sample_rate=0.1,     # 10% of transactions for performance
            profiles_sample_rate=0.1,
            environment="production" if not IS_ELECTRON_MODE else "electron",
            release=open(os.path.join(
                os.environ.get('SEVEN_APP_PATH', '.'), 'version.txt'
            )).read().strip() if os.path.exists(
                os.path.join(os.environ.get('SEVEN_APP_PATH', '.'), 'version.txt')
            ) else "unknown",
            before_send=lambda event, hint: _filter_sentry_event(event, hint),
        )
        logger.info("Sentry error tracking active")
    except ImportError:
        logger.info("Sentry SDK not installed. Run: pip install sentry-sdk")
    except Exception as _se:
        logger.warning(f"Sentry init failed: {_se}")


def _filter_sentry_event(event, hint):
    """
    Filter out known non-critical errors before sending to Sentry.
    Prevents noise from expected errors like numpy/tensorflow conflict.
    """
    _noise_patterns = [
        "np.complex_",
        "_ARRAY_API not found",
        "Stream closed",
        "9988",
        "9999",
        "WinError 995",
    ]
    try:
        exc = hint.get("exc_info")
        if exc and exc[1]:
            msg = str(exc[1])
            if any(p in msg for p in _noise_patterns):
                return None  # Drop this event
    except Exception:
        pass
    return event


_setup_sentry()

import config
from backend.api_server import start_api_server, set_state as api_set_state
from backend.admin_server import start_admin_server
import telemetry

from main_modules.startup.context             import SevenContext
from main_modules.startup.module_loader       import load_all_modules
from main_modules.startup.morning_brief       import speak_morning_brief
from main_modules.startup.daemon_launcher     import launch_schedule_daemon
from main_modules.startup.battery_monitor     import start_battery_monitor
from main_modules.startup.enrollment_handler  import (
    handle_pending_enrollment,
    handle_voice_enrollment_command,
)
from main_modules.handlers                    import register_all, execute_all
from main_modules.handlers.pre_executor       import pre_execute

app_ui = None


# ============================================================================
# SEVEN LOGIC THREAD
# ============================================================================

def seven_logic():
    global app_ui

    # Build shared context
    ctx = SevenContext()
    ctx.app_ui        = app_ui
    ctx.api_set_state = api_set_state
    ctx.config        = config

    # Load all AI modules onto ctx
    if not load_all_modules(ctx):
        return  # critical load failure

    # Wire speaking state to ears — prevents listen() processing audio
    # while Seven's TTS is playing (self-echo prevention)
    try:
        import ears.core as _ears_core
        _ears_core.set_speaking_fn(ctx.mouth.is_speaking)
        print(Fore.CYAN + "[SYSTEM] Speaking guard wired to ears")
    except Exception as _sg_err:
        print(Fore.YELLOW + f"[SYSTEM] Speaking guard not wired: {_sg_err}")

    # Voice loop configuration
    is_active = True
    interrupt_config   = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED  = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS    = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]

    interrupt_context = ctx.interrupt_context

    DEFAULT_WAKE_WORDS  = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    DEFAULT_PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                           "pause", "stop listening", "sleep", "silence", "stop",
                           "enough", "quiet", "shut up", "be quiet"]
    DEFAULT_KILL_WORDS  = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    def _word_match(text, phrases):
        """
        Word-boundary phrase match. Prevents false positives like
        'wait' matching inside 'waiting', or 'seven' matching inside 'seventeen'.
        """
        for phrase in phrases:
            if re.search(r'\b' + re.escape(phrase) + r'\b', text):
                return True
        return False

    def _get_voice_control_words():
        """
        Read wake/pause/resume/shutdown words from config, saved by
        Settings > Voice > Voice Control Commands. Falls back to
        defaults if nothing configured.

        Previously the Settings UI saved these to config.json but
        main.py never read them back, so the whole editor had zero
        effect on Seven's real behavior. This wires it up.
        """
        _identity = config.KEY.get("identity", {})
        _wake     = _identity.get("wake_words",     DEFAULT_WAKE_WORDS)
        _pause    = _identity.get("pause_words",    DEFAULT_PAUSE_WORDS)
        _resume   = _identity.get("resume_words",   [])
        _kill     = _identity.get("shutdown_words", DEFAULT_KILL_WORDS)
        # resume_words un-pauses Seven, same job WAKE_WORDS already does
        # when paused — combine rather than replace so customizing one
        # list doesn't silently drop the other's defaults
        _combined_wake = list(dict.fromkeys(_wake + _resume)) if _resume else _wake
        return _combined_wake, _pause, _kill

    # PTT listener
    _is_ptt_active_fn = lambda: True
    try:
        from ears.push_to_talk import start as _ptt_start, is_ptt_active
        _ptt_start()
        _is_ptt_active_fn = is_ptt_active
        print(Fore.CYAN + "[GATES] PTT keyboard listener started")
    except Exception as _ptt_err:
        print(Fore.YELLOW + f"[GATES] PTT init failed: {_ptt_err}")

    # Speak with interrupt helper
    def speak_with_interrupt(text):
        import time as _time
        if not INTERRUPT_ENABLED or (_time.time() - last_interrupt_time[0] < INTERRUPT_COOLDOWN):
            ctx.mouth.speak(text)
            return True
        stop_listening  = threading.Event()
        was_interrupted = threading.Event()
        def on_interrupt():
            was_interrupted.set()
            ctx.mouth_interrupt()
            last_interrupt_time[0] = _time.time()
        interrupt_thread = threading.Thread(
            target=ctx.listen_for_interrupt,
            args=(INTERRUPT_WORDS, on_interrupt, stop_listening),
            daemon=True
        )
        interrupt_thread.start()
        completed = ctx.mouth.speak(text)
        stop_listening.set()
        interrupt_thread.join(timeout=2)
        if was_interrupted.is_set():
            print("[SYSTEM] Speech interrupted")
            app_ui.update_status("INTERRUPTED", "#ffaa00")
            interrupt_context["was_interrupted"] = True
            interrupt_context["last_response"]   = text
            ctx.mouth.speak("Yeah?")
            return False
        return True

    ctx.speak_with_interrupt = speak_with_interrupt

    # Silence watcher
    _silence_watcher = None
    _last_topic_ref  = [None]
    try:
        from brain_modules.silence_watcher import SilenceWatcher
        _silence_watcher = SilenceWatcher(
            speak_fn=speak_with_interrupt,
            get_last_topic_fn=lambda: _last_topic_ref[0],
        )
        threading.Thread(target=_silence_watcher.start, daemon=True).start()
        ctx.silence_watcher = _silence_watcher
        print(Fore.CYAN + "[SYSTEM] Silence watcher started")
    except Exception as _sw_err:
        print(Fore.YELLOW + f"[SYSTEM] Silence watcher skipped: {_sw_err}")

    # Scheduler
    try:
        from backend.api_server import set_schedule_alert as _alert_fn
        ctx.scheduler_mod.start_background(speak_fn=ctx.mouth.speak, alert_fn=_alert_fn)
        print(Fore.GREEN + "[SYSTEM] Scheduler started with banner support")
    except Exception:
        ctx.scheduler_mod.start_background(speak_fn=ctx.mouth.speak)
        print(Fore.YELLOW + "[SYSTEM] Scheduler started without banner support")

    sched_count = ctx.scheduler_mod.get_active_count()
    if sched_count > 0:
        print(Fore.CYAN + f"[SYSTEM] Scheduler: {sched_count} active schedules.")

    # Launch daemons immediately — before morning brief
    # Daemons are independent processes, no reason to delay
    launch_schedule_daemon()

    from main_modules.startup.trigger_daemon_launcher import (
        launch_trigger_daemon,
        launch_overlay_daemon,
    )
    print(Fore.CYAN + "[SYSTEM] Launching trigger daemon...")
    launch_trigger_daemon()
    print(Fore.CYAN + "[SYSTEM] Launching overlay daemon...")
    launch_overlay_daemon()
    print(Fore.CYAN + "[SYSTEM] Daemons launched")

    # Morning brief (after daemons are running)
    speak_morning_brief(ctx, config)    

    # Register handlers
    try:
        register_all(ctx)
    except Exception as _hr_err:
        print(Fore.RED + f"[HANDLERS] Registration failed: {_hr_err}")
        import traceback; traceback.print_exc()

    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    while True:
        try:
            # Enrollment check
            if handle_pending_enrollment(ctx, api_set_state):
                continue

            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
                api_set_state("listening", True)
                api_set_state("thinking",  False)
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")
                api_set_state("listening", False)

            user_input, audio_path = ctx.listen()
            if not user_input:
                # Battery alert check
                try:
                    from backend.api_server import get_state as _gs
                    if _gs().get("battery_alert_pending"):
                        from backend.api_server import set_state as _ss
                        _bat_msg = _gs().get("battery_alert_msg") or "Battery low. Please plug in."
                        _ss("battery_alert_pending", False)
                        _ss("battery_alert_msg", "")
                        speak_with_interrupt(_bat_msg)
                except Exception:
                    pass
                continue

            # Wake / pause / shutdown words — reloaded live so Settings
            # changes take effect without restarting Seven
            WAKE_WORDS, PAUSE_WORDS, KILL_WORDS = _get_voice_control_words()

            # Voice gates
            _vg          = config.KEY.get("voice_gates", {})
            _ptt_enabled = _vg.get("push_to_talk",   {}).get("enabled", False)
            _ww_enabled  = _vg.get("wake_word",      {}).get("enabled", False)
            _ww_words    = _vg.get("wake_word",      {}).get("words", ["hey seven", "ok seven", "seven"])
            _sv_enabled  = _vg.get("speaker_verify", {}).get("enabled", False)

            try:
                from ears.push_to_talk import set_enabled as _ptt_set
                _ptt_set(_ptt_enabled)
            except Exception:
                pass

            if _ptt_enabled and not _is_ptt_active_fn():
                print(Fore.YELLOW + "[GATE1-PTT] Shift not held — audio discarded")
                continue

            if _silence_watcher:
                _silence_watcher.on_user_spoke()
            _last_topic_ref[0] = user_input

            if _ww_enabled:
                try:
                    from ears.wake_word import check_and_strip as _ww_check
                    user_input, _ww_found = _ww_check(user_input, _ww_words)
                    if not _ww_found:
                        print(Fore.YELLOW + "[GATE2-WW] No wake word — discarded")
                        continue
                    if user_input and len(user_input.strip()) < 2:
                        print(Fore.YELLOW + "[GATE2-WW] Wake word only, no command — discarded")
                        continue
                except Exception as _ww_err:
                    print(Fore.YELLOW + f"[GATE2-WW] Error: {_ww_err}")

            text_lower = user_input.lower().strip()

            _hallucinations = {
                "thank you", "thanks", "thank you.", "thanks.",
                "you", "the", "bye", "bye.", "yes", "no",
                "thanks for watching", "thank you for watching",
                ".", "..", "...", " ", ""
            }
            if text_lower in _hallucinations or len(text_lower) < 2:
                print(Fore.YELLOW + f"[EARS] Filtered: '{user_input}'")
                continue

            # Interrupt resume
            if interrupt_context["was_interrupted"]:
                resume_words = ["continue", "resume", "go on", "go ahead", "keep going", "carry on"]
                if _word_match(text_lower, resume_words):
                    old_response = interrupt_context["last_response"]
                    old_input    = interrupt_context["last_input"]
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
                    if old_response and old_input:
                        resume_prompt = (
                            f"I was interrupted while answering: '{old_input}'. "
                            f"I had said: '{old_response}'. "
                            f"Continue from where I left off naturally."
                        )
                        response = ctx.brain.think(resume_prompt, speaker_id="default")
                        if response:
                            speak_with_interrupt(response)
                        else:
                            ctx.mouth.speak("Sorry, lost my train of thought.")
                    else:
                        ctx.mouth.speak("Sorry, lost my train of thought. Ask me again?")
                else:
                    interrupt_context.update({"was_interrupted": False, "last_response": None, "last_input": None})
                continue

            # Speaker ID
            # audio_path is "__voice__" sentinel when input came from microphone.
            # It is None when input came from chat API.
            _came_from_voice = (audio_path == "__voice__")
            speaker_id = "default"

            if _came_from_voice:
                if ctx.is_voice_id_enabled():
                    # Voice ID enabled — identify the speaker
                    # Note: voice_id needs a real audio file.
                    # For now, use "voice_user" as the speaker ID when
                    # Voice ID is disabled but input came from mic.
                    speaker_id = ctx.identify_speaker(audio_path) if audio_path != "__voice__" else "voice_user"
                else:
                    # Voice ID disabled — mark as voice_user so brain.py
                    # saves with source="voice" not source="chat"
                    speaker_id = "voice_user"
                print(Fore.CYAN + f"[VOICE ID] Speaker: {speaker_id}")
                api_set_state("current_speaker", speaker_id)

            if _sv_enabled:
                if not ctx.is_voice_id_enabled():
                    print(Fore.YELLOW + "[GATE3-SV] Enabled but no voice enrolled — audio discarded")
                    continue
                if speaker_id == "unknown":
                    print(Fore.YELLOW + "[GATE3-SV] Unknown speaker — audio discarded")
                    continue
            elif not _sv_enabled and speaker_id == "unknown":
                # Voice ID disabled — log only, do not block
                pass

            # Double-speech lock
            # If Seven is already speaking (reminder, alert, etc.) and user speaks,
            # do not process voice input until current speech finishes.
            if ctx.mouth.is_speaking():
                print(Fore.YELLOW + "[EARS] Speaking in progress — input held")
                import time as _hold
                _hold.sleep(0.5)
                continue

            # Voice enrollment trigger
            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                handle_voice_enrollment_command(ctx, api_set_state)
                continue

            # Kill / wake / pause
            if _word_match(text_lower, KILL_WORDS):
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                ctx.mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            if _word_match(text_lower, WAKE_WORDS):
                if not is_active:
                    is_active = True
                    ctx.mouth.speak("Listening.")
                    app_ui.update_status("RESUMED", "#00ff00")
                    if _silence_watcher:
                        _silence_watcher.set_paused(False)
                continue

            if is_active and _word_match(text_lower, PAUSE_WORDS):
                is_active = False
                ctx.mouth.speak("Standing by.")
                app_ui.update_status("PAUSED", "#555555")
                if _silence_watcher:
                    _silence_watcher.set_paused(True)
                api_set_state("user_text",  "")
                api_set_state("seven_text", "")
                continue

            if not is_active:
                continue

            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status("THINKING...", "#ff00ff")
            api_set_state("thinking",  True)
            api_set_state("listening", False)
            api_set_state("user_text", user_input)
            api_set_state("seven_text", "")

            # Facts limit check
            if any(t in user_input.lower() for t in [
                "remember that", "remember this", "my name is", "call me",
                "i love", "i like", "i prefer", "i am a",
                "i work at", "i study at", "my favorite", "my favourite"
            ]):
                try:
                    import voice_limits
                    if ctx.seven_memory:
                        _current_facts = ctx.seven_memory.user_facts.count()
                        _fact_ok, _fact_msg = voice_limits.check("facts_limit", _current_facts)
                        if not _fact_ok:
                            api_set_state("speaking", True)
                            ctx.mouth.speak(_fact_msg)
                            api_set_state("speaking", False)
                            app_ui.update_status("PLAN LIMIT", "#ffaa00")
                            continue
                except Exception:
                    pass

            # Web search hint
            _web_needed = any(w in user_input.lower() for w in [
                "weather", "news", "price", "score", "latest",
                "what is", "who is", "when did", "how much",
                "tell me about", "explain", "define",
            ])
            _is_convo = any(w in user_input.lower() for w in [
                "yourself", "you are", "about you", "who are you",
                "what are you", "place", "feel", "think",
            ])
            if _web_needed and not _is_convo and len(user_input.split()) > 5:
                import random as _rand
                ctx.mouth.speak(_rand.choice(["One moment.", "Let me check.", "Checking."]))

            # Brain response
            response = ctx.brain.think(user_input, speaker_id=speaker_id)
            telemetry.log_activity()

            if response == "":
                continue
            if not response:
                response = "Processing error."

            is_streaming = (
                isinstance(response, tuple) and
                len(response) == 2 and
                response[0] == "__STREAM__"
            )
            completed = True

            # Filtering and save logic lives in brain._save_conversation().
            # main.py only handles the streaming post-speak save via store_voice_turn().

            speech_part = response
            if isinstance(response, str) and "###" in response:
                speech_part = response.split("###")[0].strip()

            if not is_streaming and speech_part:
                api_set_state("seven_text", speech_part)

            # Update context for handlers
            ctx.speaker_id  = speaker_id
            ctx.speech_part = speech_part
            ctx.user_input  = user_input

            # Pre-execute
            if isinstance(response, str):
                try:
                    pre_execute(response, ctx)
                except Exception as _pe_err:
                    print(Fore.RED + f"[PRE-EXEC] Error: {_pe_err}")

            api_set_state("speaking", True)
            if _silence_watcher:
                _silence_watcher.on_seven_speaking(True)

            if is_streaming:
                _, sentence_gen = response
                interrupt_context["last_input"] = user_input
                full_parts = []
                for sentence in sentence_gen:
                    full_parts.append(sentence)
                    if "###" in sentence:
                        continue
                    api_set_state("seven_text", " ".join(p for p in full_parts if "###" not in p))
                    completed = speak_with_interrupt(sentence)
                    if not completed:
                        break
                response    = " ".join(full_parts)
                speech_part = response.split("###")[0].strip() if "###" in response else response
                ctx.speech_part = speech_part
                app_ui.update_status(
                    "INTERRUPTED" if not completed else speech_part[:80],
                    "#ffaa00" if not completed else "#00ccff"
                )
            elif speech_part:
                interrupt_context["last_input"] = user_input
                completed = speak_with_interrupt(speech_part)
                app_ui.update_status(
                    "INTERRUPTED" if not completed else speech_part,
                    "#ffaa00" if not completed else "#00ccff"
                )

            api_set_state("speaking", False)
            api_set_state("thinking", False)
            if _silence_watcher:
                _silence_watcher.on_seven_speaking(False)

            # Store conversation - handled by brain.think() for non-streaming.
            # Streaming path: brain.think() skips save (text not available at that point).
            # We save streaming turns here after the generator is fully consumed.
            if is_streaming and isinstance(response, str) and ctx.seven_memory:
                try:
                    import brain as _brain_mod
                    _brain_mod.store_voice_turn(
                        prompt_text=user_input,
                        response_text=response,
                        speaker_id=speaker_id,
                        was_interrupted=not completed,
                    )
                except Exception as _sv_err:
                    print(Fore.RED + f"[MEMORY] Streaming save error: {_sv_err}")

            if not isinstance(response, str):
                continue

            # Dispatch to handlers
            try:
                execute_all(response, ctx)
            except Exception as _hd_err:
                print(Fore.RED + f"[HANDLERS] Dispatch error: {_hd_err}")
                import traceback; traceback.print_exc()

            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

        except OSError as e:
            if "Stream closed" in str(e) or "9988" in str(e) or "9999" in str(e):
                logger.warning(f"Mic device change detected: {e}")
                print(Fore.YELLOW + f"[EARS] Mic device change detected — recovering")
                import time as _rec_t
                _rec_t.sleep(1.5)
                try:
                    from ears.core import _do_initial_calibration
                    _do_initial_calibration()
                except Exception:
                    pass
            else:
                print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
                import traceback; traceback.print_exc()
            app_ui.update_status("LISTENING...", "#00ff00")
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            print(Fore.RED + f"[CRITICAL ERROR] Main loop: {e}")
            import traceback; traceback.print_exc()
            app_ui.update_status("ERROR RECOVERED", "#ff0000")


# ============================================================================
# START APP
# ============================================================================

def start_app():
    global app_ui

    is_electron = IS_ELECTRON_MODE

    if is_electron:
        print(Fore.CYAN + "[SYSTEM] Running in ELECTRON mode")
    else:
        print(Fore.YELLOW + "[SYSTEM] Running in STANDALONE mode")

    # ── Step 1: API server FIRST ─────────────────────────────────────────
    # Electron polls /api/status every second with a 2 min timeout.
    # The server MUST be up and responding before any heavy module loads.
    # Heavy modules (ChromaDB, resemblyzer) can take 2-5 min on first run.
    start_api_server(host="127.0.0.1", port=7777)
    logger.info("API server started on port 7777")
    print(Fore.GREEN + "[SYSTEM] API server up on port 7777")

    # Give uvicorn 1.5 seconds to bind the port before anything polls it
    import time as _startup_time
    _startup_time.sleep(1.5)
    print(Fore.GREEN + "[SYSTEM] API server confirmed ready")

    # ── Step 2: Non-blocking services ────────────────────────────────────
    try:
        telemetry.start_telemetry()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Telemetry skipped: {e}")

    try:
        start_admin_server()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Admin server skipped: {e}")

    # ── Step 3: DummyUI + voice logic thread ─────────────────────────────
    # Voice logic runs in a background thread so it never blocks the
    # API server. Heavy module loading happens inside seven_logic via
    # module_loader which also uses background threads for heavy models.
    class DummyUI:
        def update_status(self, text, color):
            try:
                api_set_state("status_text", text)
                api_set_state("status_color", color)
            except Exception:
                pass
        def close(self):
            print(Fore.RED + "[SYSTEM] Shutdown requested")
            os._exit(0)

    app_ui = DummyUI()
    logic_thread = threading.Thread(target=seven_logic, daemon=True)
    logic_thread.start()

    if is_electron:
        print(Fore.GREEN + "[SYSTEM] Backend running. Electron handles UI.")
    else:
        print(Fore.GREEN + "[SYSTEM] Backend running. Open http://localhost:5173 in browser.")

    start_battery_monitor()

    try:
        import time
        while True:
            time.sleep(5)
            if not logic_thread.is_alive():
                logger.critical("Voice loop crashed. Restarting.")
                print(Fore.RED + "[WATCHDOG] Voice loop crashed. Restarting...")
                logic_thread = threading.Thread(target=seven_logic, daemon=True)
                logic_thread.start()
    except KeyboardInterrupt:
        print(Fore.RED + "\n[SYSTEM] Interrupted by user")
        os._exit(0)


if __name__ == "__main__":
    start_app()