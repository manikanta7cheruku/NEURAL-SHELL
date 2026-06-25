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

# RMS threshold — calibrated to distinguish direct speech from background noise
# 800 works for most laptop mics at normal speaking distance (30-50cm)
# If you are far from laptop, lower this to 400
# If background noise is loud, raise this to 1200
RMS_THRESHOLD = 300  # Lower — catches quiet voice. Crest factor discriminates noise.


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
        # Short calibration — 0.2s is enough for ambient noise baseline
        recognizer.adjust_for_ambient_noise(source, duration=0.2)
        recognizer.dynamic_energy_threshold = True

        # Keep energy_threshold low — let audio through, crest factor does discrimination
        # 300 catches silence. Crest factor 30-44 catches your voice vs speaker bleed.
        # Calibrated: ambient noise threshold on this machine = ~119
        # Voice RMS = 3049, Crest = 10.69   
        # Keep threshold low — crest factor handles speaker bleed discrimination
        recognizer.energy_threshold = max(recognizer.energy_threshold, 200)
        recognizer.pause_threshold = 0.7       # Back to 0.7 — 0.5 was cutting off words
        recognizer.non_speaking_duration = 0.3
        recognizer.phrase_threshold = 0.1

        try:
            audio = recognizer.listen(source, timeout=None, phrase_time_limit=7)
            wav_data = audio.get_wav_data()

            # --- RMS ENERGY CHECK ---
            # Check actual audio amplitude before sending to Whisper.
            # Background TV/YouTube has low RMS even if recognizer passes it.
            # Your voice close to mic has 3-5x higher RMS than background audio.
            # This is the single most effective hallucination filter.
            try:
                audio_np = np.frombuffer(wav_data, dtype=np.int16).astype(np.float32)
                rms  = np.sqrt(np.mean(audio_np ** 2))
                peak = np.max(np.abs(audio_np))

                if rms < RMS_THRESHOLD:
                    print(Fore.YELLOW + f"[EARS] RMS too low ({rms:.0f} < {RMS_THRESHOLD}) — background noise, skipping")
                    return None, None

                # Crest factor = peak / RMS
                # Direct voice: crest factor typically 4-15 (sharp consonant peaks)
                # Speaker bleed: crest factor typically 1.5-3 (diffuse, averaged out)
                # If crest factor is very low, audio is diffuse = speaker bleed
                crest = peak / rms if rms > 0 else 0
                if crest < 2.5:
                    print(Fore.YELLOW + f"[EARS] Low crest factor ({crest:.2f}) — diffuse audio, likely speaker bleed, skipping")
                    return None, None

                print(Fore.CYAN + f"[EARS] RMS: {rms:.0f} | Crest: {crest:.2f} — proceeding to Whisper")
            except Exception as _rms_err:
                print(Fore.YELLOW + f"[EARS] Audio check skipped: {_rms_err}")

            with open(AUDIO_TEMP_PATH, "wb") as f:
                f.write(wav_data)

            segments_list = list(audio_model.transcribe(
                AUDIO_TEMP_PATH,
                beam_size=3,
                language="en",
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                log_prob_threshold=-0.7,
                vad_filter=True,
                vad_parameters={
                    "threshold": 0.4,
                    "min_speech_duration_ms": 150,
                    "min_silence_duration_ms": 250,
                },
                # Tell Whisper what kind of speech to expect
                # This dramatically reduces hallucination on short commands
                initial_prompt=(
                    "Voice assistant commands. Short phrases. "
                    "Examples: open chrome, volume up, set reminder, "
                    "what is the weather, close spotify."
                ),
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

            # Known Whisper hallucinations on silence/music/background TV
            # These are phrases Whisper invents when audio is not direct speech
            ghosts = {
                # Filler words — single word hallucinations
                "thank you", "thanks", "you", "bye", "okay", "alright",
                "thank you very much", "thanks for watching", "watching",
                "i", "so", "and", "the", "video", "subtitles", "caption",
                "goodbye", "see you", "see you next time", "like and subscribe",
                "bada ba ba ba", "ba ba ba", "da da da", "la la la",
                "hmm", "hm", "uh", "um", "ah", "oh",
                "music", "applause", "laughter",
                # YouTube/creator phrases Whisper hallucinates from background video
                "see you in the next video",
                "see you guys in the next video",
                "i'll see you guys in the next video",
                "that's all for today",
                "thats all for today",
                "see you in the next one",
                "thanks for watching guys",
                "don't forget to subscribe",
                "hit the like button",
                "have a great day",
                "have a good day",
                "take care everyone",
                "peace out",
                "later guys",
                "do you want to see more videos like this",
                "do you want to see more videos",
                "we'll see you in the next video",
                "well see you in the next video",
                "ill see you in the next video",
                "i will see you in the next video",
                "what's going on", "whats going on",
                "what's up", "whats up",
                "what is going on",
                "hello hello",
                "the guy is up",
                "a waste of time",
                "a bold choice",
                "a bold move",
                "a familiar phrase",
                "6 and 5",
            }
            if clean in ghosts:
                print(Fore.YELLOW + f"[EARS] Ghost filtered: '{clean}'")
                return None, None

            # Substring patterns — if ANY of these appear anywhere in the text,
            # it is background audio bleed, not user speech
            forbidden = [
                "subscribe", "amara.org", "caption", "copyright",
                "all rights reserved", "bada ba", "ba ba ba ba",
                "da da da", "la la la la",
                "next video", "see you guys", "see you in the",
                "thanks for watching", "thank you for watching",
                "dont forget to", "don't forget to",
                "hit the like", "like and subscribe",
                "have a great day", "have a good day",
                # Speaker bleed patterns from background video/audio
                "thank you very much",
                "thank you so much",
                "i wish i could",
                "i'll begin",
                "i will begin",
                "that was quick",
                "almost at a percent",
                "platform is almost",
                "you're watching",
                "youre watching",
                "welcome back",
                "welcome to",
                "in today's video",
                "in todays video",
                "in this video",
                "let's get started",
                "lets get started",
                "without further ado",
                "make sure to",
                "guys and gals",
                "smash that like",
                "drop a comment",
                "down below",
                "check out",
                "my name is",          # common YouTube intro — will not fire for Seven
                "i'm your host",
                "im your host",
                "stay tuned",
                "coming up next",
                "right after this",
                "we'll be right back",
                "well be right back",
            ]
            for p in forbidden:
                if p in clean:
                    print(Fore.YELLOW + f"[EARS] Speaker bleed filtered: '{p}' in '{clean}'")
                    return None, None

            # Reject if input is ONLY repeated single syllables (music hallucination)
            words = clean.split()
            if len(words) >= 3:
                unique = set(words)
                if len(unique) == 1 and len(list(unique)[0]) <= 3:
                    print(Fore.YELLOW + f"[EARS] Repeated syllable filtered: '{clean}'")
                    return None, None

            # Reject suspiciously high ratio of filler words
            # "Well she goes after it" = 5 words, only "she" and "it" are content
            # This catches background conversation fragments
            _filler = {"the", "a", "an", "is", "it", "to", "of", "and",
                       "or", "but", "in", "on", "at", "for", "well",
                       "so", "that", "this", "what", "i", "you", "he",
                       "she", "they", "we", "my", "your", "his", "her",
                       "up", "after", "goes", "with", "be", "are", "was"}
            if len(words) >= 4:
                content_words = [w for w in words if w not in _filler]
                filler_ratio = 1 - (len(content_words) / len(words))
                if filler_ratio > 0.75:
                    print(Fore.YELLOW + f"[EARS] High filler ratio ({filler_ratio:.2f}) filtered: '{clean}'")
                    return None, None

            # Reject run-on sentences — user commands are concise
            # Background audio produces long mixed transcriptions
            # Hard limit: more than 18 words = almost certainly background audio
            if len(words) > 18:
                print(Fore.YELLOW + f"[EARS] Too long ({len(words)} words) — background audio, filtered: '{clean[:60]}...'")
                return None, None

            # Reject trailing-off sentences — background audio fades out
            # "thank you i wish i could just" ends with "just" — no object
            # Real commands always complete: "open chrome", "set volume 50"
            _trailing_off = ["just", "but", "and", "so", "because",
                             "though", "although", "however", "anyway",
                             "i mean", "you know", "like i"]
            if words and words[-1] in _trailing_off:
                print(Fore.YELLOW + f"[EARS] Trailing-off sentence filtered: '{clean}'")
                return None, None

            # Reject if sentence has multiple "thank you" or "thanks" embedded
            _ty_count = clean.count("thank you") + clean.count("thanks")
            if _ty_count >= 1 and len(words) > 5:
                print(Fore.YELLOW + f"[EARS] Thank-you pattern in long sentence filtered: '{clean}'")
                return None, None
            
            # --- COMMAND SANITY CHECK ---
            # Voice assistant commands have a specific structure.
            # Narration/presentation sentences do not.
            # Reject if it reads like dictated text, not a command.

            # Pattern 1: "of the X of the Y" — narration pattern, not a command
            _of_the_count = clean.count("of the")
            if _of_the_count >= 2:
                print(Fore.YELLOW + f"[EARS] Narration pattern filtered: '{clean}'")
                return None, None

            # Pattern 2: Passive voice constructions — "was a presentation of"
            _passive_markers = [
                "was a ", "were a ", "is a presentation",
                "was the ", "this was", "that was",
                "reading of", "parts response", "positive parts",
            ]
            if any(p in clean for p in _passive_markers) and len(words) > 6:
                print(Fore.YELLOW + f"[EARS] Passive/narration pattern filtered: '{clean}'")
                return None, None

            # Pattern 3: Commands start with action verbs or question words
            # If first word is not a known command/question starter AND sentence
            # is longer than 8 words — likely hallucination
            _valid_starters = {
                "open", "close", "start", "stop", "play", "pause", "skip",
                "set", "get", "show", "find", "tell", "what", "how", "why",
                "when", "where", "who", "which", "can", "could", "will",
                "volume", "mute", "unmute", "brightness", "remind", "schedule",
                "add", "delete", "remove", "create", "make", "turn", "switch",
                "enable", "disable", "check", "search", "list", "hey", "hi",
                "hello", "ok", "okay", "yes", "no", "cancel", "clear",
                "increase", "decrease", "raise", "lower", "maximize", "minimize",
                "snap", "move", "resize", "pin", "unpin", "restart", "shutdown",
                "lock", "sleep", "wake", "timer", "alarm", "note", "write",
                "read", "send", "call", "message", "email", "my", "do",
                "is", "are", "was", "i", "the", "a",
            }
            if words and words[0] not in _valid_starters and len(words) > 8:
                print(Fore.YELLOW + f"[EARS] Unknown starter + long sentence filtered: '{clean[:60]}'")
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
        