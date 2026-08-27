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
        "current": "",
        "error": None,
        "max_dl_mb": 0.0,   # Monotonic guard: never decreases across retries
        "max_pct": 0         # Monotonic guard: never decreases across retries
    },
    "ollama_start": {
        "status": "pending",
        "current": "",
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

# ── Bootstrap persistence file ──
# Prevents re-running completed steps after a crash/restart
_BOOTSTRAP_STATE_FILE = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'SEVEN', 'bootstrap_state.json'
)


def _save_bootstrap_checkpoint():
    """Save completed steps to disk so restarts can skip them."""
    try:
        data = {}
        with _state_lock:
            data = {
                "packages_done": _bootstrap_state["packages"]["status"] == "done",
                "ollama_installed": is_ollama_installed(),
                "ollama_running": is_ollama_running(),
                "overall_ready": _bootstrap_state["overall_ready"]
            }
        os.makedirs(os.path.dirname(_BOOTSTRAP_STATE_FILE), exist_ok=True)
        with open(_BOOTSTRAP_STATE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass


def _load_bootstrap_checkpoint():
    """Load previous bootstrap progress to skip completed steps."""
    try:
        if os.path.exists(_BOOTSTRAP_STATE_FILE):
            with open(_BOOTSTRAP_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


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
    """Check if core packages are installed AND numpy is the correct version."""
    python = get_python_executable()

    _fix_pth_file(python)

    # Verifies numpy is 1.x AND has working ndarray attribute (catches broken installs).
    # If numpy is 2.x or corrupted, we force a reinstall — this prevents the entire
    # voice/memory stack from silently failing at runtime.
    check_script = (
        "import sys\n"
        "try:\n"
        "    import numpy as np\n"
        "    _ = np.ndarray\n"
        "    import numpy.typing\n"
        "    if np.__version__.startswith('2.'):\n"
        "        print('numpy_wrong_version')\n"
        "        sys.exit(1)\n"
        "except Exception as e:\n"
        "    print('numpy_broken')\n"
        "    sys.exit(1)\n"
        "pkgs = ['fastapi','uvicorn','pyttsx3','chromadb',"
        "'sentence_transformers','psutil','keyboard','pynput']\n"
        "missing = []\n"
        "for p in pkgs:\n"
        "    try:\n"
        "        __import__(p)\n"
        "    except ImportError:\n"
        "        missing.append(p)\n"
        "if missing:\n"
        "    print(','.join(missing))\n"
        "    sys.exit(1)\n"
        "print('OK')\n"
    )

    try:
        result = subprocess.run(
            [python, '-c', check_script],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0
        )
        if result.returncode == 0:
            print("[BOOTSTRAP] All critical packages verified.")
            return True

        output = result.stdout.strip()

        # numpy is broken or wrong version — auto-fix
        if output in ("numpy_broken", "numpy_wrong_version"):
            print(f"[BOOTSTRAP] Numpy issue detected: {output}. Auto-fixing...")
            _repair_numpy(python)
            return False

        print(f"[BOOTSTRAP] Missing packages: {output}")
        return False
    except subprocess.TimeoutExpired:
        print("[BOOTSTRAP] Package check timed out after 15s")
        return False
    except Exception as e:
        print(f"[BOOTSTRAP] Package check failed: {e}")
        return False


def _repair_numpy(python_exe):
    """
    Force reinstall numpy 1.26.x when broken or upgraded to 2.x.
    Handles the 'no RECORD file' corruption case by manually deleting the folder
    before reinstall — pip cannot uninstall packages without RECORD metadata.
    """
    print("[BOOTSTRAP] Repairing numpy installation...")

    # Find site-packages dir for this Python
    try:
        result = subprocess.run(
            [python_exe, '-c',
             'import sys, os; print([p for p in sys.path if p.endswith("site-packages")][0])'],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0
        )
        site_packages = result.stdout.strip()
        if site_packages and os.path.isdir(site_packages):
            # Nuke corrupted numpy folders manually — pip can't uninstall broken ones
            import shutil
            for name in os.listdir(site_packages):
                lower = name.lower()
                if lower == 'numpy' or lower.startswith('numpy-') or lower.startswith('~umpy'):
                    target = os.path.join(site_packages, name)
                    try:
                        if os.path.isdir(target):
                            shutil.rmtree(target, ignore_errors=True)
                            print(f"[BOOTSTRAP] Removed corrupted: {name}")
                        else:
                            os.unlink(target)
                    except Exception as _e:
                        print(f"[BOOTSTRAP] Could not remove {name}: {_e}")
    except Exception as e:
        print(f"[BOOTSTRAP] Site-packages scan failed: {e}")

    # Now do a clean install with --no-deps to avoid pulling numpy 2.x from deps
    try:
        result = subprocess.run(
            [python_exe, '-m', 'pip', 'install',
             '--no-cache-dir', '--no-deps', '--force-reinstall',
             'numpy==1.26.4'],
            capture_output=True, text=True, timeout=180,
            creationflags=0x08000000 if platform.system() == 'Windows' else 0
        )

        if result.returncode == 0:
            # Verify the repair worked
            verify = subprocess.run(
                [python_exe, '-c',
                 'import numpy as np; assert np.__version__.startswith("1."); _ = np.ndarray; import numpy.typing'],
                capture_output=True, timeout=10,
                creationflags=0x08000000 if platform.system() == 'Windows' else 0
            )
            if verify.returncode == 0:
                print("[BOOTSTRAP] Numpy 1.26.4 verified working.")
                return True
            else:
                print("[BOOTSTRAP] Numpy installed but still broken.")
                return False
        else:
            print(f"[BOOTSTRAP] Numpy repair failed: {result.stderr[-300:]}")
            return False
    except Exception as e:
        print(f"[BOOTSTRAP] Numpy repair exception: {e}")
        return False


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

    # CRITICAL: numpy 1.26.x MUST install first and pinned.
    # numpy 2.x breaks torch, faster-whisper, ctranslate2, chromadb, and sentence_transformers
    # This is enforced at installer level to prevent the entire voice/memory stack from failing.
    critical_first = [
        "numpy>=1.26.0,<2.0.0",
        "python-multipart", "fastapi", "uvicorn[standard]", "websockets",
        "requests", "colorama", "psutil", "pyttsx3", "pywin32",
        "pycaw", "comtypes", "AppOpener", "ddgs", "SpeechRecognition",
        "pyaudio", "screen-brightness-control", "pyautogui", "keyboard",
        "pynput", "rapidfuzz"
    ]

    def _pkg_name(p):
        return p.split('==')[0].split('>=')[0].split('[')[0].strip().lower()

    # Incompatible on Windows without heavy C++ toolchains; Seven uses faster-whisper instead
    incompatible_win = {
        'nemo_toolkit', 'nemo-toolkit', 'nemo_toolkit[asr]', 'webrtcvad',
        'torch-audiomentations', 'pyannote.audio'
    }

    optional = {
        'resemblyzer', 'pyaudio', 'screen-brightness-control',
        'nemo_toolkit', 'nemo-toolkit', 'nemo_toolkit[asr]',
        'sounddevice', 'coloredlogs'
    }

    critical_set = {c.split('[')[0].lower() for c in critical_first}

    # Filter out known Linux-only / incompatible packages before pip runs
    filtered_packages = []
    for p in packages:
        name = _pkg_name(p)
        if name in incompatible_win:
            print(f"[BOOTSTRAP] Skipping incompatible/non-critical Windows package: {p}")
            continue
        filtered_packages.append(p)

    ordered = [p for p in filtered_packages if _pkg_name(p) in critical_set]
    remaining = [p for p in filtered_packages if _pkg_name(p) not in critical_set]
    install_order = ordered + remaining

    total = len(install_order)
    failed_optional = []
    install_start = time.time()

    for i, pkg in enumerate(install_order):
        pkg_display = pkg.split('==')[0].split('>=')[0].strip()
        raw_name = _pkg_name(pkg)
        is_optional = (raw_name in optional) or (raw_name not in critical_set)
        progress = int(((i + 1) / total) * 100)

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
                 '--retries', '3', '--timeout', '60', '--progress-bar', 'off'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=0x08000000 if platform.system() == 'Windows' else 0
            )

            hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True)
            hb_thread.start()

            try:
                _, stderr_output = process.communicate(timeout=300)
                result_returncode = process.wait(timeout=300)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr_output = process.communicate()
                stderr_output = "Timeout after 5 minutes"
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
                print(f"[BOOTSTRAP]   non-critical package skipped ({pkg_elapsed}s): {pkg_display}")
                continue
            err = stderr_output.strip()[-400:] if stderr_output else 'Unknown error'
            print(f"[BOOTSTRAP]   FAILED: {err}")
            _set('packages', status='error',
                 error=f'{pkg_display} install failed. Please click Retry.')
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


def _find_cached_ollama_installer():
    """Find a previously downloaded Ollama installer that is complete and valid."""
    temp_dir = tempfile.gettempdir()
    cached_path = os.path.join(temp_dir, "OllamaSetup_cached.exe")

    if os.path.exists(cached_path):
        try:
            size = os.path.getsize(cached_path)
            if size > 100_000_000:  # Valid installer is ~200MB
                print(f"[BOOTSTRAP] Using verified cached installer ({round(size/1024/1024, 1)} MB)")
                return cached_path
            else:
                os.unlink(cached_path)
        except Exception:
            pass
    return None


def _safe_rename_with_retry(src, dst, max_attempts=10):
    """
    Windows Defender locks files during scan. Retry rename with exponential backoff.
    This is the industry-standard fix for WinError 32 on freshly-written executables.
    """
    import time as _t
    for attempt in range(max_attempts):
        try:
            if os.path.exists(dst):
                try:
                    os.unlink(dst)
                except PermissionError:
                    _t.sleep(0.5 * (attempt + 1))
                    continue
            os.rename(src, dst)
            return True
        except (PermissionError, OSError) as e:
            if attempt == max_attempts - 1:
                # Last attempt: copy instead of rename (works even if src is locked for read-only)
                try:
                    import shutil
                    shutil.copy2(src, dst)
                    try:
                        os.unlink(src)
                    except Exception:
                        pass
                    return True
                except Exception as copy_err:
                    raise Exception(f"Rename failed after {max_attempts} attempts: {e}. Copy also failed: {copy_err}")
            _t.sleep(0.4 * (attempt + 1))
    return False


def download_ollama_installer():
    """Download OllamaSetup.exe with monotonic progress, crash recovery, and cache reuse."""
    cached = _find_cached_ollama_installer()
    if cached:
        _set('ollama_install', status='running', progress=100,
             current="Installer ready in cache. Requesting Windows permission...")
        return cached

    _set('ollama_install', status='running', progress=0,
         current="Connecting to Ollama servers...", error=None)
    temp_dir = tempfile.gettempdir()
    part_dest = os.path.join(temp_dir, "OllamaSetup_download.tmp")
    final_dest = os.path.join(temp_dir, "OllamaSetup_cached.exe")

    if os.path.exists(part_dest):
        try:
            os.unlink(part_dest)
        except Exception:
            pass

    print("[BOOTSTRAP] Starting Ollama download...")

    # Rolling average for smooth speed display
    speed_samples = []
    last_ui_update = [0.0]

    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SEVEN/1.3.1'}

        # Retry up to 3 times on connection drops
        for attempt in range(3):
            try:
                response = requests.get(OLLAMA_DOWNLOAD_URL, headers=headers,
                                        stream=True, timeout=60, allow_redirects=True)
                response.raise_for_status()
                break
            except Exception as conn_err:
                if attempt == 2:
                    raise
                print(f"[BOOTSTRAP] Connection failed (attempt {attempt+1}/3): {conn_err}")
                time.sleep(3)

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        start_time = time.time()
        last_downloaded = 0
        last_sample_time = start_time

        f = open(part_dest, 'wb')
        try:
            for chunk in response.iter_content(chunk_size=262144):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()

                    if now - last_sample_time >= 0.5:
                        bytes_diff = downloaded - last_downloaded
                        time_diff = now - last_sample_time
                        instant_bps = bytes_diff / time_diff if time_diff > 0 else 0
                        speed_samples.append(instant_bps)
                        if len(speed_samples) > 8:
                            speed_samples.pop(0)
                        last_downloaded = downloaded
                        last_sample_time = now

                    if now - last_ui_update[0] >= 0.4:
                        last_ui_update[0] = now
                        avg_speed_bps = sum(speed_samples) / len(speed_samples) if speed_samples else 0
                        speed_mb_s = round(avg_speed_bps / (1024 * 1024), 2)

                        if total_size > 0:
                            pct = min(int((downloaded / total_size) * 100), 99)
                            dl_mb = round(downloaded / (1024 * 1024), 1)
                            tot_mb = round(total_size / (1024 * 1024), 1)

                            # GLOBAL monotonic guard — stored in shared state,
                            # survives function retries and thread restarts
                            with _state_lock:
                                prev_pct = _bootstrap_state["ollama_install"].get("max_pct", 0)
                                prev_mb = _bootstrap_state["ollama_install"].get("max_dl_mb", 0.0)
                                if pct > prev_pct:
                                    _bootstrap_state["ollama_install"]["max_pct"] = pct
                                else:
                                    pct = prev_pct
                                if dl_mb > prev_mb:
                                    _bootstrap_state["ollama_install"]["max_dl_mb"] = dl_mb
                                else:
                                    dl_mb = prev_mb

                            bytes_rem = total_size - downloaded
                            eta_sec = bytes_rem / avg_speed_bps if avg_speed_bps > 0 else 0

                            if eta_sec < 60:
                                eta_str = f"{int(eta_sec)}s left"
                            elif eta_sec < 3600:
                                eta_str = f"{int(eta_sec // 60)}m {int(eta_sec % 60)}s left"
                            else:
                                eta_str = f"{int(eta_sec // 3600)}h {int((eta_sec % 3600) // 60)}m left"

                            _set('ollama_install',
                                 progress=pct,
                                 current=f"Downloading Ollama runtime · {dl_mb} / {tot_mb} MB · {speed_mb_s} MB/s · {eta_str}")
                        else:
                            dl_mb = round(downloaded / (1024 * 1024), 1)
                            _set('ollama_install', progress=50,
                                 current=f"Downloading Ollama runtime · {dl_mb} MB · {speed_mb_s} MB/s")
        finally:
            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                pass
            f.close()

        response.close()

        actual_size = os.path.getsize(part_dest)
        if actual_size < 100_000_000:
            if os.path.exists(part_dest):
                os.unlink(part_dest)
            raise Exception(f"Download incomplete ({round(actual_size / 1024 / 1024, 1)} MB). Expected ~200MB.")

        _set('ollama_install', progress=100, current="Verifying download...")
        time.sleep(2.0)
        _safe_rename_with_retry(part_dest, final_dest, max_attempts=15)

        _set('ollama_install', progress=100, current="Download complete. Preparing installer...")
        print(f"[BOOTSTRAP] Ollama download verified: {final_dest}")
        time.sleep(0.5)
        return final_dest

    except Exception as e:
        err_msg = str(e)
        if os.path.exists(part_dest):
            try:
                os.unlink(part_dest)
            except Exception:
                pass

        _set('ollama_install', status='error',
             error=f"Download failed: {err_msg}. Click Retry to resume.")
        print(f"[BOOTSTRAP] Ollama download error: {err_msg}")
        return None


def install_ollama_silent(installer_path):
    """Run OllamaSetup.exe with Inno Setup silent flags and prompt Windows UAC."""
    print(f"[BOOTSTRAP] Launching Ollama installer: {installer_path}")

    if not os.path.exists(installer_path):
        _set('ollama_install', status='error', error='Installer missing. Click Retry to download.')
        return False

    # Notify frontend to display the urgent UAC attention banner
    _set('ollama_install', status='running', progress=100, current="UAC_PROMPT_ACTIVE")
    time.sleep(0.5)

    try:
        import ctypes
        # Inno Setup standard flags: /VERYSILENT /NORESTART /SP- (Skip prompt)
        params = "/VERYSILENT /NORESTART /SP-"
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", installer_path, params, None, 1
        )

        if ret > 32:
            print("[BOOTSTRAP] UAC accepted. Extracting Ollama binaries in background...")
            _set('ollama_install', status='running', progress=100, current="Extracting and configuring Ollama runtime...")

            deadline = time.time() + 180
            while time.time() < deadline:
                if is_ollama_installed():
                    _set('ollama_install', status='done', progress=100, current="Ollama installed successfully.")
                    print("[BOOTSTRAP] Ollama binary verified.")
                    return True
                time.sleep(2)

            _set('ollama_install', status='error', error='Installation took too long. Click Retry to try again.')
            return False
        else:
            print(f"[BOOTSTRAP] Windows UAC prompt was declined by user (error code {ret})")
            # Keep installer intact so retry requires 0 download time
            _set('ollama_install', status='error', error='PERMISSION_DENIED')
            return False

    except Exception as e:
        print(f"[BOOTSTRAP] Installation exception: {e}")
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


def retrigger_uac_only():
    """
    Re-open the Windows UAC prompt without re-downloading Ollama.
    Called when user initially clicked NO but wants to grant permission now.
    Skips the entire download phase — uses cached installer.
    """
    if is_ollama_installed():
        print("[BOOTSTRAP] Ollama already installed — no UAC needed.")
        _set('ollama_install', status='done', progress=100,
             current="Already installed.")
        with _state_lock:
            _bootstrap_state['overall_ready'] = True
        return True

    cached = _find_cached_ollama_installer()
    if not cached:
        print("[BOOTSTRAP] No cached installer — falling back to full setup.")
        return setup_ollama()

    print("[BOOTSTRAP] Re-triggering UAC prompt with cached installer...")
    _set('ollama_install', status='running', progress=100, error=None,
         current="Re-requesting Windows permission...")

    ok = install_ollama_silent(cached)
    if ok:
        # Also start Ollama immediately after successful install
        return start_ollama()
    return False


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
    Crash-proof: wraps entire flow in try/except so the API server never dies.
    Resumes from checkpoint if a previous run was interrupted.
    """
    _set('packages', status='running', progress=5, current='Initializing environment deployment...')
    _set('ollama_install', status='pending', progress=0, current='Waiting for packages...')
    _set('ollama_start', status='pending', current='Waiting...')

    def _run():
        try:
            print("[BOOTSTRAP] Starting environment setup...")
            checkpoint = _load_bootstrap_checkpoint()

            # ── Step 1: Python packages ──
            if checkpoint.get("packages_done") and check_packages_installed():
                print("[BOOTSTRAP] Packages already installed (checkpoint).")
                _set('packages', status='done', progress=100, current='Already installed')
            elif check_packages_installed():
                print("[BOOTSTRAP] Packages already installed (verified).")
                _set('packages', status='done', progress=100, current='Already installed')
                _save_bootstrap_checkpoint()
            else:
                ok = install_packages()
                if not ok:
                    print("[BOOTSTRAP] Package install failed — cannot continue")
                    if on_complete:
                        on_complete(False)
                    return
                _save_bootstrap_checkpoint()

            # ── Step 2: Ollama install ──
            if is_ollama_installed():
                print("[BOOTSTRAP] Ollama already installed.")
                _set('ollama_install', status='done', progress=100, current='Already installed')
            else:
                ollama_ok = setup_ollama()
                if not ollama_ok:
                    if is_ollama_installed():
                        print("[BOOTSTRAP] Ollama found after install attempt.")
                        _set('ollama_install', status='done', progress=100)
                    else:
                        print("[BOOTSTRAP] Ollama install failed.")
                        if on_complete:
                            on_complete(False)
                        return

            # ── Step 3: Start Ollama ──
            if is_ollama_running():
                print("[BOOTSTRAP] Ollama already running.")
                _set('ollama_start', status='done')
            else:
                ok = start_ollama()
                if not ok:
                    time.sleep(3)
                    ok = start_ollama()
                    if not ok:
                        if on_complete:
                            on_complete(False)
                        return

            with _state_lock:
                _bootstrap_state['overall_ready'] = True

            _save_bootstrap_checkpoint()
            print("[BOOTSTRAP] Environment setup complete.")
            if on_complete:
                on_complete(True)

        except Exception as e:
            # CRITICAL: Never let bootstrap crash the API server.
            # Log the error and set state so the frontend shows a retry button.
            import traceback
            traceback.print_exc()
            print(f"[BOOTSTRAP] Setup crashed (non-fatal): {e}")
            _set('packages', status='error',
                 error=f'Setup interrupted: {str(e)[:200]}. Click Retry to resume.')

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