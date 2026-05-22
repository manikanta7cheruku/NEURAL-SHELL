"""
=============================================================================
PROJECT SEVEN - backend/bootstrap.py
First-Launch Environment Setup
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

# ── Ollama config ──
OLLAMA_DOWNLOAD_URL   = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_INSTALLER_NAME = "OllamaSetup.exe"
OLLAMA_HOST           = "http://127.0.0.1:11434"
OLLAMA_CHECK_TIMEOUT  = 60

# ── Shared state ──
_bootstrap_state = {
    "packages": {
        "status": "pending",
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
    with _state_lock:
        return json.loads(json.dumps(_bootstrap_state))


def _set(section, **kwargs):
    with _state_lock:
        for k, v in kwargs.items():
            _bootstrap_state[section][k] = v


# ============================================================================
# PYTHON / PIP DETECTION
# ============================================================================

def get_python_executable():
    """
    Find the correct Python executable.
    Packaged app: use embedded Python.
    Dev mode: use current Python.
    """
    app_path = os.environ.get('SEVEN_APP_PATH')
    if app_path:
        embedded = os.path.join(app_path, 'python', 'python.exe')
        if os.path.exists(embedded):
            print(f"[BOOTSTRAP] Using embedded Python: {embedded}")
            return embedded

    print(f"[BOOTSTRAP] Using system Python: {sys.executable}")
    return sys.executable


def get_requirements_path():
    """Find requirements.txt."""
    app_path = os.environ.get('SEVEN_APP_PATH')
    if app_path:
        req = os.path.join(app_path, 'requirements.txt')
        if os.path.exists(req):
            return req

    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    req = os.path.join(script_dir, 'requirements.txt')
    if os.path.exists(req):
        return req

    return None


def _ensure_pip(python_exe):
    """
    Ensure pip is available for this Python executable.
    Embeddable Python does NOT include pip — we must bootstrap it.
    Returns True if pip is available after this call.
    """
    # Test if pip already works
    result = subprocess.run(
        [python_exe, '-m', 'pip', '--version'],
        capture_output=True
    )
    if result.returncode == 0:
        print("[BOOTSTRAP] pip already available.")
        return True

    print("[BOOTSTRAP] pip not found — bootstrapping pip...")
    _set('packages', current='Bootstrapping pip...', progress=1)

    # Download get-pip.py
    get_pip_url  = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = os.path.join(tempfile.gettempdir(), 'get-pip.py')

    try:
        urllib.request.urlretrieve(get_pip_url, get_pip_path)
    except Exception as e:
        _set('packages', status='error', error=f'Failed to download pip: {e}')
        return False

    # Install pip
    result = subprocess.run(
        [python_exe, get_pip_path, '--no-warn-script-location'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        _set('packages', status='error',
             error=f'pip bootstrap failed: {result.stderr[-300:]}')
        return False

    print("[BOOTSTRAP] pip bootstrapped successfully.")
    return True


def _fix_pth_file(python_exe):
    """
    Embeddable Python has a pythonXXX._pth file that DISABLES site-packages.
    We must uncomment 'import site' in it for pip installs to be importable.
    
    This is the #1 silent killer of embedded Python installs.
    """
    python_dir = os.path.dirname(python_exe)

    # Find the ._pth file (e.g. python311._pth)
    pth_files = [
        f for f in os.listdir(python_dir)
        if f.endswith('._pth') and f.startswith('python')
    ]

    if not pth_files:
        print("[BOOTSTRAP] No ._pth file found — skipping fix")
        return

    pth_path = os.path.join(python_dir, pth_files[0])
    print(f"[BOOTSTRAP] Fixing pth file: {pth_path}")

    with open(pth_path, 'r') as f:
        content = f.read()

    # Uncomment 'import site' if it's commented out
    fixed = content.replace('#import site', 'import site')

    # Also ensure Lib/site-packages is in the path file
    lib_line = 'Lib\\site-packages'
    if lib_line not in fixed:
        fixed = fixed + f'\n{lib_line}\n'

    if fixed != content:
        with open(pth_path, 'w') as f:
            f.write(fixed)
        print("[BOOTSTRAP] Fixed pth file — site-packages enabled.")
    else:
        print("[BOOTSTRAP] pth file already correct.")


# ============================================================================
# STEP 1 — INSTALL PYTHON PACKAGES
# ============================================================================

def check_packages_installed():
    """Check if core packages are installed in the correct Python."""
    python = get_python_executable()

    critical = ['fastapi', 'uvicorn', 'pyttsx3', 'chromadb',
                'sentence_transformers', 'psutil']

    for pkg in critical:
        result = subprocess.run(
            [python, '-c', f'import {pkg.replace("-", "_")}'],
            capture_output=True
        )
        if result.returncode != 0:
            print(f"[BOOTSTRAP] Missing: {pkg}")
            return False

    return True


def install_packages():
    """
    Install all packages from requirements.txt into the correct Python.
    """
    _set('packages', status='running', progress=0,
         current='Preparing...', error=None)

    python_exe = get_python_executable()

    # Step 0: Fix ._pth file (must happen before pip)
    _fix_pth_file(python_exe)

    # Step 1: Ensure pip exists
    if not _ensure_pip(python_exe):
        return False

    # Step 2: Get requirements
    req_path = get_requirements_path()
    if not req_path:
        _set('packages', status='error', error='requirements.txt not found')
        return False

    # Step 3: Upgrade pip
    _set('packages', current='Upgrading pip...', progress=3)
    subprocess.run(
        [python_exe, '-m', 'pip', 'install', '--upgrade', 'pip', '--quiet'],
        capture_output=True
    )

        # ── Step 3b: Ensure critical runtime dependencies exist ──
    # These must be present BEFORE api_server.py imports
    _set('packages', current='Installing core dependencies...', progress=4)

    critical_runtime_packages = [
        "python-multipart",
        "fastapi",
        "uvicorn[standard]",
        "websockets",
        "pyautogui",
        "requests",
        "colorama",
        "psutil",
        "pyttsx3",
        "pywin32",
        "pycaw",
        "comtypes",
        "AppOpener",
        "ddgs",
        "SpeechRecognition",
        "pyaudio",
        "screen-brightness-control",
    ]

    for pkg in critical_runtime_packages:
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", pkg,
             "--quiet", "--no-warn-script-location"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"[BOOTSTRAP] Warning: Failed installing {pkg}")

    print("[BOOTSTRAP] Core runtime dependencies ensured.")

    # Step 4: Read packages
    with open(req_path, 'r') as f:
        lines = f.readlines()

    packages = [
        l.strip() for l in lines
        if l.strip() and not l.startswith('#') and not l.startswith('-')
    ]

    if not packages:
        _set('packages', status='error', error='No packages in requirements.txt')
        return False

    total    = len(packages)
    optional = ['resemblyzer', 'pyaudio', 'screen-brightness-control']

    print(f"[BOOTSTRAP] Installing {total} packages into {python_exe}")

    for i, pkg in enumerate(packages):
        pkg_display = pkg.split('==')[0].split('>=')[0].strip()
        progress    = int(((i) / total) * 100)
        _set('packages', current=f'Installing {pkg_display}...', progress=progress)
        print(f"[BOOTSTRAP] [{i+1}/{total}] {pkg_display}")

        result = subprocess.run(
            [python_exe, '-m', 'pip', 'install', pkg,
             '--quiet', '--no-warn-script-location'],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            is_optional = any(o in pkg.lower() for o in optional)
            if is_optional:
                print(f"[BOOTSTRAP] Optional skipped: {pkg_display}")
                continue
            err = result.stderr.strip()[-300:] if result.stderr else 'Unknown'
            _set('packages', status='error',
                 error=f'{pkg_display} failed: {err}')
            return False

    _set('packages', status='done', progress=100,
         current='All packages installed')
    print("[BOOTSTRAP] All packages installed.")
    return True


# ============================================================================
# STEP 2 — OLLAMA INSTALL
# ============================================================================

def is_ollama_installed():
    """Check if Ollama is installed on this system."""
    result = subprocess.run(
        ['where', 'ollama'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    if result.returncode == 0 and result.stdout.strip():
        return True

    # Also check common install locations directly
    paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''),
                     'Programs', 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        os.path.join(os.environ.get('USERPROFILE', ''),
                     'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
    ]
    for p in paths:
        if os.path.exists(p):
            print(f"[BOOTSTRAP] Ollama found at: {p}")
            return True

    return False

    paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''),
                     'Programs', 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        os.path.join(os.environ.get('USERPROFILE', ''),
                     'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
    ]
    return any(os.path.exists(p) for p in paths)


def get_ollama_executable():
    """Find ollama.exe."""
    result = subprocess.run(
        ['where', 'ollama'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    if result.returncode == 0 and result.stdout.strip():
        path = result.stdout.strip().split('\n')[0].strip()
        if os.path.exists(path):
            return path

    paths = [
        os.path.join(os.environ.get('LOCALAPPDATA', ''),
                     'Programs', 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        os.path.join(os.environ.get('USERPROFILE', ''),
                     'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
    ]
    for p in paths:
        if os.path.exists(p):
            return p

    return 'ollama'


def download_ollama_installer():
    """Download OllamaSetup.exe with progress."""
    _set('ollama_install', status='running', progress=0, error=None)

    dest = os.path.join(tempfile.gettempdir(), OLLAMA_INSTALLER_NAME)

    if os.path.exists(dest) and os.path.getsize(dest) > 10_000_000:
        _set('ollama_install', progress=100)
        print(f"[BOOTSTRAP] Ollama installer cached: {dest}")
        return dest

    print(f"[BOOTSTRAP] Downloading Ollama...")

    try:
        def _progress(block_num, block_size, total_size):
            if total_size > 0:
                pct = min(int((block_num * block_size / total_size) * 100), 99)
                _set('ollama_install', progress=pct)

        urllib.request.urlretrieve(OLLAMA_DOWNLOAD_URL, dest, _progress)
        _set('ollama_install', progress=100)
        print(f"[BOOTSTRAP] Ollama downloaded: {dest}")
        return dest

    except Exception as e:
        error_msg = str(e).encode('ascii', errors='replace').decode('ascii')

        # Give user clear instructions
        friendly = (
            "Could not download Ollama automatically. "
            "Please install it manually: "
            "1. Visit ollama.com/download  "
            "2. Download OllamaSetup.exe  "
            "3. Run it  "
            "4. Then restart Seven setup"
        )
        _set('ollama_install', status='error', error=friendly)
        print(f"[BOOTSTRAP] Ollama download failed: {error_msg}")
        return None


def install_ollama_silent(installer_path):
    """Run OllamaSetup.exe silently."""
    print(f"[BOOTSTRAP] Installing Ollama silently...")
    try:
        result = subprocess.run(
            [installer_path, '/S'],
            capture_output=True,
            timeout=180
        )
        if result.returncode == 0:
            _set('ollama_install', status='done', progress=100)
            print("[BOOTSTRAP] Ollama installed.")
            return True
        else:
            err = f"Exit code {result.returncode}"
            _set('ollama_install', status='error', error=err)
            return False
    except subprocess.TimeoutExpired:
        _set('ollama_install', status='error', error='Install timed out')
        return False
    except Exception as e:
        _set('ollama_install', status='error', error=str(e))
        return False


def setup_ollama():
    """Full Ollama setup: check → download → install."""
    if is_ollama_installed():
        print("[BOOTSTRAP] Ollama already installed.")
        _set('ollama_install', status='done', progress=100)
        return True

    installer = download_ollama_installer()
    if not installer:
        return False

    return install_ollama_silent(installer)


# ============================================================================
# STEP 3 — START OLLAMA SERVICE
# ============================================================================

def is_ollama_running():
    """Check if Ollama API responds."""
    try:
        with urllib.request.urlopen(
            f"{OLLAMA_HOST}/api/tags", timeout=3
        ) as r:
            return r.status == 200
    except Exception:
        return False


def start_ollama():
    """Start Ollama service and wait for it to respond."""
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
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if platform.system() == 'Windows' else 0
            )
        )
    except Exception as e:
        _set('ollama_start', status='error', error=str(e))
        return False

    # Wait up to OLLAMA_CHECK_TIMEOUT seconds
    deadline = time.time() + OLLAMA_CHECK_TIMEOUT
    while time.time() < deadline:
        if is_ollama_running():
            print("[BOOTSTRAP] Ollama is running.")
            _set('ollama_start', status='done')
            return True
        time.sleep(2)

    _set('ollama_start', status='error',
         error='Ollama did not respond within 60 seconds')
    return False


# ============================================================================
# STEP 4 — PULL LLM MODEL
# ============================================================================

def pull_model(model_name: str):
    """Pull an Ollama model with progress tracking."""
    _set('model_pull', status='running', model=model_name,
         progress=0, downloaded_gb=0.0, total_gb=0.0, error=None)

    ollama_exe = get_ollama_executable()
    print(f"[BOOTSTRAP] Pulling: {model_name}")

    try:
        process = subprocess.Popen(
            [ollama_exe, 'pull', model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if platform.system() == 'Windows' else 0
            )
        )

        total_bytes     = 0
        completed_bytes = 0

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                data   = json.loads(line)
                status = data.get('status', '')

                if 'total' in data and data['total'] > 0:
                    total_bytes     = max(total_bytes, data['total'])
                    completed_bytes = data.get('completed', completed_bytes)
                    pct             = int((completed_bytes / total_bytes) * 100)
                    dl_gb           = round(completed_bytes / (1024 ** 3), 2)
                    total_gb        = round(total_bytes     / (1024 ** 3), 2)
                    _set('model_pull', progress=pct,
                         downloaded_gb=dl_gb, total_gb=total_gb)

                elif status == 'success':
                    _set('model_pull', status='done', progress=100)

            except json.JSONDecodeError:
                print(f"[BOOTSTRAP] ollama: {line}")

        process.wait()

        if process.returncode == 0:
            _set('model_pull', status='done', progress=100)
            print(f"[BOOTSTRAP] Model {model_name} ready.")
            return True
        else:
            _set('model_pull', status='error',
                 error=f'Pull exited with code {process.returncode}')
            return False

    except Exception as e:
        _set('model_pull', status='error', error=str(e))
        return False


# ============================================================================
# ORCHESTRATORS
# ============================================================================

def run_environment_setup(on_complete=None):
    """
    Run full environment setup in background thread.
    Ollama is optional — if download fails, setup continues.
    User can install Ollama manually later.
    """
    def _run():
        print("[BOOTSTRAP] Starting environment setup...")

        # ── Step 1: Python packages (required) ──
        if not check_packages_installed():
            ok = install_packages()
            if not ok:
                print("[BOOTSTRAP] Package install failed — cannot continue")
                if on_complete:
                    on_complete(False)
                return
        else:
            print("[BOOTSTRAP] Packages already installed.")
            _set('packages', status='done', progress=100,
                 current='Already installed')

        # ── Step 2: Ollama install (optional — non-fatal) ──
        ollama_ok = False
        try:
            ollama_ok = setup_ollama()
            if not ollama_ok:
                print("[BOOTSTRAP] Ollama install failed — continuing anyway")
                print("[BOOTSTRAP] User can install Ollama manually from ollama.com")
                _set('ollama_install',
                     status='error',
                     error='Download failed. Install Ollama manually from ollama.com/download')
        except Exception as e:
            print(f"[BOOTSTRAP] Ollama error (non-fatal): {e}")
            _set('ollama_install',
                 status='error',
                 error=f'Ollama unavailable: {str(e)[:100]}')

        # ── Step 3: Start Ollama (only if installed) ──
        if ollama_ok:
            try:
                start_ollama()
            except Exception as e:
                print(f"[BOOTSTRAP] Ollama start error (non-fatal): {e}")
        else:
            _set('ollama_start', status='error',
                 error='Skipped — Ollama not installed')

        # ── Setup complete regardless of Ollama status ──
        with _state_lock:
            _bootstrap_state['overall_ready'] = True

        print("[BOOTSTRAP] Environment setup complete.")
        print("[BOOTSTRAP] Note: If Ollama failed, install from ollama.com/download")
        if on_complete:
            on_complete(True)  # Always succeed at package level

    t = threading.Thread(target=_run, daemon=True, name="Bootstrap")
    t.start()
    return t


def run_model_pull(model_name: str, on_complete=None):
    """Pull model in background thread."""
    def _run():
        ok = pull_model(model_name)
        if on_complete:
            on_complete(ok)

    t = threading.Thread(target=_run, daemon=True, name="ModelPull")
    t.start()
    return t