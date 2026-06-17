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
# V1.3: Interrupt detection
import threading
import time
import numpy as np

colorama.init(autoreset=True)

MODEL_SIZE = "medium.en"
AUDIO_TEMP_PATH = "temp_audio.wav"

def _load_whisper_model(model_size: str) -> WhisperModel:
    """
    Load Whisper with best available device.
    Priority: CUDA GPU → CPU
    Falls back to CPU if CUDA fails or unavailable.
    """
    # Try GPU first
    try:
        import torch
        if torch.cuda.is_available():
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            print(Fore.GREEN + f"[EARS] Whisper loaded on GPU (CUDA) ✓")
            return model
        else:
            print(Fore.YELLOW + "[EARS] CUDA not available — using CPU")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] GPU check failed ({e}) — using CPU")

    # CPU fallback — works on ALL machines
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print(Fore.GREEN + f"[EARS] Whisper loaded on CPU ✓")
        return model
    except Exception as e:
        print(Fore.RED + f"[EARS] CPU load failed: {e}")
        raise


print(Fore.CYAN + f"[EARS] Loading Whisper Model ({MODEL_SIZE})...")
audio_model = _load_whisper_model(MODEL_SIZE)


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
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        recognizer.dynamic_energy_threshold = True
        recognizer.energy_threshold = max(recognizer.energy_threshold, 400)
        recognizer.pause_threshold = 0.8
        recognizer.non_speaking_duration = 0.4

        try:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=8)
            with open(AUDIO_TEMP_PATH, "wb") as f:
                f.write(audio.get_wav_data())

            segments_list = list(audio_model.transcribe(
                AUDIO_TEMP_PATH,
                beam_size=5,
                language="en",
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
            ))
            segments = segments_list[0]

            # Filter segments with low confidence (hallucinations have high no_speech_prob)
            confident_segments = []
            for seg in segments:
                if hasattr(seg, 'no_speech_prob') and seg.no_speech_prob > 0.6:
                    print(Fore.YELLOW + f"[EARS] Low confidence segment filtered (no_speech={seg.no_speech_prob:.2f}): '{seg.text}'")
                    continue
                confident_segments.append(seg)

            full_text = "".join([s.text for s in confident_segments]).strip()

            if not full_text:
                return None, None

            clean = full_text.lower().strip()
            for ch in [".", "!", ",", "?", "..."]:
                clean = clean.replace(ch, "")
            clean = clean.strip()

            # Very short - noise
            if len(clean) < 3:
                return None, None

            # Known Whisper hallucinations on silence/music
            ghosts = {
                "thank you", "thanks", "you", "bye", "okay", "alright",
                "thank you very much", "thanks for watching", "watching",
                "i", "so", "and", "the", "video", "subtitles", "caption",
                "goodbye", "see you", "see you next time", "like and subscribe",
                "bada ba ba ba", "ba ba ba", "da da da", "la la la",
                "hmm", "hm", "uh", "um", "ah", "oh",
                "music", "applause", "laughter",
            }
            if clean in ghosts:
                print(Fore.YELLOW + f"[EARS] Ghost filtered: '{clean}'")
                return None, None

            # Substring hallucination patterns
            forbidden = [
                "subscribe", "amara.org", "caption", "copyright",
                "all rights reserved", "bada ba", "ba ba ba ba",
                "da da da", "la la la la",
            ]
            for p in forbidden:
                if p in clean:
                    print(Fore.YELLOW + f"[EARS] Forbidden pattern filtered: '{p}' in '{clean}'")
                    return None, None

            # Reject if input is ONLY repeated single syllables (music hallucination)
            words = clean.split()
            if len(words) >= 3:
                unique = set(words)
                if len(unique) == 1 and len(list(unique)[0]) <= 3:
                    print(Fore.YELLOW + f"[EARS] Repeated syllable filtered: '{clean}'")
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
        

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """
    V1.3: Lightweight listener that runs DURING speech.
    Listens for short interrupt phrases and triggers callback.
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.8
    recognizer.non_speaking_duration = 0.5
    
    # Seven's own voice gets picked up as these — ignore them
    self_voice_ghosts = [
        "thank you", "thanks", "thanks for watching", "you",
        "bye", "okay", "subtitles", "subscribe", "video",
        "caption", "copyright", "amara"
    ]
    
    while not stop_event.is_set():
        try:
            with sr.Microphone() as source:
                try:
                    audio = recognizer.listen(source, timeout=1.5, phrase_time_limit=2)
                except sr.WaitTimeoutError:
                    continue
                
                interrupt_audio_path = "temp_interrupt.wav"
                with open(interrupt_audio_path, "wb") as f:
                    f.write(audio.get_wav_data())
                
                segments, _ = audio_model.transcribe(
                    interrupt_audio_path,
                    beam_size=1,
                    language="en"
                )
                text = "".join([s.text for s in segments]).strip().lower()
                
                try:
                    os.remove(interrupt_audio_path)
                except:
                    pass
                
                if not text or len(text) < 2:
                    continue
                
                clean = text.replace(".", "").replace("!", "").replace(",", "").strip()
                
                # Skip Seven's own voice being picked up
                if clean in self_voice_ghosts:
                    continue
                
                # Check against interrupt words
                for word in interrupt_words:
                    if word in clean:
                        print(f"[EARS] ⚡ Interrupt detected: '{clean}' (matched: '{word}')")
                        on_interrupt_callback()
                        return
                        
        except Exception:
            continue
    
    try:
        if os.path.exists("temp_interrupt.wav"):
            os.remove("temp_interrupt.wav")
    except:
        pass
        