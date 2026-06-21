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
        SERVER_URL = "https://seven-server-u2rp.onrender.com"
        r = _req.get(f"{SERVER_URL}/api/device/{device_id}", timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {"found": True, "name": data.get("name"), "email": data.get("email")}
        return {"found": False}
    except Exception:
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

    try:
        import telemetry
        telemetry.save_email(email)
    except Exception:
        pass

    try:
        import server_sync
        import license as license_module
        device_id = license_module.get_device_id()
        server_sync.register_device(
            device_id=device_id,
            email=email,
            name=name,
            referral_code=req.referral_code or None
        )
    except Exception as e:
        print(f"[SETUP] Server sync warning: {e}")

    if req.referral_code and req.referral_code.strip():
        try:
            import server_sync
            import telemetry as tel
            device_id = tel.get_device_id()
            server_sync._post("/api/register", {
                "device_id":     device_id,
                "email":         email,
                "name":          name,
                "country":       None,
                "referral_code": req.referral_code.strip()
            })
            print(f"[SETUP] Referral code registered: {req.referral_code}")
        except Exception as e:
            print(f"[SETUP] Referral register warning: {e}")

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

        here     = os.path.dirname(os.path.abspath(__file__))
        root     = os.path.dirname(os.path.dirname(here))
        app_path = os.environ.get("SEVEN_APP_PATH", "")

        speaker_candidates = [
            os.path.join(app_path, "mouth", "speaker.py"),
            os.path.join(root,     "mouth", "speaker.py"),
        ]
        speaker_path = next((c for c in speaker_candidates if os.path.exists(c)), None)
        if not speaker_path:
            print("[PREVIEW] speaker.py not found")
            return

        idx = vid if str(vid).isdigit() else "0"
        with _preview_lock:
            _preview_process = sp.Popen(
                [_sys.executable, "-c",
                 f"""
import pyttsx3
engine = pyttsx3.init()
voices = engine.getProperty('voices')
idx = {idx}
if voices and idx < len(voices):
    engine.setProperty('voice', voices[idx].id)
engine.setProperty('rate', 165)
engine.setProperty('volume', 1.0)
engine.say('{sample_text}')
engine.runAndWait()
"""],
                stdout=sp.PIPE, stderr=sp.PIPE,
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

                with _preview_lock:
                    _preview_process = sp.Popen(
                        [os.path.join(piper_dir, "piper.exe"),
                         "--model", model_path, "--output_file", tmp_path],
                        stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, cwd=piper_dir,
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
                               capture_output=True, timeout=30)
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
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

    try:
        import pyttsx3
        engine      = pyttsx3.init()
        sapi_voices = engine.getProperty('voices')
        engine.stop()
        female_names = ["zira", "hazel", "helena", "linda", "susan",
                        "eva", "aria", "jenny", "michelle", "emma"]
        for i, v in enumerate(sapi_voices or []):
            raw    = v.name or f"Voice {i}"
            clean  = raw.replace("Microsoft ", "").split(" Desktop")[0].split(" -")[0].strip()
            gender = "Female" if any(n in clean.lower() for n in female_names) else "Male"
            lang   = "English"
            if "(" in raw and ")" in raw:
                lang = raw.split("(")[-1].split(")")[0].strip()
            result.append({
                "index": len(result), "engine": "sapi", "voice_id": str(i),
                "name": clean, "gender": gender, "language": lang,
                "quality": "Standard", "flag": "🪟", "installed": True,
            })
    except Exception as e:
        print(f"[VOICES] SAPI scan error: {e}")

    return {"voices": result, "count": len(result)}


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