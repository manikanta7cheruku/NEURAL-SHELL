"""
backend/routes/setup.py
Handles: /api/setup/*, /api/bootstrap/*
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import threading

router = APIRouter()

# ── Voice preview process management ──
_preview_process = None
_preview_lock    = threading.Lock()


class SetupCompleteRequest(BaseModel):
    name:         str
    email:        str
    referral_code: Optional[str] = ""
    wake_word:    Optional[str]  = "seven"
    voice_index:  Optional[int]  = 0
    model_name:   Optional[str]  = ""


@router.get("/api/setup/existing-identity")
def get_existing_identity():
    """Check if device has previously registered identity on server."""
    try:
        import telemetry as tel
        import requests as _req

        device_id  = tel.get_device_id()
        SERVER_URL = "https://seven-server-a825.onrender.com"
        r = _req.get(f"{SERVER_URL}/api/device/{device_id}", timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {"found": True, "name": data.get("name"), "email": data.get("email")}
        return {"found": False}
    except Exception as e:
        print(f"[SETUP] Identity check failed: {e}")
        return {"found": False}


@router.post("/api/setup/complete")
def complete_setup(req: SetupCompleteRequest):
    """Called when user finishes setup wizard."""
    import config

    name  = req.name.strip()
    email = req.email.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    wake    = req.wake_word.lower().strip() if req.wake_word else "seven"
    updates = {
        "setup_complete": True,
        "email":          email,
        "identity": {
            **config.KEY.get("identity", {}),
            "user_name":  name,
            "wake_words": [wake, f"hey {wake}"],
        },
        "voice": {"voice_index": req.voice_index},
    }

    if req.model_name:
        updates["brain"] = {**config.KEY.get("brain", {}), "model_name": req.model_name}

    success = config.update_config(updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save configuration")

    # Force Registration to Render Backend
    # Force Registration/Update to Render Backend
    try:
        import requests
        import telemetry
        device_id = telemetry.get_device_id()
        
        # 1. Register or update the device record
        resp = requests.post(
            "https://seven-server-a825.onrender.com/api/register",
            json={
                "device_id": device_id,
                "email": email,
                "name": name,
                "country": "Unknown",
                "referral_code": req.referral_code.strip() if req.referral_code else None
            },
            timeout=10
        )
        
        # 2. If the API returned a conflict (already registered), we explicitly update the profile
        if resp.status_code == 409 or resp.status_code == 200:
            requests.post(
                "https://seven-server-a825.onrender.com/api/device/update",
                json={
                    "device_id": device_id,
                    "email": email,
                    "name": name
                },
                timeout=10
            )
            
        print(f"[SETUP] Render backend sync successful for {email}")
    except Exception as e:
        print(f"[SETUP] Render backend sync failed (non-fatal): {e}")

    return {"success": True, "message": f"Welcome to Seven, {name}."}


@router.post("/api/setup/preview-voice")
async def preview_voice(request: Request):
    """Preview a voice. Interrupts any currently playing preview first."""
    global _preview_process

    try:
        body = await request.json()
    except Exception:
        body = {}

    engine_name = body.get("engine", "sapi")
    voice_id    = body.get("voice_id", "0")
    sample_text = "Hello. I am Seven, your private AI assistant."

    print(f"[PREVIEW] engine={engine_name} voice_id={voice_id}")

    def _stop_current():
        global _preview_process
        with _preview_lock:
            if _preview_process and _preview_process.poll() is None:
                try:
                    _preview_process.kill()
                    _preview_process.wait(timeout=2)
                    print("[PREVIEW] Stopped previous preview")
                except Exception as e:
                    print(f"[PREVIEW] Stop error: {e}")
            _preview_process = None

    def _speak_sapi_preview(vid):
        global _preview_process
        import subprocess as sp, sys as _sys

        _preview_exe = _sys.executable.replace('python.exe', 'pythonw.exe') if _sys.platform == 'win32' else _sys.executable
        
        _si = None
        _cflags = 0
        if _sys.platform == 'win32':
            _si = sp.STARTUPINFO()
            _si.dwFlags |= sp.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0
            _cflags = 0x08000000 | 0x00000008 | 0x00000200

        # Safely escape the voice ID for the python script string
        # Use raw string r'...' to preserve Windows Registry backslashes in PyTTSx3
        clean_id = str(vid).strip()
        
        script = f"""
import pyttsx3
import sys
import time
try:
    engine = pyttsx3.init('sapi5')
    voices = engine.getProperty('voices')
    target = r'{clean_id}'
    for v in voices:
        if v.id.lower() == target.lower() or v.name.lower() == target.lower():
            engine.setProperty('voice', v.id)
            break
    engine.setProperty('rate', 170)
    engine.setProperty('volume', 1.0)
    engine.say('{sample_text}')
    engine.runAndWait()
    engine.stop()
    time.sleep(0.2)
except Exception as e:
    sys.exit(1)
"""
        with _preview_lock:
            _preview_process = sp.Popen(
                [_preview_exe, "-c", script],
                stdout=sp.PIPE, stderr=sp.PIPE,
                startupinfo=_si, creationflags=_cflags
            )
            proc = _preview_process
        proc.wait(timeout=15)

    def _speak():
        global _preview_process
        _stop_current()

        try:
            if engine_name == "piper":
                import subprocess as sp, tempfile

                here     = os.path.dirname(os.path.abspath(__file__))
                root     = os.path.dirname(os.path.dirname(here))
                app_path = os.environ.get("SEVEN_APP_PATH", "")

                piper_dir = None
                for c in [
                    os.path.join(app_path, "mouth", "piper"),
                    os.path.join(root,     "mouth", "piper"),
                ]:
                    if os.path.isdir(c) and os.path.exists(os.path.join(c, "piper.exe")):
                        piper_dir = c
                        break

                if not piper_dir:
                    _speak_sapi_preview(voice_id)
                    return

                model_path = os.path.join(piper_dir, "voices", f"{voice_id}.onnx")
                if not os.path.exists(model_path):
                    _speak_sapi_preview(voice_id)
                    return

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name

                import sys as _sys2
                _si2     = None
                _cflags2 = 0
                if _sys2.platform == 'win32':
                    _si2 = sp.STARTUPINFO()
                    _si2.dwFlags |= sp.STARTF_USESHOWWINDOW
                    _si2.wShowWindow = 0
                    _cflags2 = 0x08000000 | 0x00000008 | 0x00000200

                with _preview_lock:
                    _preview_process = sp.Popen(
                        [os.path.join(piper_dir, "piper.exe"),
                         "--model", model_path, "--output_file", tmp_path],
                        stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, cwd=piper_dir,
                        startupinfo=_si2, creationflags=_cflags2,
                    )
                    proc = _preview_process

                try:
                    proc.stdin.write(sample_text.encode("utf-8"))
                    proc.stdin.close()
                    proc.wait(timeout=15)
                except Exception as e:
                    print(f"[PREVIEW] Piper wait error: {e}")
                    return

                if proc.returncode == 0 and os.path.exists(tmp_path):
                    try:
                        import winsound
                        winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
                    except Exception:
                        ps_script = (
                            f"$p = New-Object System.Media.SoundPlayer('{tmp_path}');"
                            f"$p.PlaySync();"
                        )
                        sp.run(["powershell", "-NoProfile", "-Command", ps_script],
                               capture_output=True, timeout=30,
                               startupinfo=_si2, creationflags=_cflags2)
                    try:
                        os.unlink(tmp_path)
                    except Exception as e:
                        print(f"[SETUP] Temp file cleanup failed: {e}")
                else:
                    _speak_sapi_preview(voice_id)
            else:
                _speak_sapi_preview(voice_id)

        except Exception as e:
            print(f"[PREVIEW] Error: {e}")
            import traceback
            traceback.print_exc()

    threading.Thread(target=_speak, daemon=True).start()
    return {"success": True}


@router.get("/api/setup/voices")
def get_available_voices():
    """Returns Piper TTS voices + Windows SAPI voices."""
    result = []

    PIPER_VOICES = [
        {"engine": "piper", "voice_id": "en_US-ryan-high",   "name": "Ryan",  "gender": "Male",   "language": "American English", "quality": "Natural", "flag": "🇺🇸"},
        {"engine": "piper", "voice_id": "en_US-amy-medium",  "name": "Amy",   "gender": "Female", "language": "American English", "quality": "Natural", "flag": "🇺🇸"},
        {"engine": "piper", "voice_id": "en_GB-alan-medium", "name": "Alan",  "gender": "Male",   "language": "British English",  "quality": "Natural", "flag": "🇬🇧"},
        {"engine": "piper", "voice_id": "en_IN-maya-medium", "name": "Maya",  "gender": "Female", "language": "Indian English",   "quality": "Natural", "flag": "🇮🇳"},
    ]

    # Load Piper Voices
    try:
        app_path = os.environ.get("SEVEN_APP_PATH", "")
        here     = os.path.dirname(os.path.abspath(__file__))
        root     = os.path.dirname(os.path.dirname(here))

        piper_voices_dir = None
        for c in [
            os.path.join(app_path, "mouth", "piper", "voices"),
            os.path.join(root,     "mouth", "piper", "voices"),
        ]:
            if os.path.isdir(c):
                piper_voices_dir = c
                break

        for i, v in enumerate(PIPER_VOICES):
            installed = False
            if piper_voices_dir:
                installed = os.path.exists(os.path.join(piper_voices_dir, f"{v['voice_id']}.onnx"))
            result.append({
                "index": i, "engine": "piper", "voice_id": v["voice_id"],
                "name": v["name"], "gender": v["gender"], "language": v["language"],
                "quality": v["quality"], "flag": v["flag"], "installed": installed,
            })
    except Exception as e:
        print(f"[VOICES] Piper scan error: {e}")

    # Load SAPI Voices
    try:
        import pyttsx3
        engine = pyttsx3.init('sapi5')
        voices = engine.getProperty('voices')
        engine.stop()
        
        start_idx = len(result)
        for i, v in enumerate(voices or []):
            raw = v.name or f"Voice {i}"
            clean = raw.replace("Microsoft ", "").split(" Desktop")[0].split(" -")[0].strip()
            gender = "Female" if any(n in clean.lower() for n in ["zira", "hazel", "helena", "jenny", "aria"]) else "Male"
            result.append({
                "index": start_idx + i, 
                "engine": "sapi", 
                "voice_id": v.id, 
                "name": clean, 
                "gender": gender, 
                "language": "English", 
                "quality": "Standard", 
                "installed": True
            })
    except Exception as e: 
        print(f"[VOICES] SAPI scan error: {e}")
        
    return {"voices": result, "count": len(result)}


# ── Whisper STT model management ──
#
# Not to be confused with the LLM models in StepModel.jsx. This controls
# the speech-to-text engine only — how Seven turns your voice into text,
# before that text ever reaches the LLM.

WHISPER_MODELS = [
    {
        "id": "tiny.en", "label": "Tiny", "tag": "FASTEST",
        "size_mb": 75, "param": "39M",
        "headline": "Fastest transcription, most mistakes",
        "cpu_speed": "Near instant", "gpu_speed": "Near instant",
        "accuracy": "Basic, best for short simple commands",
    },
    {
        "id": "base.en", "label": "Base", "tag": "LIGHT",
        "size_mb": 145, "param": "74M",
        "headline": "Quick responses on modest hardware",
        "cpu_speed": "Fast", "gpu_speed": "Near instant",
        "accuracy": "Fair, occasional mistranscriptions",
    },
    {
        "id": "small.en", "label": "Small", "tag": "BALANCED",
        "size_mb": 484, "param": "244M",
        "headline": "Solid accuracy without a GPU",
        "cpu_speed": "Moderate", "gpu_speed": "Fast",
        "accuracy": "Good, recommended for most CPU-only users",
    },
    {
        "id": "medium.en", "label": "Medium", "tag": "RECOMMENDED",
        "size_mb": 1500, "param": "769M",
        "headline": "Seven's current default, strong accuracy",
        "cpu_speed": "Slow without a GPU", "gpu_speed": "Fast",
        "accuracy": "Very good, fewer hallucinations on silence",
    },
    {
        "id": "large-v3", "label": "Large", "tag": "BEST ACCURACY",
        "size_mb": 3100, "param": "1550M",
        "headline": "Best possible transcription quality",
        "cpu_speed": "Very slow without a GPU", "gpu_speed": "Moderate",
        "accuracy": "Excellent, near-human transcription accuracy",
    },
]

_whisper_download_state = {
    "downloading": False,
    "model":       None,
    "progress":    0,
    "error":       None,
}
_whisper_download_lock = threading.Lock()


def _is_whisper_model_installed(model_id: str) -> bool:
    """
    Check if a faster-whisper model is already downloaded on disk.
    Uses direct folder size check only. scan_cache_dir() is unreliable
    across huggingface_hub versions and has been removed.
    """
    home    = os.path.expanduser("~")
    base_id = model_id.split(".")[0]

    candidates = [
        os.path.join(home, ".cache", "huggingface", "hub", f"models--Systran--faster-whisper-{model_id}"),
        os.path.join(home, ".cache", "huggingface", "hub", f"models--Systran--faster-whisper-{base_id}"),
        os.path.join(home, ".cache", "huggingface", "hub", f"models--guillaumekln--faster-whisper-{model_id}"),
        os.path.join(home, ".cache", "huggingface", "hub", f"models--guillaumekln--faster-whisper-{base_id}"),
    ]

    for folder in candidates:
        if not os.path.isdir(folder):
            continue
        total = 0
        for root, _, files in os.walk(folder):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        if total > 1 * 1024 * 1024:
            return True

    return False


@router.get("/api/setup/whisper-models")
def get_whisper_models():
    """List available Whisper STT model sizes with install status."""
    import json as _json
    cfg_path = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "config.json"
    )
    current = "medium.en"
    
    # ALWAYS read from file, never from config.KEY (which can be stale)
    try:
        # Force fresh read with no caching
        with open(cfg_path, "r", encoding="utf-8") as _f:
            cfg_data = _json.load(_f)
            current = cfg_data.get("brain", {}).get("whisper_model", "medium.en")
            _log_config_change("GET /whisper-models", current)
            print(f"[WHISPER] GET models - read from file: {current}")
            
        # Also check what config.KEY says (for debugging)
        import config
        in_memory = config.KEY.get("brain", {}).get("whisper_model", "N/A")
        print(f"[WHISPER] GET models - config.KEY says: {in_memory}")
        
        if current != in_memory and in_memory != "N/A":
            print(f"[WHISPER] WARNING: File says {current} but config.KEY says {in_memory} - using file value")
            # Force update config.KEY to match file
            config.KEY.setdefault("brain", {})["whisper_model"] = current
            
    except Exception as e:
        print(f"[WHISPER] GET models - config read error: {e}, using default: {current}")
        pass
    
    result = []
    for m in WHISPER_MODELS:
        result.append({
            **m,
            "installed": _is_whisper_model_installed(m["id"]),
            "active":    m["id"] == current,
        })
    
    print(f"[WHISPER] GET models - returning current: {current}")
    return {"models": result, "current": current}


@router.post("/api/setup/whisper-model")
def set_whisper_model(data: dict):
    """
    Select a Whisper model. Saves to config immediately.
    If not yet downloaded, starts a background download — frontend
    should poll /api/setup/whisper-download-status for progress.
    """
    import config
    import json as _json

    model_id  = data.get("model", "").strip()
    valid_ids = [m["id"] for m in WHISPER_MODELS]
    if model_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Unknown model")

    print(f"[WHISPER] POST /whisper-model called with: {model_id}")
    
    # Write directly to config.json file — config.update_config() does NOT write to disk!
    cfg_path = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "config.json"
    )
    
    # Read current config from file
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg_data = _json.load(f)
    except Exception as e:
        print(f"[WHISPER] Failed to read config: {e}")
        cfg_data = {}
    
    # Update whisper_model
    if "brain" not in cfg_data:
        cfg_data["brain"] = {}
    cfg_data["brain"]["whisper_model"] = model_id
    
    # Write to file with forced flush
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            _json.dump(cfg_data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        print(f"[WHISPER] Wrote {model_id} to config.json and flushed to disk")
    except Exception as e:
        print(f"[WHISPER] Failed to write config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}")
    
    # Verify write by reading back from file
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            verify_data = _json.load(f)
            verified = verify_data.get("brain", {}).get("whisper_model")
            print(f"[WHISPER] Verified file write: {verified}")
            
            if verified != model_id:
                print(f"[WHISPER] ERROR: Wrote {model_id} but file contains {verified}!")
                raise HTTPException(status_code=500, detail="Config verification failed")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[WHISPER] Verification read failed: {e}")
    
    # Also update in-memory config.KEY
    config.KEY.setdefault("brain", {})["whisper_model"] = model_id
    print(f"[WHISPER] Updated config.KEY to {model_id}")
    
    _log_config_change(f"POST /whisper-model", model_id)

    if _is_whisper_model_installed(model_id):
        print(f"[WHISPER] Model {model_id} already installed, returning immediately")
        return {"success": True, "installed": True, "current": model_id,
                "message": "Model already installed. Restart Seven to apply."}

    with _whisper_download_lock:
        if _whisper_download_state["downloading"]:
            return {"success": True, "installed": False, "current": model_id,
                    "message": "A download is already in progress."}
        _whisper_download_state.update({
            "downloading": True, "model": model_id, "progress": 5, "error": None
        })

    def _download():
        print(f"[WHISPER] Download thread started for {model_id}")
        model_meta = next((m for m in WHISPER_MODELS if m["id"] == model_id), None)
        total_mb   = model_meta["size_mb"] if model_meta else 500
        stop_flag  = {"done": False}

        def _watch_progress():
            import time as _t
            home    = os.path.expanduser("~")
            base_id = model_id.split(".")[0]
            folders = [
                os.path.join(home, ".cache", "huggingface", "hub", f"models--Systran--faster-whisper-{model_id}"),
                os.path.join(home, ".cache", "huggingface", "hub", f"models--Systran--faster-whisper-{base_id}"),
            ]
            last_pct = 5
            while not stop_flag["done"]:
                try:
                    total_bytes = 0
                    for folder in folders:
                        if os.path.isdir(folder):
                            for root, _, files in os.walk(folder):
                                for fn in files:
                                    try:
                                        total_bytes += os.path.getsize(os.path.join(root, fn))
                                    except OSError:
                                        pass
                    current_mb = total_bytes / (1024 * 1024)
                    pct = min(99, int((current_mb / total_mb) * 100))
                    if pct < 5:
                        pct = 5
                    if pct != last_pct:
                        last_pct = pct
                        with _whisper_download_lock:
                            _whisper_download_state["progress"] = pct
                except Exception:
                    pass
                _t.sleep(0.5)

        watcher = threading.Thread(target=_watch_progress, daemon=True)
        watcher.start()

        try:
            print(f"[WHISPER] Initializing WhisperModel to download {model_id}")
            from faster_whisper import WhisperModel
            # cpu/int8 used deliberately here only to trigger the download —
            # this is a one-time cache warm-up, not how the model runs later.
            # ears/core.py loads the real model with GPU if available.
            WhisperModel(model_id, device="cpu", compute_type="int8")
            stop_flag["done"] = True
            print(f"[WHISPER] Download completed for {model_id}")
            
            # Re-verify config after download to catch any overwrites
            import config as cfg_check
            final_model = cfg_check.KEY.get("brain", {}).get("whisper_model")
            if final_model != model_id:
                print(f"[WHISPER] WARNING: After download, config shows {final_model} instead of {model_id}!")
            with _whisper_download_lock:
                _whisper_download_state.update({
                    "downloading": False, "progress": 100, "error": None
                })
        except Exception as e:
            stop_flag["done"] = True
            with _whisper_download_lock:
                _whisper_download_state.update({
                    "downloading": False, "error": str(e)
                })

    print(f"[WHISPER] Starting download thread for {model_id}")
    threading.Thread(target=_download, daemon=True).start()
    return {"success": True, "installed": False, "current": model_id, "message": "Download started."}


@router.get("/api/setup/whisper-download-status")
def get_whisper_download_status():
    with _whisper_download_lock:
        return dict(_whisper_download_state)


# ── Bootstrap endpoints ──

@router.get("/api/bootstrap/status")
def get_bootstrap_status():
    """Poll for live environment setup progress."""
    try:
        try:
            from backend.bootstrap import get_state
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from bootstrap import get_state
        return get_state()
    except Exception as e:
        return {"error": str(e), "overall_ready": False}


@router.post("/api/bootstrap/start")
def start_bootstrap():
    """Start the environment setup sequence."""
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import bootstrap
        bootstrap.run_environment_setup()
        return {"success": True, "message": "Bootstrap started"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/bootstrap/pull-model")
def pull_model_endpoint(data: dict):
    """Start pulling an Ollama model."""
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import bootstrap
        model = data.get("model", "").strip()
        if not model:
            raise HTTPException(status_code=400, detail="model name required")
        bootstrap.run_model_pull(model)
        return {"success": True, "model": model, "message": "Pull started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/bootstrap/models-installed")
def get_installed_models():
    """
    Returns list of Ollama models already pulled on this machine.
    StepModel calls this to skip download if model already exists.
    """
    try:
        import urllib.request as _ur
        import json as _js
        with _ur.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            data = _js.loads(r.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            return {"installed": models, "count": len(models)}
    except Exception:
        return {"installed": [], "count": 0}


@router.get("/api/bootstrap/check")
def check_environment():
    """Quick environment health check."""
    try:
        try:
            from backend.bootstrap import check_packages_installed, is_ollama_installed, is_ollama_running
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from bootstrap import check_packages_installed, is_ollama_installed, is_ollama_running

        return {
            "packages_installed": check_packages_installed(),
            "ollama_installed":   is_ollama_installed(),
            "ollama_running":     is_ollama_running(),
            "needs_setup":        not (check_packages_installed() and is_ollama_installed())
        }
    except Exception as e:
        return {"packages_installed": False, "ollama_installed": False,
                "ollama_running": False, "needs_setup": True, "error": str(e)}


@router.post("/api/bootstrap/start-ollama")
def start_ollama_endpoint():
    """Start Ollama service if not already running."""
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import bootstrap
        threading.Thread(target=bootstrap.start_ollama, daemon=True).start()
        return {"success": True, "message": "Starting Ollama"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/bootstrap/retry-uac")
def retry_uac_endpoint():
    """
    Re-trigger the Windows UAC prompt without re-downloading Ollama.
    Called from the frontend when user clicks 'Grant Permission' after initially declining.
    """
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import bootstrap
        threading.Thread(target=bootstrap.retrigger_uac_only, daemon=True).start()
        return {"success": True, "message": "Re-requesting Windows permission"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
    # Add this right after the imports at the top, after "router = APIRouter()"
_last_whisper_model = None
_config_write_log = []

def _log_config_change(source: str, model: str):
    """Log all whisper_model changes to track what's overwriting it."""
    global _last_whisper_model, _config_write_log
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    if model != _last_whisper_model:
        entry = f"[{timestamp}] {source}: {_last_whisper_model} → {model}"
        print(f"[WHISPER] CHANGE: {entry}")
        _config_write_log.append(entry)
        _last_whisper_model = model
        
        # Keep only last 20 changes
        if len(_config_write_log) > 20:
            _config_write_log.pop(0)

@router.get("/api/setup/whisper-debug")
def get_whisper_debug():
    """Debug endpoint to see all whisper_model changes."""
    return {"changes": _config_write_log, "current": _last_whisper_model}