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

def speak_text(text):
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id)
        engine.setProperty('rate', 190)
        engine.setProperty('volume', 1.0)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[SPEAKER SUBPROCESS] Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        speak_text(text)