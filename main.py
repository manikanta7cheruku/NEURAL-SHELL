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

# ============================================================================
# CRITICAL: Visual C++ Redistributable Check (MUST run before ALL imports)
# numpy, torch, chromadb, and faster-whisper all require msvcp140.dll.
# Fresh Windows machines often lack this DLL, causing silent 0xC0000005 crashes.
# This check auto-downloads and installs VC++ if missing.
# ============================================================================
def _ensure_vcredist():
    """Check for VC++ 2015-2022 runtime DLLs. Auto-install if missing."""
    if sys.platform != 'win32':
        return

    import ctypes
    import os as _os

    # Check for the two critical DLLs
    dlls_needed = ["msvcp140.dll", "vcruntime140.dll"]
    missing = []
    for dll in dlls_needed:
        try:
            ctypes.CDLL(dll)
        except OSError:
            missing.append(dll)

    if not missing:
        return  # All DLLs present

    print(f"[SYSTEM] CRITICAL: Missing Visual C++ runtime DLLs: {missing}")
    print("[SYSTEM] Downloading Visual C++ Redistributable from Microsoft...")

    import urllib.request
    import tempfile
    import subprocess

    vc_url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    vc_installer = _os.path.join(tempfile.gettempdir(), "vc_redist.x64.exe")

    try:
        # Download VC++ installer
        req = urllib.request.Request(
            vc_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(vc_installer, "wb") as f:
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)

        print(f"[SYSTEM] Downloaded VC++ installer ({_os.path.getsize(vc_installer)} bytes)")

        # Install silently — /install /quiet /norestart
        # This requires admin elevation which ShellExecuteW handles
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", vc_installer, "/install /quiet /norestart", None, 0
            )
            if ret > 32:
                print("[SYSTEM] VC++ installation started. Waiting for completion...")
                import time
                # Wait up to 2 minutes for installation
                for _ in range(120):
                    time.sleep(1)
                    try:
                        ctypes.CDLL("msvcp140.dll")
                        print("[SYSTEM] Visual C++ Redistributable installed successfully.")
                        return
                    except OSError:
                        continue
                print("[SYSTEM] WARNING: VC++ install may still be in progress.")
            else:
                print(f"[SYSTEM] VC++ install declined by user (code {ret}).")
                print("[SYSTEM] Seven may crash without Visual C++ Redistributable.")
        except Exception as e:
            print(f"[SYSTEM] VC++ install error: {e}")

    except Exception as e:
        print(f"[SYSTEM] Failed to download VC++ Redistributable: {e}")
        print("[SYSTEM] Please install manually from: https://aka.ms/vs/17/release/vc_redist.x64.exe")

_ensure_vcredist()

# numpy 2.0 removed numpy.iterable.
# sentence-transformers, faster-whisper, and chromadb embedding functions
# all call numpy.iterable internally. The embedded Python environment
# ships with numpy 2.x while the venv has 1.26.4.
# Patch at process start before any ML library loads.
# Silence noisy env vars before any ML library loads
import os as _os_early
_os_early.environ.setdefault('TF_CPP_MIN_LOG_LEVEL',             '3')
_os_early.environ.setdefault('TF_ENABLE_ONEDNN_OPTS',            '0')
_os_early.environ.setdefault('TRANSFORMERS_VERBOSITY',            'error')
_os_early.environ.setdefault('TRANSFORMERS_NO_ADVISORY_WARNINGS', '1')
_os_early.environ.setdefault('TOKENIZERS_PARALLELISM',            'false')
_os_early.environ.setdefault('PYTORCH_JIT',                       '0')

# Silence noisy loggers before they are imported
import logging as _early_logging
for _noisy_logger in [
    'tensorflow', 'torch', 'torch._dynamo',
    'nv_one_logger', 'graphviz', 'datasets',
    'huggingface_hub', 'transformers',
    'httpcore', 'httpx',
]:
    _early_logging.getLogger(_noisy_logger).setLevel(_early_logging.ERROR)

# Safe numpy compatibility patch — completely isolated and crash-proof.
# Never imports heavy libraries (transformers/torch) at the top level of main.py.
try:
    import warnings as _np_warnings
    import numpy as _np_patch
    if hasattr(_np_patch, '__version__'):
        _np_v = str(_np_patch.__version__)
        if _np_v.startswith('2.'):
            if not hasattr(_np_patch, 'iterable'):
                _np_patch.iterable = lambda obj: hasattr(obj, '__iter__')
            if not hasattr(_np_patch, 'complex'):
                _np_patch.complex = complex
            if not hasattr(_np_patch, 'float'):
                _np_patch.float = float
            if not hasattr(_np_patch, 'int'):
                _np_patch.int = int
            if not hasattr(_np_patch, 'bool'):
                _np_patch.bool = bool
            print("[SYSTEM] numpy 2.x compatibility patches applied")
        else:
            _np_warnings.filterwarnings('ignore', category=FutureWarning, module='numpy')
            _np_warnings.filterwarnings('ignore', message='.*np\\.bool.*')
            _np_warnings.filterwarnings('ignore', message='.*np\\.int.*')
            _np_warnings.filterwarnings('ignore', message='.*np\\.float.*')
            _np_warnings.filterwarnings('ignore', message='.*np\\.complex.*')
except Exception:
    pass

# ============================================================================
# PATH SETUP — Must be the very first thing after imports
# ============================================================================

# Inject app root IMMEDIATELY — before any other path logic.
# This is line 1 of path setup intentionally.
# In a packaged app the working directory is NOT the app root.
# __file__ is always reliable — it points to main.py itself.
_this_file_dir = os.path.dirname(os.path.abspath(__file__))
if _this_file_dir not in sys.path:
    sys.path.insert(0, _this_file_dir)
print(f"[SYSTEM] App root injected: {_this_file_dir}")

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
# Note: _this_file_dir already injected at top of PATH SETUP block


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

    cflags = 0x08000000 if sys.platform == 'win32' else 0

    # 1. Verify numpy health explicitly — detects corrupted numpy installs immediately
    np_test = subprocess.run(
        [python, '-c', 'import numpy as np; _ = np.__version__; _ = np.ndarray'],
        capture_output=True,
        creationflags=cflags
    )
    if np_test.returncode != 0:
        print("[SYSTEM] numpy is corrupted or unimportable — entering pre-setup recovery mode")
        return False

    # 2. Check core server packages
    for pkg in ['fastapi', 'uvicorn', 'pyttsx3', 'speech_recognition']:
        result = subprocess.run(
            [python, '-c', f'import {pkg.replace("-","_")}'],
            capture_output=True,
            creationflags=cflags
        )
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

# Run validation (moved to main_modules/startup/validator.py)
print("[STARTUP] Validating dependencies...")
from main_modules.startup.validator import validate_startup
_startup_ok, _startup_errors, _startup_warnings = validate_startup()

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

# Bootstrap is handled exclusively by the setup wizard (StepEnvironment.jsx).
# Do NOT auto-start downloads on app launch — it crashes the process if
# torch/numpy are loading simultaneously.
try:
    from backend.bootstrap import is_ollama_installed
    if is_ollama_installed():
        print("[STARTUP] Ollama: installed")
    else:
        print("[STARTUP] Ollama: not found (setup wizard will handle installation)")
except Exception:
    print("[STARTUP] Ollama check skipped")

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
        # ML frameworks
        'tensorflow', 'tensorflow.python', 'tensorflow.core',
        'torch', 'torch._dynamo', 'torch._inductor',
        'torch._native.dsl_registry',
        # NVidia / CUDA loggers
        'nv_one_logger', 'nv_one_logger.api.config',
        'nv_one_logger.exporter.export_config_manager',
        'nv_one_logger.training_telemetry.api.training_telemetry_provider',
        'nv_one_logger.recorder.default_recorder',
        # Graph tools
        'graphviz', 'graphviz._tools',
        # HuggingFace
        'datasets', 'datasets.builder', 'datasets.info',
        'huggingface_hub', 'huggingface_hub.utils',
        'transformers', 'transformers.modeling_utils',
        'sentence_transformers',
        # ChromaDB
        'chromadb', 'chromadb.api', 'chromadb.db',
        # HTTP
        'urllib3', 'urllib3.connectionpool', 'urllib3.util',
        'urllib3.util.retry', 'httpx', 'httpcore',
        # Uvicorn
        'uvicorn.access', 'uvicorn.error',
        # Sentry
        'sentry_sdk', 'sentry_sdk.errors',
        'sentry_sdk.transport', 'sentry_sdk.integrations',
        # Audio / ML
        'faster_whisper',
        'speechbrain',
        'PIL', 'pyttsx3',
        # System
        'matplotlib', 'matplotlib.font_manager',
        'comtypes', 'comtypes.client',
        'comtypes._post_coinit', 'comtypes._comobject',
        'h5py', 'numexpr', 'asyncio',
        'keras', 'keras.src',
        'absl', 'absl.logging',
    ]:
        logging.getLogger(noisy).setLevel(logging.ERROR)

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
from main_modules.startup.daemon_launcher     import launch_schedule_daemon, launch_panel_server
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
    if _safe_mode:
        print(Fore.YELLOW + "[SYSTEM] Safe mode active — ML modules not loaded")
        ctx.brain = None
        ctx.mouth = None
        ctx.listen = lambda: (None, None)
        api_set_state("status_text", "SAFE MODE — Voice disabled")
        api_set_state("status_color", "#ffaa00")
    else:
        try:
            api_set_state("status_text", "Loading AI modules...")
            api_set_state("status_color", "#ffaa00")
        except Exception:
            pass

        if not load_all_modules(ctx):
            print(Fore.RED + "[SYSTEM] ML loading failed.")
            try:
                api_set_state("status_text", "ERROR: AI modules failed to load")
                api_set_state("status_color", "#ff0000")
                api_set_state("listening", False)
                with open(_safe_mode_file, 'w') as _sf:
                    _sf.write(str(time.time()))
                print(Fore.RED + "[SYSTEM] Safe mode flag created. Restart to retry.")
            except Exception:
                pass
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
    launch_panel_server()

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

    # Speak startup greeting so user knows Seven is now active and listening
    try:
        import datetime as _dt
        _hour = _dt.datetime.now().hour
        if _hour < 5:
            _time_greet = "Good evening"
        elif _hour < 12:
            _time_greet = "Good morning"
        elif _hour < 17:
            _time_greet = "Good afternoon"
        else:
            _time_greet = "Good evening"

        _user_name = config.KEY.get("identity", {}).get("user_name", "")
        if _user_name:
            _startup_msg = f"{_time_greet}, {_user_name}. Seven is online and ready."
        else:
            _startup_msg = f"{_time_greet}. Seven is online and ready."

        ctx.mouth.speak(_startup_msg)
        api_set_state("seven_text", _startup_msg)
    except Exception as _sg_err:
        print(Fore.YELLOW + f"[SYSTEM] Startup greeting skipped: {_sg_err}")

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

            # Store conversation turns after streaming completion
            if is_streaming and isinstance(response, str):
                try:
                    import brain as _brain_mod
                    _brain_mod.store_voice_turn(
                        prompt_text=user_input,
                        response_text=response,
                        speaker_id=speaker_id,
                        was_interrupted=not completed,
                    )
                except Exception as _sv_err:
                    print(Fore.YELLOW + f"[MEMORY] Streaming voice save skipped: {_sv_err}")

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
    # This MUST succeed. If it fails, nothing else matters.
    try:
        start_api_server(host="127.0.0.1", port=7777)
        logger.info("API server started on port 7777")
        print(Fore.GREEN + "[SYSTEM] API server up on port 7777")
    except Exception as _api_err:
        print(Fore.RED + f"[SYSTEM] CRITICAL: API server failed to start: {_api_err}")
        print(Fore.RED + "[SYSTEM] Retrying in 3 seconds...")
        import time as _t
        _t.sleep(3)
        try:
            start_api_server(host="127.0.0.1", port=7777)
            print(Fore.GREEN + "[SYSTEM] API server started on retry")
        except Exception as _api_err2:
            print(Fore.RED + f"[SYSTEM] API server retry failed: {_api_err2}")
            print(Fore.RED + "[SYSTEM] Seven cannot function without the API server.")
            import time as _t2
            _t2.sleep(5)
            os._exit(1)

    import time as _startup_time
    _startup_time.sleep(0.8)
    print(Fore.GREEN + "[SYSTEM] API server confirmed ready")

    # ── Step 2: Check if setup is complete ───────────────────────────────
    import json as _setup_json
    _appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    _cfg_file = os.path.join(_appdata, 'SEVEN', 'config.json')
    _is_setup_done = False
    try:
        if os.path.exists(_cfg_file):
            with open(_cfg_file, 'r', encoding='utf-8') as _f:
                _is_setup_done = _setup_json.load(_f).get('setup_complete', False)
    except Exception:
        pass

    # Also check if critical dependencies are still present.
    # Users may uninstall Ollama or reinstall Seven — in those cases we must
    # re-run setup even though config.json says setup is complete.
    _dependencies_ok = False
    if _is_setup_done:
        try:
            from backend.bootstrap import is_ollama_installed
            _dependencies_ok = is_ollama_installed()
            if not _dependencies_ok:
                print(Fore.YELLOW + "[SYSTEM] Setup was marked complete but Ollama is missing — reverting to setup mode")
                # Clear the flag so wizard runs again
                try:
                    with open(_cfg_file, 'r', encoding='utf-8') as _f:
                        _cfg_data = _setup_json.load(_f)
                    _cfg_data['setup_complete'] = False
                    with open(_cfg_file, 'w', encoding='utf-8') as _f:
                        _setup_json.dump(_cfg_data, _f, indent=2)
                    _is_setup_done = False
                except Exception as _cfg_err:
                    print(Fore.YELLOW + f"[SYSTEM] Could not update config: {_cfg_err}")
        except Exception as _dep_err:
            print(Fore.YELLOW + f"[SYSTEM] Dependency check failed: {_dep_err}")

    # ── ML READINESS CHECK ──────────────────────────────────────────────
    _ml_ready = False
    if _is_setup_done:
        try:
            import subprocess as _sp
            _test_python = sys.executable
            # In packaged mode, use the embedded Python for the check
            if _app_path:
                _emb = os.path.join(_app_path, 'python', 'python.exe')
                if os.path.exists(_emb):
                    _test_python = _emb
            _ml_test = _sp.run(
                [_test_python, '-c',
                 'import numpy; import numpy._utils; print("OK")'],
                capture_output=True, text=True, timeout=15,
                creationflags=0x08000000 if sys.platform == 'win32' else 0
            )
            if _ml_test.returncode == 0 and 'OK' in _ml_test.stdout:
                _ml_ready = True
                print("[SYSTEM] ML packages verified — entering full mode")
            else:
                _stderr = _ml_test.stderr.strip()[:200] if _ml_test.stderr else "no output"
                print(Fore.YELLOW + f"[SYSTEM] ML packages broken: {_stderr}")
                print(Fore.YELLOW + "[SYSTEM] Falling back to onboarding mode for repair")
        except Exception as _ml_err:
            # If the check itself crashes, assume ML is fine and let full mode try.
            # It is better to attempt full mode and fail gracefully than to
            # incorrectly force setup mode on a working installation.
            print(Fore.YELLOW + f"[SYSTEM] ML check inconclusive: {_ml_err} — assuming OK")
            _ml_ready = True

    if not _is_setup_done or not _ml_ready:
        # ── ONBOARDING MODE ─────────────────────────────────────────────
        # Only the API server runs. No voice loop, no ML imports, no daemons.
        # This prevents 0xC0000005 crashes from concurrent DLL loading.
        if _is_setup_done and not _ml_ready:
            print(Fore.CYAN + "[SYSTEM] Setup was complete but ML is broken — running in Repair mode")
        else:
            print(Fore.CYAN + "[SYSTEM] Setup not complete — running in Onboarding mode")
        print(Fore.GREEN + "[SYSTEM] API ready for Setup Wizard on port 7777")

        try:
            import time
            while True:
                time.sleep(1)
                # Re-read config from disk (in-memory config.KEY may be stale)
                try:
                    with open(_cfg_file, 'r', encoding='utf-8') as _f:
                        _live = _setup_json.load(_f)
                    if _live.get('setup_complete', False):
                        print(Fore.GREEN + "[SYSTEM] Setup completed. Restarting into full Seven mode...")
                        time.sleep(0.8)
                        os._exit(0)  # Electron will restart Python automatically
                except Exception:
                    pass
        except KeyboardInterrupt:
            print(Fore.RED + "\n[SYSTEM] Interrupted by user")
            os._exit(0)
        return

    # ── FULL MODE (only after setup is complete) ─────────────────────────
    # Check for safe mode flag (created after repeated crashes)
    _safe_mode_file = os.path.join(_appdata, 'SEVEN', 'safe_mode.flag')
    _safe_mode = os.path.exists(_safe_mode_file)
    if _safe_mode:
        print(Fore.YELLOW + "[SYSTEM] SAFE MODE: Skipping ML module loading due to previous crashes")
        print(Fore.YELLOW + "[SYSTEM] Voice and AI features will be unavailable until the issue is resolved")
        print(Fore.YELLOW + "[SYSTEM] Delete %APPDATA%\\SEVEN\\safe_mode.flag to exit safe mode")

    print(Fore.GREEN + "[SYSTEM] Setup complete. Starting full Seven...")

    try:
        telemetry.start_telemetry()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Telemetry skipped: {e}")

    try:
        start_admin_server()
    except Exception as e:
        print(Fore.YELLOW + f"[SYSTEM] Admin server skipped: {e}")

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