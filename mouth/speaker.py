"""
=============================================================================
PROJECT SEVEN - mouth/speaker.py (Subprocess TTS Worker)
Version: 2.0 — Piper TTS with pyttsx3 fallback

PURPOSE:
    Runs as a SEPARATE PROCESS so it can be killed mid-sentence.
    Called by mouth/core.py via subprocess.
    
    Primary:  Piper TTS  (natural human voice, offline)
    Fallback: pyttsx3    (Windows SAPI, robotic but always available)

USAGE:
    python -m mouth.speaker "Text to speak"
=============================================================================
"""

import sys
import os
import json
import subprocess
import tempfile


# ── Config paths ──────────────────────────────────────────────────────────

def _get_config():
    """Read config.json. Returns dict or {}."""
    try:
        appdata     = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_path = os.path.join(appdata, "SEVEN", "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
            return data
    except Exception as e:
        print(f"[SPEAKER] Config read error: {e}", file=sys.stderr)
    return {}


def _get_voice_setting():
    """
    Returns (engine, voice_id, sapi_idx).
    
    Reads config.json voice section.
    Handles both old format (voice_index only) and new format (engine + voice_id).
    
    Old format: { "voice_index": 1 }
                → engine=sapi, sapi_idx=1
    New format: { "engine": "piper", "voice_id": "en_US-ryan-high", "voice_index": 0 }
                → engine=piper, voice_id=en_US-ryan-high
    """
    cfg   = _get_config()
    voice = cfg.get("voice", {})

    # If no engine field → old config format → use SAPI with voice_index
    # This handles existing installs that haven't been updated yet
    if "engine" not in voice:
        sapi_idx = voice.get("voice_index", 0)
        print(f"[SPEAKER] Old config format detected → SAPI index {sapi_idx}", file=sys.stderr)
        return "sapi", str(sapi_idx), sapi_idx

    engine   = voice.get("engine", "sapi")
    voice_id = voice.get("voice_id", "en_US-ryan-high")
    sapi_idx = voice.get("voice_index", 0)

    # Validate piper setup — if engine=piper but piper not found, fall back to SAPI
    if engine == "piper":
        piper_dir = _get_piper_dir()
        if not piper_dir:
            print(f"[SPEAKER] engine=piper in config but piper.exe not found → falling back to SAPI", file=sys.stderr)
            return "sapi", str(sapi_idx), sapi_idx
        model = _get_voice_model_path(voice_id)
        if not model:
            print(f"[SPEAKER] Piper model '{voice_id}' not found → falling back to SAPI", file=sys.stderr)
            return "sapi", str(sapi_idx), sapi_idx

    return engine, voice_id, sapi_idx


# ── Piper paths ───────────────────────────────────────────────────────────

def _get_piper_dir():
    """
    Find piper.exe location. Checks 4 locations in priority order.
    Uses absolute paths only — never depends on cwd.
    """
    candidates = []

    # 1. SEVEN_APP_PATH set by Electron (packaged app)
    app_path = os.environ.get("SEVEN_APP_PATH", "")
    if app_path:
        candidates.append(os.path.join(app_path, "mouth", "piper"))

    # 2. Relative to THIS FILE — always works regardless of cwd
    #    speaker.py is at mouth/speaker.py
    #    piper.exe  is at mouth/piper/piper.exe
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "piper"))

    # 3. Project root detection — walk up from this file
    root = os.path.dirname(here)  # SEVEN/
    candidates.append(os.path.join(root, "mouth", "piper"))

    # 4. CWD fallback
    candidates.append(os.path.join(os.getcwd(), "mouth", "piper"))

    for c in candidates:
        exe = os.path.join(c, "piper.exe")
        if os.path.exists(exe):
            return c   # Remove the print — it runs 3x per speak call

    print(f"[SPEAKER] Piper NOT found. Searched:", file=sys.stderr)
    for c in candidates:
        print(f"[SPEAKER]   {c}", file=sys.stderr)
    return None


def _get_voice_model_path(voice_id):
    """Return full path to .onnx model file."""
    piper_dir = _get_piper_dir()
    if not piper_dir:
        return None
    voices_dir = os.path.join(piper_dir, "voices")
    model_path = os.path.join(voices_dir, f"{voice_id}.onnx")
    if os.path.exists(model_path):
        return model_path
    return None


# ── Piper TTS ─────────────────────────────────────────────────────────────

def _speak_piper(text, voice_id, speed=165):
    """
    Speak text using Piper TTS.
    Piper reads from stdin, outputs WAV, we play via Windo  ws built-in player.
    Returns True on success, False on failure.
    """
    piper_dir  = _get_piper_dir()
    model_path = _get_voice_model_path(voice_id)

    if not piper_dir or not model_path:
        print(f"[SPEAKER] Piper not found. dir={piper_dir} model={model_path}", file=sys.stderr)
        return False

    piper_exe = os.path.join(piper_dir, "piper.exe")

    try:
        # Write to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        # Run piper: stdin → WAV file
                # Convert speed to piper length_scale
        # speed 130=slow(1.3), 165=normal(1.0), 190=fast(0.8), 220=max(0.6)
        length_scale = round(1.0 - (speed - 165) / 275, 2)
        length_scale = max(0.5, min(2.0, length_scale))

        # Use Popen with DETACHED_PROCESS | CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        # This combination fully suppresses conhost.exe for console-subsystem binaries
        _si = None
        _cflags = 0
        if sys.platform == 'win32':
            _si = subprocess.STARTUPINFO()
            _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _si.wShowWindow = 0
            # DETACHED_PROCESS (0x8) + CREATE_NO_WINDOW (0x8000000) + CREATE_NEW_PROCESS_GROUP (0x200)
            _cflags = 0x08000000 | 0x00000008 | 0x00000200

        proc = subprocess.Popen(
            [
                piper_exe,
                "--model",        model_path,
                "--output_file",  tmp_path,
                "--length_scale", str(length_scale),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=piper_dir,
            startupinfo=_si,
            creationflags=_cflags,
            close_fds=True,
        )
        try:
            stdout_data, stderr_data = proc.communicate(
                input=text.encode("utf-8"), timeout=30
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_data, stderr_data = proc.communicate()

        class _R:
            pass
        result = _R()
        result.returncode = proc.returncode
        result.stdout = stdout_data
        result.stderr = stderr_data

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            print(f"[SPEAKER] Piper error: {err}", file=sys.stderr)
            os.unlink(tmp_path)
            return False

        # Play WAV using Windows built-in (no extra deps)
        _play_wav(tmp_path)

        # Cleanup
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return True

    except subprocess.TimeoutExpired:
        print("[SPEAKER] Piper timeout", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[SPEAKER] Piper exception: {e}", file=sys.stderr)
        return False


def _play_wav(wav_path):
    """
    Play a WAV file synchronously.
    winsound = instant start, no subprocess overhead.
    PowerShell = fallback only.
    """
    try:
        # Method 1: winsound — pure Windows API, instant, no subprocess cost
        import winsound
        winsound.PlaySound(wav_path, winsound.SND_FILENAME)
        return
    except Exception as e:
        print(f"[SPEAKER] winsound error, trying PowerShell: {e}", file=sys.stderr)

    try:
        # Method 2: PowerShell SoundPlayer (fallback)
        ps_script = (
            f"$player = New-Object System.Media.SoundPlayer('{wav_path}'); "
            f"$player.PlaySync();"
        )
        _si2 = None
        _cflags2 = 0
        if sys.platform == 'win32':
            _si2 = subprocess.STARTUPINFO()
            _si2.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            _si2.wShowWindow = 0
            _cflags2 = 0x08000000
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=60,
            startupinfo=_si2,
            creationflags=_cflags2,
        )
    except Exception as e:
        print(f"[SPEAKER] PowerShell fallback error: {e}", file=sys.stderr)


# ── pyttsx3 fallback ──────────────────────────────────────────────────────

def _speak_sapi(text, voice_index=0, speed=165):
    """
    Speak text using Windows SAPI (pyttsx3).
    Used when Piper is not installed.
    """
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')

        if not voices:
            print("[SPEAKER] No SAPI voices found", file=sys.stderr)
            return

        if voice_index >= len(voices):
            voice_index = 0

        engine.setProperty('voice',  voices[voice_index].id)
        engine.setProperty('rate',   int(speed))
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        print(f"[SPEAKER] SAPI error: {e}", file=sys.stderr)


# ── Main entry ────────────────────────────────────────────────────────────

# Module-level cache — config read once per process, not once per word
_VOICE_CACHE = None

def _get_voice_cached():
    """
    Read voice config once and cache it.
    speaker.py runs as a subprocess — process lives for one speak call.
    Cache is valid for the entire process lifetime.
    """
    global _VOICE_CACHE
    if _VOICE_CACHE is None:
        cfg          = _get_config()
        engine, voice_id, sapi_idx = _get_voice_setting()
        speed        = cfg.get("voice", {}).get("speed", 165)
        _VOICE_CACHE = (engine, voice_id, sapi_idx, speed)
    return _VOICE_CACHE


def speak_text(text):
    """
    Speak text. Uses Piper if available, falls back to pyttsx3.
    """
    engine, voice_id, sapi_idx, speed = _get_voice_cached()

    if engine == "piper":
        success = _speak_piper(text, voice_id, speed=speed)
        if not success:
            print("[SPEAKER] Falling back to SAPI", file=sys.stderr)
            _speak_sapi(text, sapi_idx, speed=speed)
    else:
        _speak_sapi(text, sapi_idx, speed=speed)


if __name__ == "__main__":
    # Only run when executed directly, not when imported by -c command
    text = os.environ.get("SEVEN_SPEAK_TEXT", "")
    if not text and len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    if text:
        speak_text(text)