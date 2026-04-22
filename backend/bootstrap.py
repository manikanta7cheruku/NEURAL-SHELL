"""
=============================================================================
PROJECT SEVEN - backend/bootstrap.py
First-Launch Environment Setup

PURPOSE:
    Handles everything the Setup Wizard Step 4 needs:
    1. Install Python packages from requirements.txt
    2. Download and install Ollama silently
    3. Start Ollama service
    4. Verify the environment is ready
    5. Pull selected LLM model with progress streaming

    All functions stream progress via Server-Sent Events (SSE)
    so the React wizard can show live status to the user.

CALLED BY:
    - api_server.py (new endpoints /api/bootstrap/*)
    - Only runs during setup wizard (setup_complete: false)
=============================================================================
"""

import os
import sys
import json
import subprocess
import threading
import time
import platform
import urllib.request
import tempfile
from pathlib import Path

# ── Ollama config ──
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_INSTALLER_NAME = "OllamaSetup.exe"
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_CHECK_TIMEOUT = 30  # seconds to wait for Ollama to start

# ── Shared state (polled by /api/bootstrap/status) ──
_bootstrap_state = {
    "packages": {
        "status": "pending",   # pending | running | done | error
        "current": "",
        "progress": 0,
        "error": None
    },
    "ollama_install": {
        "status": "pending",
        "progress": 0,
        "error": None
    },
    "ollama_start": {
        "status": "pending",
        "error": None
    },
    "model_pull": {
        "status": "pending",
        "model": "",
        "progress": 0,
        "downloaded_gb": 0.0,
        "total_gb": 0.0,
        "error": None
    },
    "overall_ready": False
}

_state_lock = threading.Lock()


def get_state():
    """Return a copy of current bootstrap state."""
    with _state_lock:
        return json.loads(json.dumps(_bootstrap_state))


def _set(section, **kwargs):
    """Thread-safe state update."""
    with _state_lock:
        for k, v in kwargs.items():
            _bootstrap_state[section][k] = v


# ============================================================================
# PYTHON DETECTION
# ============================================================================

def get_python_executable():
    """
    Find the correct Python executable to use.
    
    Priority:
    1. Embedded Python inside app (packaged mode)
    2. System Python (dev mode)
    
    Returns the full path to python.exe
    """
    # Check if running from packaged Electron app
    # Electron sets this env var in main.js
    app_path = os.environ.get('SEVEN_APP_PATH')

    if app_path:
        # Packaged mode — use embedded Python
        embedded = os.path.join(app_path, 'python', 'python.exe')
        if os.path.exists(embedded):
            print(f"[BOOTSTRAP] Using embedded Python: {embedded}")
            return embedded

    # Dev mode — use current Python
    return sys.executable


def get_pip_executable():
    """Get pip for the correct Python environment."""
    python = get_python_executable()
    return [python, '-m', 'pip']


def get_requirements_path():
    """Find requirements.txt — works in both dev and packaged mode."""
    # Try app path first (packaged)
    app_path = os.environ.get('SEVEN_APP_PATH')
    if app_path:
        req = os.path.join(app_path, 'requirements.txt')
        if os.path.exists(req):
            return req

    # Dev mode — relative to this file
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    req = os.path.join(script_dir, 'requirements.txt')
    if os.path.exists(req):
        return req

    return None


# ============================================================================
# STEP 1 — INSTALL PYTHON PACKAGES
# ============================================================================

def check_packages_installed():
    """
    Quick check if core packages are already installed.
    Returns True if all critical packages are importable.
    """
    critical = [
        'requests', 'fastapi', 'uvicorn', 'pyttsx3',
        'chromadb', 'sentence_transformers', 'faster_whisper',
        'psutil', 'pywin32'
    ]
    
    python = get_python_executable()
    
    for pkg in critical:
        check_name = pkg.replace('-', '_')
        result = subprocess.run(
            [python, '-c', f'import {check_name}'],
            capture_output=True
        )
        if result.returncode != 0:
            print(f"[BOOTSTRAP] Package missing: {pkg}")
            return False
    
    return True


def install_packages():
    """
    Install all packages from requirements.txt.
    Updates _bootstrap_state.packages with live progress.
    Runs synchronously (called from a thread).
    """
    _set('packages', status='running', progress=0, current='Starting...', error=None)

    req_path = get_requirements_path()
    if not req_path:
        _set('packages', status='error', error='requirements.txt not found')
        return False

    pip = get_pip_executable()

    # First upgrade pip itself
    _set('packages', current='Upgrading pip...', progress=2)
    subprocess.run(
        pip + ['install', '--upgrade', 'pip', '--quiet'],
        capture_output=True
    )

    # Read requirements
    with open(req_path, 'r') as f:
        lines = f.readlines()

    # Filter to actual package lines
    packages = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('-'):
            packages.append(line)

    if not packages:
        _set('packages', status='error', error='No packages found in requirements.txt')
        return False

    total = len(packages)
    print(f"[BOOTSTRAP] Installing {total} packages...")

    for i, pkg in enumerate(packages):
        pkg_display = pkg.split('==')[0].split('>=')[0].strip()
        progress = int(((i) / total) * 100)
        _set('packages', current=f'Installing {pkg_display}...', progress=progress)
        print(f"[BOOTSTRAP] [{i+1}/{total}] Installing {pkg_display}")

        result = subprocess.run(
            pip + ['install', pkg, '--quiet', '--no-warn-script-location'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # Some packages are optional — don't fail on them
            optional = ['resemblyzer', 'pyaudio', 'screen-brightness-control']
            is_optional = any(o in pkg.lower() for o in optional)

            if is_optional:
                print(f"[BOOTSTRAP] Optional package failed (ok): {pkg_display}")
                continue
            else:
                error_msg = result.stderr.strip()[-200:] if result.stderr else 'Unknown error'
                print(f"[BOOTSTRAP] Failed: {pkg_display} — {error_msg}")
                _set('packages', status='error', error=f'{pkg_display} failed: {error_msg}')
                return False

    _set('packages', status='done', progress=100, current='All packages installed')
    print("[BOOTSTRAP] All packages installed successfully.")
    return True


# ============================================================================
# STEP 2 — OLLAMA INSTALL
# ============================================================================

def is_ollama_installed():
    """Check if Ollama is installed on this system."""
    # Check PATH
    result = subprocess.run(['where', 'ollama'], capture_output=True, text=True)
    if result.returncode == 0:
        return True

    # Check common install locations
    common_paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
    ]
    return any(os.path.exists(p) for p in common_paths)


def get_ollama_executable():
    """Find ollama.exe path."""
    # Try PATH first
    result = subprocess.run(['where', 'ollama'], capture_output=True, text=True)
    if result.returncode == 0:
        path = result.stdout.strip().split('\n')[0]
        if os.path.exists(path):
            return path

    # Check common locations
    common_paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p

    return 'ollama'  # Fallback — hope it's in PATH


def download_ollama_installer():
    """
    Download OllamaSetup.exe to temp directory.
    Updates _bootstrap_state.ollama_install with progress.
    Returns path to installer or None on failure.
    """
    _set('ollama_install', status='running', progress=0, error=None)

    dest = os.path.join(tempfile.gettempdir(), OLLAMA_INSTALLER_NAME)

    # If already downloaded, skip
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000_000:  # > 10MB
        _set('ollama_install', progress=100)
        print(f"[BOOTSTRAP] Ollama installer already cached: {dest}")
        return dest

    print(f"[BOOTSTRAP] Downloading Ollama from {OLLAMA_DOWNLOAD_URL}")

    try:
        def _reporthook(block_num, block_size, total_size):
            if total_size > 0:
                pct = min(int((block_num * block_size / total_size) * 100), 99)
                _set('ollama_install', progress=pct)

        urllib.request.urlretrieve(OLLAMA_DOWNLOAD_URL, dest, _reporthook)
        _set('ollama_install', progress=100)
        print(f"[BOOTSTRAP] Ollama downloaded to {dest}")
        return dest

    except Exception as e:
        _set('ollama_install', status='error', error=str(e))
        print(f"[BOOTSTRAP] Ollama download failed: {e}")
        return None


def install_ollama_silent(installer_path):
    """
    Run OllamaSetup.exe silently.
    /S = silent install (NSIS standard flag)
    """
    print(f"[BOOTSTRAP] Running silent Ollama install: {installer_path}")

    try:
        result = subprocess.run(
            [installer_path, '/S'],
            capture_output=True,
            timeout=120  # 2 min timeout
        )
        if result.returncode == 0:
            print("[BOOTSTRAP] Ollama installed successfully.")
            _set('ollama_install', status='done', progress=100)
            return True
        else:
            error = f"Installer exited with code {result.returncode}"
            _set('ollama_install', status='error', error=error)
            print(f"[BOOTSTRAP] Ollama install failed: {error}")
            return False
    except subprocess.TimeoutExpired:
        _set('ollama_install', status='error', error='Installation timed out')
        return False
    except Exception as e:
        _set('ollama_install', status='error', error=str(e))
        return False


def setup_ollama():
    """
    Full Ollama setup flow:
    1. Check if already installed
    2. If not: download + install silently
    Returns True when Ollama is installed.
    """
    if is_ollama_installed():
        print("[BOOTSTRAP] Ollama already installed.")
        _set('ollama_install', status='done', progress=100)
        return True

    # Download
    installer = download_ollama_installer()
    if not installer:
        return False

    # Install silently
    return install_ollama_silent(installer)


# ============================================================================
# STEP 3 — START OLLAMA SERVICE
# ============================================================================

def is_ollama_running():
    """Check if Ollama API is responding."""
    try:
        import urllib.request as req
        with req.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start_ollama():
    """
    Start the Ollama service in background.
    Waits up to OLLAMA_CHECK_TIMEOUT seconds for it to respond.
    Updates _bootstrap_state.ollama_start.
    """
    _set('ollama_start', status='running', error=None)

    if is_ollama_running():
        print("[BOOTSTRAP] Ollama already running.")
        _set('ollama_start', status='done')
        return True

    ollama_exe = get_ollama_executable()
    print(f"[BOOTSTRAP] Starting Ollama: {ollama_exe}")

    try:
        subprocess.Popen(
            [ollama_exe, 'serve'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
        )
    except Exception as e:
        _set('ollama_start', status='error', error=str(e))
        print(f"[BOOTSTRAP] Failed to start Ollama: {e}")
        return False

    # Wait for Ollama to respond
    deadline = time.time() + OLLAMA_CHECK_TIMEOUT
    while time.time() < deadline:
        if is_ollama_running():
            print("[BOOTSTRAP] Ollama is now running.")
            _set('ollama_start', status='done')
            return True
        time.sleep(1)

    _set('ollama_start', status='error', error='Ollama did not start within 30 seconds')
    return False


# ============================================================================
# STEP 4 — PULL LLM MODEL
# ============================================================================

def pull_model(model_name: str):
    """
    Pull an Ollama model with real progress tracking.
    Streams pull progress to _bootstrap_state.model_pull.
    
    Ollama pull outputs JSON lines like:
        {"status": "pulling manifest"}
        {"status": "pulling", "digest": "...", "total": 4000000, "completed": 500000}
        {"status": "success"}
    
    Runs synchronously (called from a thread).
    """
    _set('model_pull', status='running', model=model_name, progress=0,
         downloaded_gb=0.0, total_gb=0.0, error=None)

    ollama_exe = get_ollama_executable()
    print(f"[BOOTSTRAP] Pulling model: {model_name}")

    try:
        process = subprocess.Popen(
            [ollama_exe, 'pull', model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0
        )

        total_bytes = 0
        completed_bytes = 0

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            # Try to parse as JSON (Ollama outputs JSON lines)
            try:
                data = json.loads(line)
                status = data.get('status', '')

                if 'total' in data and data['total'] > 0:
                    total_bytes = max(total_bytes, data['total'])
                    completed_bytes = data.get('completed', completed_bytes)

                    pct = int((completed_bytes / total_bytes) * 100)
                    dl_gb = round(completed_bytes / (1024 ** 3), 2)
                    total_gb = round(total_bytes / (1024 ** 3), 2)

                    _set('model_pull',
                         progress=pct,
                         downloaded_gb=dl_gb,
                         total_gb=total_gb)

                elif status == 'success':
                    _set('model_pull', status='done', progress=100)
                    print(f"[BOOTSTRAP] Model {model_name} pulled successfully.")

            except json.JSONDecodeError:
                # Plain text line — just log it
                print(f"[BOOTSTRAP] ollama: {line}")

        process.wait()

        if process.returncode == 0:
            _set('model_pull', status='done', progress=100)
            return True
        else:
            _set('model_pull', status='error', error=f'Pull exited with code {process.returncode}')
            return False

    except Exception as e:
        _set('model_pull', status='error', error=str(e))
        print(f"[BOOTSTRAP] Pull failed: {e}")
        return False


# ============================================================================
# FULL BOOTSTRAP SEQUENCE
# ============================================================================

def run_environment_setup(on_complete=None):
    """
    Run full environment setup in background thread.
    Steps: packages → ollama install → ollama start
    
    on_complete: optional callback(success: bool)
    """
    def _run():
        print("[BOOTSTRAP] Starting environment setup...")

        # Step 1 — Python packages
        if not check_packages_installed():
            ok = install_packages()
            if not ok:
                if on_complete:
                    on_complete(False)
                return
        else:
            print("[BOOTSTRAP] Packages already installed.")
            _set('packages', status='done', progress=100, current='Already installed')

        # Step 2 — Ollama install
        ok = setup_ollama()
        if not ok:
            if on_complete:
                on_complete(False)
            return

        # Step 3 — Start Ollama
        ok = start_ollama()
        if not ok:
            if on_complete:
                on_complete(False)
            return

        with _state_lock:
            _bootstrap_state['overall_ready'] = True

        print("[BOOTSTRAP] Environment setup complete.")
        if on_complete:
            on_complete(True)

    t = threading.Thread(target=_run, daemon=True, name="BootstrapSetup")
    t.start()
    return t


def run_model_pull(model_name: str, on_complete=None):
    """
    Pull a model in background thread.
    on_complete: optional callback(success: bool)
    """
    def _run():
        ok = pull_model(model_name)
        if on_complete:
            on_complete(ok)

    t = threading.Thread(target=_run, daemon=True, name="ModelPull")
    t.start()
    return t