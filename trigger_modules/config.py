"""
trigger_modules/config.py
Logging setup, path resolution, DB discovery, constants.
Imported first by trigger_daemon.py so side effects (logging tee,
console hiding, UTF-8) are established before anything else runs.
"""
import os
import sys
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────
# CONSOLE HIDING (pythonw.exe mode only)
# ─────────────────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        if "pythonw" in sys.executable.lower():
            _hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if _hwnd:
                ctypes.windll.user32.ShowWindow(_hwnd, 0)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# FORCE UTF-8 ENCODING
# ─────────────────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# ROTATING LOG FILE — writes all stdout/stderr to APPDATA log
# ─────────────────────────────────────────────────────────────────────────
_LOG_DIR = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'SEVEN', 'logs'
)

try:
    os.makedirs(_LOG_DIR, exist_ok=True)
    _LOG_FILE = os.path.join(_LOG_DIR, 'trigger_daemon.log')

    # Rotate if log exceeds 2MB — keep 3 backups
    if os.path.exists(_LOG_FILE) and os.path.getsize(_LOG_FILE) > 2 * 1024 * 1024:
        for i in range(2, 0, -1):
            _old = os.path.join(_LOG_DIR, f'trigger_daemon.log.{i}')
            _new = os.path.join(_LOG_DIR, f'trigger_daemon.log.{i+1}')
            if os.path.exists(_old):
                try:
                    if os.path.exists(_new):
                        os.remove(_new)
                    os.rename(_old, _new)
                except Exception:
                    pass
        try:
            os.rename(_LOG_FILE, os.path.join(_LOG_DIR, 'trigger_daemon.log.1'))
        except Exception:
            pass

    class _TeeStream:
        """Write to both original stream and log file with timestamp."""
        def __init__(self, original, log_path):
            self._orig = original
            self._log_path = log_path

        def write(self, data):
            try:
                if self._orig:
                    self._orig.write(data)
            except Exception:
                pass
            try:
                if data.strip():
                    with open(self._log_path, 'a', encoding='utf-8') as f:
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        for line in data.rstrip('\n').split('\n'):
                            f.write(f"[{ts}] {line}\n")
            except Exception:
                pass

        def flush(self):
            try:
                if self._orig:
                    self._orig.flush()
            except Exception:
                pass

    sys.stdout = _TeeStream(sys.stdout, _LOG_FILE)
    sys.stderr = _TeeStream(sys.stderr, _LOG_FILE)
except Exception:
    pass


# ─────────────────────────────────────────────────────────────────────────
# PROJECT PATH
# ─────────────────────────────────────────────────────────────────────────
# trigger_modules/config.py → parent → PROJECT ROOT
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Honor SEVEN_APP_PATH set by Electron in packaged mode
_app_path = os.environ.get("SEVEN_APP_PATH", "")
if _app_path and _app_path not in sys.path:
    sys.path.insert(0, _app_path)
    PROJECT_ROOT = _app_path


# ─────────────────────────────────────────────────────────────────────────
# APPDATA / LOCK PATHS
# ─────────────────────────────────────────────────────────────────────────
APPDATA   = os.environ.get('APPDATA', os.path.expanduser('~'))
LOCK_FILE = os.path.join(APPDATA, 'SEVEN', 'trigger_daemon.lock')


# ─────────────────────────────────────────────────────────────────────────
# DB PATH RESOLUTION
# Priority 1: local seven_data (dev mode, has actual triggers)
# Priority 2: APPDATA seven_data (installed mode)
# ─────────────────────────────────────────────────────────────────────────
LOCAL_SEVEN_DATA = os.path.join(PROJECT_ROOT, 'seven_data')
LOCAL_DB         = os.path.join(LOCAL_SEVEN_DATA, 'triggers.db')
APPDATA_SEVEN    = os.path.join(APPDATA, 'SEVEN', 'seven_data')
APPDATA_DB       = os.path.join(APPDATA_SEVEN, 'triggers.db')


def _resolve_db_path():
    """Find the correct triggers.db and its parent folder."""
    def _has_triggers(db_path):
        if not os.path.exists(db_path):
            return False
        try:
            import sqlite3 as _sq
            c = _sq.connect(db_path, timeout=2)
            count = c.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name='triggers'"
            ).fetchone()[0]
            c.close()
            return count > 0
        except Exception:
            return False

    if _has_triggers(LOCAL_DB):
        print(f"[TRIGGER DAEMON] Using LOCAL DB: {LOCAL_DB}")
        return LOCAL_DB, LOCAL_SEVEN_DATA

    if _has_triggers(APPDATA_DB):
        print(f"[TRIGGER DAEMON] Using APPDATA DB: {APPDATA_DB}")
        return APPDATA_DB, APPDATA_SEVEN

    if os.path.exists(LOCAL_SEVEN_DATA):
        print(f"[TRIGGER DAEMON] Defaulting to LOCAL (no triggers yet): {LOCAL_DB}")
        return LOCAL_DB, LOCAL_SEVEN_DATA

    print(f"[TRIGGER DAEMON] Defaulting to APPDATA: {APPDATA_DB}")
    return APPDATA_DB, APPDATA_SEVEN


TRIGGERS_DB, SEVEN_DATA = _resolve_db_path()
RELOAD_SIGNAL = os.path.join(SEVEN_DATA, 'trigger_reload.signal')


# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────
def is_seven_running():
    """Check if Seven main backend is running on port 7777."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:7777/api/status", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


def setup_logging():
    """
    No-op marker.
    All logging side effects run at import time above.
    trigger_daemon.py imports this to make the import intent explicit.
    """
    pass