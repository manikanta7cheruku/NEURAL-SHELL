"""
=============================================================================
PROJECT SEVEN - ears/core.py (The Listener)
Version: 1.2 (Voice Identity Support)

CHANGES FROM V1.1.2:
    1. listen() now returns (text, audio_path) tuple instead of just text
    2. Audio file kept for voice identification before cleanup
    3. All existing logic unchanged (filters, corrections, whisper)
=============================================================================
"""

import speech_recognition as sr
from faster_whisper import WhisperModel
import os
import colorama
from colorama import Fore

colorama.init(autoreset=True)

MODEL_SIZE = "medium.en"
AUDIO_TEMP_PATH = "temp_audio.wav"

print(Fore.CYAN + f"[EARS] Loading Whisper Model ({MODEL_SIZE})...")
audio_model = WhisperModel(MODEL_SIZE, device="cuda", compute_type="float16")


def listen():
    """
    Listen for speech and transcribe it.
    
    Returns:
        tuple: (transcribed_text, audio_file_path) or (None, None)
        
    V1.2 Change: Returns tuple instead of just string.
    The audio_path is needed by voice_id.py to identify the speaker.
    main.py handles cleanup of the audio file after identification.
    """
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.6

        try:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=8)
            with open(AUDIO_TEMP_PATH, "wb") as f:
                f.write(audio.get_wav_data())

            segments, info = audio_model.transcribe(AUDIO_TEMP_PATH, beam_size=5)
            full_text = "".join([s.text for s in segments]).strip()

            # --- AGGRESSIVE SILENCE FILTER ---
            clean = full_text.lower().strip().replace(".", "").replace("!", "").replace(",", "")

            # 1. Ignore very short noise
            if len(clean) < 2:
                return None, None

            # 2. Ignore specific silence hallucinations (Exact Match)
            ghosts = [
                "thank you", "thanks", "you", "bye", "okay", "alright",
                "thank you very much", "thanks for watching", "watching",
                "i", "so", "and", "the", "video", "subtitles", "caption"
            ]

            if clean in ghosts:
                return None, None

            # 3. Ignore YouTube Outros (Substring Match)
            forbidden = ["subscribe", "amara.org", "caption", "copyright", "all rights reserved"]
            for p in forbidden:
                if p in clean:
                    return None, None

            # --- AUTOCORRECT ---
            corrections = {
                "semen": "Seven", "savin": "Seven", "sibin": "Seven",
                "simon": "Seven", "siman": "Seven", "heaven": "Seven",
                "siwen": "Seven", "so when": "Seven", "servant": "Seven",
                "sir'en": "Seven", "siren": "Seven", "sevan": "Seven",
                "i7": "Hi Seven", "i 7": "Hi Seven",
                "fight explorer": "File Explorer",
                "five explorer": "File Explorer",
                "aye": "Hi", "alo": "Hello",
                  "and roll my voice": "enroll my voice",
                "and roll": "enroll",
                "in role": "enroll",
                "in roll": "enroll",
                "unroll": "enroll",
                "un roll": "enroll",
            }

            for wrong, right in corrections.items():
                if wrong in clean:
                    full_text = full_text.lower().replace(wrong, right)
                    break

            return full_text.capitalize(), AUDIO_TEMP_PATH

        except:
            return None, None