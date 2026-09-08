"""
main_modules/startup/system_init.py
System initialization — runs before anything else.

Extracted from main.py to keep the entry point under 300 lines.
Handles: VC++ check, numpy patch, logging, Sentry.
"""
import sys
import os
import logging
import logging.handlers


def ensure_vcredist():
    """Check for VC++ 2015-2022 runtime DLLs. Auto-install if missing."""
    if sys.platform != 'win32':
        return

    import ctypes

    dlls_needed = ["msvcp140.dll", "vcruntime140.dll"]
    missing = []
    for dll in dlls_needed:
        try:
            ctypes.CDLL(dll)
        except OSError:
            missing.append(dll)

    if not missing:
        return

    print(f"[SYSTEM] CRITICAL: Missing Visual C++ runtime DLLs: {missing}")
    print("[SYSTEM] Downloading Visual C++ Redistributable...")

    import urllib.request
    import tempfile
    import subprocess

    vc_url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    vc_installer = os.path.join(tempfile.gettempdir(), "vc_redist.x64.exe")

    try:
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

        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", vc_installer,
                "/install /quiet /norestart", None, 0
            )
            if ret > 32:
                import time
                for _ in range(120):
                    time.sleep(1)
                    try:
                        ctypes.CDLL("msvcp140.dll")
                        print("[SYSTEM] VC++ installed successfully.")
                        return
                    except OSError:
                        continue
        except Exception as e:
            print(f"[SYSTEM] VC++ install error: {e}")
    except Exception as e:
        print(f"[SYSTEM] Failed to download VC++: {e}")


def apply_numpy_patch():
    """Apply numpy 2.x compatibility patches before any ML import."""
    import os as _os
    _os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    _os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
    _os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
    _os.environ.setdefault('TRANSFORMERS_NO_ADVISORY_WARNINGS', '1')
    _os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    _os.environ.setdefault('PYTORCH_JIT', '0')

    import logging as _lg
    for _noisy in ['tensorflow', 'torch', 'torch._dynamo',
                   'nv_one_logger', 'graphviz', 'datasets',
                   'huggingface_hub', 'transformers',
                   'httpcore', 'httpx']:
        _lg.getLogger(_noisy).setLevel(_lg.ERROR)

    try:
        import warnings as _w
        import numpy as _np
        if hasattr(_np, '__version__') and str(_np.__version__).startswith('2.'):
            if not hasattr(_np, 'iterable'):
                _np.iterable = lambda obj: hasattr(obj, '__iter__')
            if not hasattr(_np, 'complex'):
                _np.complex = complex
            if not hasattr(_np, 'float'):
                _np.float = float
            if not hasattr(_np, 'int'):
                _np.int = int
            if not hasattr(_np, 'bool'):
                _np.bool = bool
            print("[SYSTEM] numpy 2.x compatibility patches applied")
        else:
            _w.filterwarnings('ignore', category=FutureWarning, module='numpy')
    except Exception:
        pass


def setup_logging():
    """Configure rotating file logger for Seven."""
    _log_dir = os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'SEVEN', 'logs'
    )
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = os.path.join(_log_dir, 'seven.log')

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fh = logging.handlers.RotatingFileHandler(
        _log_file, maxBytes=5 * 1024 * 1024,
        backupCount=3, encoding='utf-8',
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

    for noisy in [
        'tensorflow', 'tensorflow.python', 'torch', 'torch._dynamo',
        'nv_one_logger', 'graphviz', 'datasets', 'huggingface_hub',
        'transformers', 'sentence_transformers', 'chromadb',
        'urllib3', 'httpx', 'httpcore', 'uvicorn.access',
        'sentry_sdk', 'faster_whisper', 'PIL', 'pyttsx3',
        'matplotlib', 'comtypes', 'h5py', 'numexpr', 'asyncio',
    ]:
        logging.getLogger(noisy).setLevel(logging.ERROR)

    if not root.handlers:
        root.addHandler(fh)
        root.addHandler(ch)

    return logging.getLogger('seven.main')


def setup_sentry():
    """Initialize Sentry error tracking if DSN is configured."""
    try:
        import sentry_sdk
        _dsn = os.environ.get("SEVEN_SENTRY_DSN", "")
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
            return
        sentry_sdk.init(
            dsn=_dsn, traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment="production",
        )
    except ImportError:
        pass
    except Exception:
        pass