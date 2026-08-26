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
        capture_output=True,
        creationflags=0x08000000 if platform.system() == 'Windows' else 0
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
        text=True,
        creationflags=0x08000000 if platform.system() == 'Windows' else 0
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
                'sentence_transformers', 'psutil', 'keyboard', 'pynput']

    for pkg in critical:
        result = subprocess.run(
            [python, '-c', f'import {pkg.replace("-", "_")}'],
            capture_output=True,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0
        )
        if result.returncode != 0:
            print(f"[BOOTSTRAP] Missing: {pkg}")
            return False

    return True


def install_packages():
    """
    Install all packages from requirements.txt into the correct Python.
    Shows real-time progress with package name, count, and speed.
    """
    _set('packages', status='running', progress=0,
         current='Preparing...', error=None)

    python_exe = get_python_executable()

    # Force standard python.exe for pip operations (pythonw.exe lacks stdio)
    if python_exe.lower().endswith('pythonw.exe'):
        std_python = python_exe[:-5] + '.exe'
        if os.path.exists(std_python):
            python_exe = std_python

    # Step 0: Fix ._pth file
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
    _set('packages', current='Upgrading pip...', progress=2)
    try:
        subprocess.run(
            [python_exe, '-m', 'pip', 'install', '--upgrade', 'pip',
             '--disable-pip-version-check', '--no-warn-script-location', '--quiet'],
            capture_output=True,
            timeout=120,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0
        )
    except Exception:
        pass

    # Step 4: Read requirements.txt
    with open(req_path, 'r') as f:
        lines = f.readlines()

    packages = [
        l.strip() for l in lines
        if l.strip() and not l.startswith('#') and not l.startswith('-')
    ]

    if not packages:
        _set('packages', status='error', error='No packages in requirements.txt')
        return False

    critical_first = [
        "python-multipart", "fastapi", "uvicorn[standard]", "websockets",
        "requests", "colorama", "psutil", "pyttsx3", "pywin32",
        "pycaw", "comtypes", "AppOpener", "ddgs", "SpeechRecognition",
        "pyaudio", "screen-brightness-control", "pyautogui", "keyboard",
        "pynput", "rapidfuzz"
    ]

    def _pkg_name(p):
        return p.split('==')[0].split('>=')[0].split('[')[0].strip().lower()

    critical_set = {c.split('[')[0].lower() for c in critical_first}
    ordered = [p for p in packages if _pkg_name(p) in critical_set]
    remaining = [p for p in packages if _pkg_name(p) not in critical_set]
    install_order = ordered + remaining

    total = len(install_order)
    optional = {'resemblyzer', 'pyaudio', 'screen-brightness-control'}
    failed_optional = []
    install_start = time.time()

    for i, pkg in enumerate(install_order):
        pkg_display = pkg.split('==')[0].split('>=')[0].strip()
        is_optional = any(o in pkg.lower() for o in optional)
        # Fix: Lock progress to prevent UI bouncing. Max package progress is 100.
        progress    = int(((i + 1) / total) * 100)

        label = f"[{i+1}/{total}] {pkg_display}"
        if i < len(ordered):
            label += " (core)"

        _set('packages', current=f'[{i+1}/{total}] Installing {pkg_display}...', progress=progress)
        pkg_start = time.time()

        result_returncode = 1
        stderr_output = ""
        _stop_heartbeat = threading.Event()

        def _heartbeat_worker():
            dots = 0
            while not _stop_heartbeat.is_set():
                dots = (dots + 1) % 4
                elapsed = int(time.time() - pkg_start)
                _set('packages',
                     current=f'[{i+1}/{total}] Installing {pkg_display}{"." * dots}  ({elapsed}s)',
                     progress=progress)
                time.sleep(1)

        try:
            process = subprocess.Popen(
                [python_exe, '-m', 'pip', 'install', pkg,
                 '--no-warn-script-location', '--disable-pip-version-check',
                 '--retries', '5', '--timeout', '90', '--progress-bar', 'off'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=0x08000000 if platform.system() == 'Windows' else 0
            )

            hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True)
            hb_thread.start()

            try:
                _, stderr_output = process.communicate(timeout=600)
                result_returncode = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr_output = process.communicate()
                stderr_output = "Timeout after 10 minutes"
                result_returncode = 1
            finally:
                _stop_heartbeat.set()
                hb_thread.join(timeout=2)

        except Exception as _e:
            stderr_output = str(_e)
            result_returncode = 1
            _stop_heartbeat.set()

        pkg_elapsed = round(time.time() - pkg_start, 1)

        if result_returncode == 0:
            print(f"[BOOTSTRAP]   done in {pkg_elapsed}s")
        else:
            if is_optional:
                failed_optional.append(pkg_display)
                print(f"[BOOTSTRAP]   optional skipped ({pkg_elapsed}s)")
                continue
            err = stderr_output.strip()[-400:] if stderr_output else 'Unknown error'
            print(f"[BOOTSTRAP]   FAILED: {err}")
            _set('packages', status='error',
                 error=f'{pkg_display} install failed. Check your internet connection.')
            return False

    total_elapsed = round(time.time() - install_start, 1)
    _set('packages', status='done', progress=100, current=f'All packages ready ({total_elapsed}s)')
    return True


# ============================================================================
# STEP 2 — OLLAMA INSTALL
# ============================================================================

def is_ollama_installed():
    """
    Check if Ollama is installed on this system.
    Checks both PATH and all known install locations.
    The duplicate dead code block below the first return has been removed.
    """
    # Check 1: PATH lookup
    result = subprocess.run(
        ['where', 'ollama'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        creationflags=0x08000000 if platform.system() == 'Windows' else 0
    )
    if result.returncode == 0 and result.stdout.strip():
        found = result.stdout.strip().split('\n')[0].strip()
        print(f"[BOOTSTRAP] Ollama found in PATH: {found}")
        return True

    # Check 2: All known install locations
    localappdata  = os.environ.get('LOCALAPPDATA', '')
    userprofile   = os.environ.get('USERPROFILE', '')
    programfiles  = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    programfilesx = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')

    paths = [
        os.path.join(localappdata,  'Programs', 'Ollama', 'ollama.exe'),
        os.path.join(userprofile,   'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
        os.path.join(programfiles,  'Ollama', 'ollama.exe'),
        os.path.join(programfilesx, 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        r'C:\ollama\ollama.exe',
    ]

    for p in paths:
        if os.path.exists(p):
            print(f"[BOOTSTRAP] Ollama found at: {p}")
            return True

    print("[BOOTSTRAP] Ollama not found anywhere on this system")
    return False


def get_ollama_executable():
    """
    Find ollama.exe path.
    Checks PATH first then all known install locations.
    Never returns a bare string that would fail silently.
    """
    # Check PATH first
    result = subprocess.run(
        ['where', 'ollama'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        creationflags=0x08000000 if platform.system() == 'Windows' else 0
    )
    if result.returncode == 0 and result.stdout.strip():
        path = result.stdout.strip().split('\n')[0].strip()
        if os.path.exists(path):
            print(f"[BOOTSTRAP] Ollama exe from PATH: {path}")
            return path

    # Check all known install locations
    localappdata  = os.environ.get('LOCALAPPDATA', '')
    userprofile   = os.environ.get('USERPROFILE', '')
    programfiles  = os.environ.get('PROGRAMFILES', r'C:\Program Files')
    programfilesx = os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')

    paths = [
        os.path.join(localappdata,  'Programs', 'Ollama', 'ollama.exe'),
        os.path.join(userprofile,   'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
        os.path.join(programfiles,  'Ollama', 'ollama.exe'),
        os.path.join(programfilesx, 'Ollama', 'ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
        r'C:\ollama\ollama.exe',
    ]

    for p in paths:
        if os.path.exists(p):
            print(f"[BOOTSTRAP] Ollama exe found at: {p}")
            return p

    # Last resort - hope it is in system PATH
    print("[BOOTSTRAP] WARNING: ollama.exe not found, falling back to PATH lookup")
    return 'ollama'


def download_ollama_installer():
    """Download OllamaSetup.exe with unique naming, chunked streaming, and ETA."""
    _set('ollama_install', status='running', progress=0, error=None)

    unique_name = f"OllamaSetup_{int(time.time())}.exe"
    dest = os.path.join(tempfile.gettempdir(), unique_name)

    print("[BOOTSTRAP] Downloading Ollama installer with real-time metrics...")
    
    try:
        import requests
        response = requests.get(OLLAMA_DOWNLOAD_URL, stream=True, timeout=15)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        
        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    elapsed = max(time.time() - start_time, 0.001)
                    speed_bps = downloaded / elapsed
                    speed_mb_s = round(speed_bps / (1024 * 1024), 2)
                    
                    if total_size > 0:
                        pct = min(int((downloaded / total_size) * 100), 99)
                        downloaded_mb = round(downloaded / (1024 * 1024), 1)
                        total_mb = round(total_size / (1024 * 1024), 1)
                        
                        bytes_remaining = total_size - downloaded
                        eta_seconds = bytes_remaining / speed_bps if speed_bps > 0 else 0
                        eta_str = f"{int(eta_seconds)}s left" if eta_seconds < 60 else f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s left"
                        
                        _set('ollama_install', progress=pct, current=f"{downloaded_mb}/{total_mb} MB  ·  {speed_mb_s} MB/s  ·  {eta_str}")
        
        response.close() # Explicitly close the connection to prevent hanging
        
        # Corrupted download check (Ollama is ~180MB. Anything under 50MB is corrupted)
        if os.path.getsize(dest) < 50_000_000:
            raise Exception("Downloaded file is too small (corrupted).")

        _set('ollama_install', progress=100, current="Awaiting Windows Defender Scan...")
        print(f"[BOOTSTRAP] Ollama downloaded successfully to {dest}")
        time.sleep(2)
        return dest

    except Exception as e:
        err_msg = str(e)
        friendly = (
            "Network timeout or file corruption. "
            "Please install manually: "
            "1. Visit ollama.com/download  "
            "2. Run OllamaSetup.exe  "
            "3. Restart Seven"
        )
        _set('ollama_install', status='error', error=friendly)
        print(f"[BOOTSTRAP] Ollama download failed: {err_msg}")
        return None


def install_ollama_silent(installer_path):
    """Run OllamaSetup.exe silently and prompt UAC."""
    print(f"[BOOTSTRAP] Installing Ollama silently...")
    
    # 1. Instantly trigger the UI banner for UAC
    _set('ollama_install', 
         status='running', 
         progress=100, 
         current="UAC_PROMPT_ACTIVE")
         
    time.sleep(1.5) # Allow frontend to render the banner
    
    try:
        import ctypes
        # ShellExecuteW blocks until the user clicks Yes or No
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", installer_path, "/S", None, 0
        )

        if ret > 32:
            print("[BOOTSTRAP] Ollama installer launched. Awaiting extraction...")
            _set('ollama_install', current="Extracting and registering services...")
            
            # Wait up to 5 minutes for extraction to complete on slow HDDs
            deadline = time.time() + 300 
            while time.time() < deadline:
                if is_ollama_installed():
                    _set('ollama_install', status='done', progress=100, current="Ollama installed successfully.")
                    print("[BOOTSTRAP] Ollama verified successfully.")
                    return True
                time.sleep(2)
                
            _set('ollama_install', status='error', error='Installation timed out after 5 minutes. Please run OllamaSetup manually.')
            return False
        else:
            print(f"[BOOTSTRAP] UAC Denied by user (Code {ret})")
            _set('ollama_install', status='error', error='Permission Denied. You must click YES on the Windows prompt to continue.')
            return False

    except Exception as e:
        print(f"[BOOTSTRAP] Ollama install exception: {e}")
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
    """Pull an Ollama model using the REST API with ETA and MB/s."""
    _set('model_pull', status='running', model=model_name,
         progress=0, current="", downloaded_gb=0.0, total_gb=0.0, error=None)

    print(f"[BOOTSTRAP] Pulling model via API: {model_name}")

    try:
        import requests
        response = requests.post(f"{OLLAMA_HOST}/api/pull", json={"name": model_name}, stream=True, timeout=600)
        response.raise_for_status()
        
        last_update = 0
        start_time = time.time()
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    
                    if 'total' in data and data['total'] > 0:
                        completed = data.get('completed', 0)
                        total = data['total']
                        pct = int((completed / total) * 100)
                        now = time.time()
                        
                        if now - last_update > 0.5:
                            dl_gb = round(completed / (1024 ** 3), 2)
                            tot_gb = round(total / (1024 ** 3), 2)
                            
                            elapsed = max(now - start_time, 0.001)
                            speed_bps = completed / elapsed
                            speed_mb_s = round(speed_bps / (1024 * 1024), 2)
                            
                            bytes_remaining = total - completed
                            eta_seconds = bytes_remaining / speed_bps if speed_bps > 0 else 0
                            eta_str = f"{int(eta_seconds)}s left" if eta_seconds < 60 else f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s left"
                            
                            current_str = f"{dl_gb}/{tot_gb} GB  ·  {speed_mb_s} MB/s  ·  {eta_str}"
                            
                            _set('model_pull', progress=pct, current=current_str, downloaded_gb=dl_gb, total_gb=tot_gb)
                            last_update = now
                    elif 'status' in data and not ('total' in data):
                        # Catch intermediate statuses like 'pulling manifest'
                        if now - last_update > 0.5:
                            _set('model_pull', current=data['status'])
                            last_update = now
                except Exception:
                    pass
                
        _set('model_pull', status='done', progress=100, current="Pull complete")
        print(f"[BOOTSTRAP] Model {model_name} pulled successfully.")
        return True

    except Exception as e:
        print(f"[BOOTSTRAP] Pull failed: {e}")
        _set('model_pull', status='error', error=str(e))
        return False


# ============================================================================
# ORCHESTRATORS
# ============================================================================

def run_environment_setup(on_complete=None):
    """
    Run full environment setup in background thread.
    Instantly updates shared state so button reacts in 0ms.
    """
    # INSTANT UPDATE - Button reacts immediately on click
    _set('packages', status='running', progress=5, current='Initializing environment deployment...')
    _set('ollama_install', status='pending', progress=0, current='Waiting for package completion...')
    _set('ollama_start', status='pending', current='Waiting...')

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

        # ── Step 2: Ollama install (REQUIRED) ──
        ollama_ok = setup_ollama()
        if not ollama_ok:
            # Check if user already has Ollama installed manually
            if is_ollama_installed():
                print("[BOOTSTRAP] Ollama found via manual install")
                _set('ollama_install', status='done', progress=100)
            else:
                print("[BOOTSTRAP] Ollama install failed")
                if on_complete:
                    on_complete(False)
                return

        # ── Step 3: Start Ollama (REQUIRED) ──
        ok = start_ollama()
        if not ok:
            # Try one more time
            import time
            time.sleep(3)
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