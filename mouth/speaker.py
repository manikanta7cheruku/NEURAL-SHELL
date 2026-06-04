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
        print(f"[SPEAKER] Reading config: {config_path}", file=sys.stderr)
        print(f"[SPEAKER] Config exists: {os.path.exists(config_path)}", file=sys.stderr)
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
            print(f"[SPEAKER] Voice config: {data.get('voice', 'NOT FOUND')}", file=sys.stderr)
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
            print(f"[SPEAKER] Piper found at: {c}", file=sys.stderr)
            return c

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

def _speak_piper(text, voice_id):
    """
    Speak text using Piper TTS.
    Piper reads from stdin, outputs WAV, we play via Windows built-in player.
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
        result = subprocess.run(
            [
                piper_exe,
                "--model",       model_path,
                "--output_file", tmp_path,
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
            cwd=piper_dir,   # important: espeak-ng-data must be next to piper.exe
        )

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
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=60,
        )
    except Exception as e:
        print(f"[SPEAKER] PowerShell fallback error: {e}", file=sys.stderr)


# ── pyttsx3 fallback ──────────────────────────────────────────────────────

def _speak_sapi(text, voice_index=0):
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
        cfg   = _get_config()
        speed = cfg.get("voice", {}).get("speed", 165)
        engine.setProperty('rate', speed)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        print(f"[SPEAKER] SAPI error: {e}", file=sys.stderr)


# ── Main entry ────────────────────────────────────────────────────────────

def speak_text(text):
    """
    Speak text. Uses Piper if available, falls back to pyttsx3.
    """
    engine, voice_id, sapi_idx = _get_voice_setting()
    print(f"[SPEAKER] engine={engine} voice_id={voice_id} sapi_idx={sapi_idx}", file=sys.stderr)

    if engine == "piper":
        piper_dir  = _get_piper_dir()
        model_path = _get_voice_model_path(voice_id)
        print(f"[SPEAKER] piper_dir={piper_dir}", file=sys.stderr)
        print(f"[SPEAKER] model_path={model_path}", file=sys.stderr)
        success = _speak_piper(text, voice_id)
        if not success:
            print("[SPEAKER] Piper failed — falling back to SAPI", file=sys.stderr)
            _speak_sapi(text, sapi_idx)
    else:
        print(f"[SPEAKER] Using SAPI index {sapi_idx}", file=sys.stderr)
        _speak_sapi(text, sapi_idx)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        speak_text(text)