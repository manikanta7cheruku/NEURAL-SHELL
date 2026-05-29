"""
=============================================================================
PROJECT SEVEN - mouth/speaker.py (Subprocess TTS Worker)
Version: 1.3

PURPOSE:
    Runs as a SEPARATE PROCESS so it can be killed mid-sentence.
    Called by mouth/core.py via subprocess.
    
USAGE:
    python -m mouth.speaker "Text to speak"
=============================================================================
"""

import pyttsx3
import sys
import os
import json


def _get_voice_index():
    """
    Read user's selected voice index from config.json.
    Falls back to 0 if not set.
    """
    try:
        appdata     = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_path = os.path.join(appdata, "SEVEN", "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
            return cfg.get("voice", {}).get("voice_index", 0)
    except Exception:
        pass
    return 0


def speak_text(text):
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')

        if not voices:
            print("[SPEAKER] No voices found", file=sys.stderr)
            return

        # Read user-selected voice index
        voice_index = _get_voice_index()

        # Safety clamp
        if voice_index >= len(voices):
            voice_index = 0

        engine.setProperty('voice', voices[voice_index].id)
        engine.setProperty('rate', 175)   # slightly slower = more natural
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        print(f"[SPEAKER SUBPROCESS] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        speak_text(text)