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
                return json.load(f)
    except Exception:
        pass
    return {}


def _get_voice_setting():
    """
    Returns (engine, voice_id) where:
      engine   = "piper" or "sapi"
      voice_id = piper model filename (e.g. "en_US-ryan-high")
                 OR sapi voice index (int)
    """
    cfg   = _get_config()
    voice = cfg.get("voice", {})
    
    engine   = voice.get("engine", "piper")        # default to piper
    voice_id = voice.get("voice_id", "en_US-ryan-high")  # default voice
    sapi_idx = voice.get("voice_index", 0)
    
    return engine, voice_id, sapi_idx


# ── Piper paths ───────────────────────────────────────────────────────────

def _get_piper_dir():
    """
    Find piper.exe location.
    Works both in dev (relative path) and packaged Electron app.
    """
    # 1. Env var set by Electron (packaged)
    app_path = os.environ.get("SEVEN_APP_PATH", "")
    if app_path:
        p = os.path.join(app_path, "mouth", "piper", "piper.exe")
        if os.path.exists(p):
            return os.path.join(app_path, "mouth", "piper")

    # 2. Relative to this file (dev mode)
    here     = os.path.dirname(os.path.abspath(__file__))
    piper_dir = os.path.join(here, "piper")
    exe      = os.path.join(piper_dir, "piper.exe")
    if os.path.exists(exe):
        return piper_dir

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
    Play a WAV file synchronously using Windows built-in tools.
    No external dependencies needed.
    """
    try:
        # Method 1: PowerShell SoundPlayer (most reliable, synchronous)
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
        print(f"[SPEAKER] WAV playback error: {e}", file=sys.stderr)
        try:
            # Method 2: winsound (stdlib fallback)
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
        except Exception as e2:
            print(f"[SPEAKER] winsound fallback error: {e2}", file=sys.stderr)


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
        engine.setProperty('rate',   165)
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

    if engine == "piper":
        success = _speak_piper(text, voice_id)
        if not success:
            # Fallback to SAPI if Piper fails
            print("[SPEAKER] Falling back to SAPI", file=sys.stderr)
            _speak_sapi(text, sapi_idx)
    else:
        _speak_sapi(text, sapi_idx)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        speak_text(text)