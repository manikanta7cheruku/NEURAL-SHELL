"""
=============================================================================
PROJECT SEVEN - ears/core.py (The Listener)
Version: 1.3 — Adaptive Noise Floor

CHANGES FROM V1.2:
    1. Adaptive noise floor — threshold adjusts as environment changes
    2. No hardcoded RMS values — calibrates from real measurements
    3. Rolling window noise tracking — handles fan on/off, room changes
    4. Duplicate print line removed
    5. Old _calibrate_noise_floor replaced with adaptive system
=============================================================================
"""

import speech_recognition as sr
from faster_whisper import WhisperModel
import os
import threading
import time
import numpy as np
import colorama
from colorama import Fore

colorama.init(autoreset=True)

MODEL_SIZE      = "medium.en"
AUDIO_TEMP_PATH = "temp_audio.wav"

# External interrupt flag — set True to make listen() return immediately
# Used by enrollment to unblock the listening loop
_force_return = False

def set_force_return(val: bool):
    """Call this to make the current listen() return immediately."""
    global _force_return
    _force_return = val


# =============================================================================
# WHISPER MODEL LOADER
# =============================================================================

def _load_whisper_model(model_size: str) -> WhisperModel:
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

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print(Fore.GREEN + f"[EARS] Whisper loaded on CPU ✓")
        return model
    except Exception as e:
        print(Fore.RED + f"[EARS] CPU load failed: {e}")
        raise


print(Fore.CYAN + f"[EARS] Loading Whisper Model ({MODEL_SIZE})...")
audio_model = _load_whisper_model(MODEL_SIZE)


# =============================================================================
# ADAPTIVE NOISE FLOOR
# No hardcoded thresholds. Calibrates from real measurements at startup.
# Updates continuously as environment changes — fan on/off, AC, room change.
#
# HOW IT WORKS:
#   1. At startup: record 1 second of silence → measure RMS → set baseline
#   2. Every rejected audio clip → feed its RMS into rolling average
#   3. Threshold = rolling_average × MULTIPLIER
#   4. Fan turns off → next 20 rejected clips are quieter → average drops
#      → threshold drops → quiet voice now passes
# =============================================================================

_noise_floor   = 0.0        # current estimated ambient noise RMS
_noise_samples = []         # rolling window of rejected clip RMS values
_NOISE_WINDOW    = 20
_MULTIPLIER      = 2.2
_MIN_CREST       = 3.5
_MIN_DURATION    = 0.5
_floor_lock      = threading.Lock()
_initial_floor   = 0.0   # set once at calibration, never changes
_NOISE_FLOOR_CAP = 500   # hard ceiling — prevents runaway from leakage


def _update_noise_floor(rms: float):
    """
    Update noise floor with a rejected clip.
    Rules:
    - Floor can DECREASE if environment gets quieter (fan off)
    - Floor can INCREASE only up to _NOISE_FLOOR_CAP
    - Floor can NEVER exceed the cap (prevents headphone/music runaway)
    - Small fluctuations ignored (only log >20% change)
    """
    global _noise_floor, _noise_samples
    with _floor_lock:
        _noise_samples.append(rms)
        if len(_noise_samples) > _NOISE_WINDOW:
            _noise_samples.pop(0)
        prev         = _noise_floor
        new_floor    = sum(_noise_samples) / len(_noise_samples)
        _noise_floor = min(new_floor, _NOISE_FLOOR_CAP)
        if prev > 0 and abs(_noise_floor - prev) / prev > 0.20:
            print(Fore.CYAN + f"[EARS] Threshold: {prev * _MULTIPLIER:.0f} → {_noise_floor * _MULTIPLIER:.0f}")


def _get_threshold() -> float:
    """
    Returns the current voice detection threshold.
    If no data yet — returns 300 (permissive default for quiet rooms).
    """
    with _floor_lock:
        if _noise_floor == 0:
            return 300
        return _noise_floor * _MULTIPLIER


def _do_initial_calibration():
    global _noise_samples, _noise_floor, _initial_floor
    try:
        _r = sr.Recognizer()
        with sr.Microphone() as _src:
            print(Fore.CYAN + "[EARS] Calibrating ambient noise — 1 second...")
            _audio = _r.record(_src, duration=1)
            _wav   = _audio.get_wav_data()
            _arr   = np.frombuffer(_wav, dtype=np.int16).astype(np.float32)
            _rms   = float(np.sqrt(np.mean(_arr ** 2)))
            with _floor_lock:
                _noise_samples = [_rms] * 5
                _noise_floor   = _rms
                _initial_floor = _rms   # locked forever
            print(Fore.GREEN + f"[EARS] Noise floor: {_rms:.0f} | Threshold: {_rms * _MULTIPLIER:.0f}")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Calibration failed: {e} — using quiet room default")
        with _floor_lock:
            _noise_samples = [136.0] * 5
            _noise_floor   = 136.0
            _initial_floor = 136.0


_do_initial_calibration()


# =============================================================================
# MAIN LISTEN FUNCTION
# =============================================================================

def listen():
    """
    Listen for speech and transcribe it.

    Returns:
        tuple: (transcribed_text, audio_file_path) or (None, None)
    """
    recognizer = sr.Recognizer()

    try:
        mic = sr.Microphone()
    except Exception as _mic_err:
        print(Fore.YELLOW + f"[EARS] Microphone init failed: {_mic_err}")
        import time as _t
        _t.sleep(2)
        return None, None

    try:
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.1)
            recognizer.dynamic_energy_threshold = False
            recognizer.energy_threshold         = _get_threshold()
            recognizer.pause_threshold          = 0.7
            recognizer.non_speaking_duration    = 0.3
            recognizer.phrase_threshold         = 0.1

            if _force_return:
                # Enrollment waiting — unblock immediately
                recognizer.energy_threshold = 50
                _listen_timeout = 1.5
                _phrase_limit   = 1
            else:
                _listen_timeout = None
                _phrase_limit   = 7

            try:
                audio    = recognizer.listen(
                    source,
                    timeout=_listen_timeout,
                    phrase_time_limit=_phrase_limit
                )
                wav_data = audio.get_wav_data()

                # ── Signal Quality Checks ──────────────────────────────────
                try:
                    audio_np  = np.frombuffer(wav_data, dtype=np.int16).astype(np.float32)
                    rms       = float(np.sqrt(np.mean(audio_np ** 2)))
                    peak      = float(np.max(np.abs(audio_np)))
                    dur       = len(audio_np) / 16000.0
                    threshold = _get_threshold()

                    if rms < threshold:
                        _update_noise_floor(rms)
                        print(Fore.YELLOW + f"[EARS] RMS {rms:.0f} < {threshold:.0f} (floor:{_noise_floor:.0f}) — noise")
                        return None, None

                    if dur < _MIN_DURATION:
                        _update_noise_floor(rms)
                        print(Fore.YELLOW + f"[EARS] Too short ({dur:.2f}s) — noise burst")
                        return None, None

                    crest = peak / rms if rms > 0 else 0
                    if crest < _MIN_CREST:
                        _update_noise_floor(rms)
                        print(Fore.YELLOW + f"[EARS] Crest {crest:.2f} < {_MIN_CREST} — diffuse noise")
                        return None, None

                    print(Fore.CYAN + f"[EARS] RMS:{rms:.0f} Crest:{crest:.2f} Dur:{dur:.2f}s Floor:{_noise_floor:.0f} Thresh:{threshold:.0f}")

                except Exception as _e:
                    print(Fore.YELLOW + f"[EARS] Signal check failed: {_e}")

                # ── Write WAV for Whisper ──────────────────────────────────
                with open(AUDIO_TEMP_PATH, "wb") as f:
                    f.write(wav_data)

                # ── Whisper Transcription ──────────────────────────────────
                segments_list = list(audio_model.transcribe(
                    AUDIO_TEMP_PATH,
                    beam_size=3,
                    language="en",
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                    log_prob_threshold=-0.7,
                    vad_filter=True,
                    vad_parameters={
                        "threshold":              0.4,
                        "min_speech_duration_ms": 150,
                        "min_silence_duration_ms": 250,
                    },
                    initial_prompt=(
                        "Voice assistant commands. Short phrases. "
                        "Examples: open chrome, volume up, set reminder, "
                        "what is the weather, close spotify."
                    ),
                ))
                segments = segments_list[0]

                # ── Confidence Filter ──────────────────────────────────────
                confident_segments = []
                for seg in segments:
                    if hasattr(seg, 'no_speech_prob') and seg.no_speech_prob > 0.6:
                        print(Fore.YELLOW + f"[EARS] Low confidence filtered (no_speech={seg.no_speech_prob:.2f}): '{seg.text}'")
                        continue
                    confident_segments.append(seg)

                full_text = "".join([s.text for s in confident_segments]).strip()
                if not full_text:
                    return None, None

                clean = full_text.lower().strip()
                for ch in [".", "!", ",", "?", "..."]:
                    clean = clean.replace(ch, "")
                clean = clean.strip()

                if len(clean) < 3:
                    return None, None

                # ── Ghost Filter ───────────────────────────────────────────
                ghosts = {
                    "thank you", "thanks", "you", "bye", "alright",
                    "thank you very much", "thanks for watching", "watching",
                    "i", "so", "and", "the", "video", "subtitles", "caption",
                    "goodbye", "see you", "see you next time", "like and subscribe",
                    "bada ba ba ba", "ba ba ba", "da da da", "la la la",
                    "hmm", "hm", "uh", "um", "ah", "oh",
                    "music", "applause", "laughter",
                    "see you in the next video", "see you guys in the next video",
                    "i'll see you guys in the next video",
                    "that's all for today", "thats all for today",
                    "see you in the next one", "thanks for watching guys",
                    "don't forget to subscribe", "hit the like button",
                    "have a great day", "have a good day", "take care everyone",
                    "peace out", "later guys",
                    "do you want to see more videos like this",
                    "do you want to see more videos",
                    "we'll see you in the next video", "well see you in the next video",
                    "ill see you in the next video", "i will see you in the next video",
                    "hello hello", "the guy is up", "a waste of time",
                    "a bold choice", "a bold move", "a familiar phrase", "6 and 5",
                }
                if clean in ghosts:
                    print(Fore.YELLOW + f"[EARS] Ghost filtered: '{clean}'")
                    return None, None

                # ── Forbidden Pattern Filter ───────────────────────────────
                forbidden = [
                    "subscribe", "amara.org", "caption", "copyright",
                    "mooji.org", "visit us at", "www.", ".org", ".com/",
                    "for more information", "all rights reserved",
                    "bada ba", "ba ba ba ba", "da da da", "la la la la",
                    "next video", "see you guys", "see you in the",
                    "thanks for watching", "thank you for watching",
                    "dont forget to", "don't forget to",
                    "hit the like", "like and subscribe",
                    "have a great day", "have a good day",
                    "thank you very much", "thank you so much",
                    "i wish i could", "i'll begin", "i will begin",
                    "that was quick", "almost at a percent", "platform is almost",
                    "you're watching", "youre watching",
                    "welcome back", "welcome to",
                    "in today's video", "in todays video", "in this video",
                    "let's get started", "lets get started", "without further ado",
                    "make sure to", "guys and gals", "smash that like",
                    "drop a comment", "down below", "check out",
                    "my name is", "i'm your host", "im your host",
                    "stay tuned", "coming up next", "right after this",
                    "we'll be right back", "well be right back",
                ]
                for p in forbidden:
                    if p in clean:
                        print(Fore.YELLOW + f"[EARS] Forbidden filtered: '{p}'")
                        return None, None

                words = clean.split()

                # Repeated syllable
                if len(words) >= 3:
                    unique = set(words)
                    if len(unique) == 1 and len(list(unique)[0]) <= 3:
                        print(Fore.YELLOW + f"[EARS] Repeated syllable filtered: '{clean}'")
                        return None, None

                # Filler ratio
                _filler = {"the","a","an","is","it","to","of","and","or","but",
                           "in","on","at","for","well","so","that","this","what",
                           "i","you","he","she","they","we","my","your","his","her",
                           "up","after","goes","with","be","are","was"}
                if len(words) >= 4:
                    content_words = [w for w in words if w not in _filler]
                    filler_ratio  = 1 - (len(content_words) / len(words))
                    if filler_ratio > 0.75:
                        print(Fore.YELLOW + f"[EARS] High filler ratio ({filler_ratio:.2f}) filtered")
                        return None, None

                # Word count
                if len(words) > 18:
                    print(Fore.YELLOW + f"[EARS] Too long ({len(words)} words) filtered")
                    return None, None

                # Trailing off
                _trailing_off = ["just","but","and","so","because","though",
                                 "although","however","anyway","i mean","you know","like i"]
                if words and words[-1] in _trailing_off:
                    print(Fore.YELLOW + f"[EARS] Trailing-off filtered: '{clean}'")
                    return None, None

                # Thank-you pattern
                _ty_count = clean.count("thank you") + clean.count("thanks")
                if _ty_count >= 1 and len(words) > 5:
                    print(Fore.YELLOW + f"[EARS] Thank-you pattern filtered")
                    return None, None

                # Narration pattern
                if clean.count("of the") >= 2:
                    print(Fore.YELLOW + f"[EARS] Narration pattern filtered: '{clean}'")
                    return None, None

                # Passive voice
                _passive = ["was a ","were a ","is a presentation","was the ",
                            "this was","that was","reading of","parts response","positive parts"]
                if any(p in clean for p in _passive) and len(words) > 6:
                    print(Fore.YELLOW + f"[EARS] Passive pattern filtered: '{clean}'")
                    return None, None

                # Unknown starter
                _valid_starters = {
                    "open","close","start","stop","play","pause","skip","set","get",
                    "show","find","tell","what","how","why","when","where","who","which",
                    "can","could","will","volume","mute","unmute","brightness","remind",
                    "schedule","add","delete","remove","create","make","turn","switch",
                    "enable","disable","check","search","list","hey","hi","hello","ok",
                    "okay","yes","no","cancel","clear","increase","decrease","raise",
                    "lower","maximize","minimize","snap","move","resize","pin","unpin",
                    "restart","shutdown","lock","sleep","wake","timer","alarm","note",
                    "write","read","send","call","message","email","my","do","is","are",
                    "was","i","the","a","place","where","recalibrate",
                }
                if words and words[0] not in _valid_starters and len(words) > 8:
                    print(Fore.YELLOW + f"[EARS] Unknown starter filtered: '{clean[:60]}'")
                    return None, None

                # ── Autocorrect ────────────────────────────────────────────
                corrections = {
                    "semen":"seven","savin":"seven","sibin":"seven","simon":"seven",
                    "siman":"seven","heaven":"seven","siwen":"seven","so when":"seven",
                    "servant":"seven","sir'en":"seven","siren":"seven","sevan":"seven",
                    "i7":"hi seven","i 7":"hi seven",
                    "fight explorer":"file explorer","five explorer":"file explorer",
                    "aye":"hi","alo":"hello",
                    "and roll my voice":"enroll my voice","and roll":"enroll",
                    "in role":"enroll","in roll":"enroll","unroll":"enroll","un roll":"enroll",
                    "candle":"camera","candor":"camera","camera up":"camera",
                    "hit":"hey","had":"hey","hate":"hey",
                    "closer":"close","clothes":"close","volume up to":"volume",
                    "what's the whether":"what is the weather",
                    "what's the weather":"what is the weather","whether":"weather",
                }
                for wrong, right in corrections.items():
                    if wrong in clean:
                        full_text = full_text.lower().replace(wrong, right)
                        break

                return full_text.capitalize(), AUDIO_TEMP_PATH

            except sr.WaitTimeoutError:
                return None, None
            except OSError as _ose:
                print(Fore.YELLOW + f"[EARS] Microphone disconnected: {_ose}")
                import time as _t
                _t.sleep(1)
                return None, None
            except Exception:
                return None, None

    except OSError as _outer_ose:
        # OSError from context manager __exit__ (mic disconnect during cleanup)
        print(Fore.YELLOW + f"[EARS] Mic stream error: {_outer_ose}")
        import time as _t
        _t.sleep(1)
        return None, None
    except Exception:
        return None, None


# =============================================================================
# INTERRUPT LISTENER
# =============================================================================

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """
    Lightweight listener running during TTS speech.
    Detects interrupt words and triggers callback.
    """
    recognizer = sr.Recognizer()
    recognizer.energy_threshold       = 300
    recognizer.pause_threshold        = 0.8
    recognizer.non_speaking_duration  = 0.5

    self_voice_ghosts = [
        "thank you","thanks","thanks for watching","you","bye","okay",
        "subtitles","subscribe","video","caption","copyright","amara"
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
                except Exception:
                    pass

                if not text or len(text) < 2:
                    continue

                clean = text.replace(".","").replace("!","").replace(",","").strip()

                if clean in self_voice_ghosts:
                    continue

                for word in interrupt_words:
                    if word in clean:
                        print(f"[EARS] Interrupt detected: '{clean}' (matched: '{word}')")
                        on_interrupt_callback()
                        return

        except Exception:
            continue

    try:
        if os.path.exists("temp_interrupt.wav"):
            os.remove("temp_interrupt.wav")
    except Exception:
        pass