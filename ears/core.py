"""
=============================================================================
PROJECT SEVEN - ears/core.py (The Listener)
Version: 2.0 — Clean Signal Pipeline

WHAT CHANGED FROM 1.3:
    1. Removed adjust_for_ambient_noise — conflicted with adaptive floor
    2. Removed initial_prompt from Whisper — was teaching it to hallucinate
    3. Tightened Whisper confidence thresholds — no_speech 0.6->0.7, logprob -0.7->-0.5
    4. Tightened Silero VAD threshold 0.4->0.5
    5. Lowered crest factor minimum 3.5->2.2 — was blocking quiet/distant voices
    6. Raised phrase_time_limit 7->15 seconds — was cutting off natural speech
    7. Removed word count cap (>18) — was silently dropping real input
    8. Removed valid starters filter — was blocking natural conversation
    9. Removed passive voice filter — was blocking real phrases
    10. Removed narration filter — was blocking real questions
    11. Removed trailing-off filter — was blocking real sentences
    12. Cleaned ghost filter — removed real words (alright, yes, no)
    13. Cleaned forbidden list — removed patterns that match real speech
    14. Raised filler ratio threshold 0.75->0.85, minimum 4->6 words
=============================================================================
"""

import speech_recognition as sr
from faster_whisper import WhisperModel
import os
import threading
import numpy as np
import colorama
from colorama import Fore

colorama.init(autoreset=True)

MODEL_SIZE      = "medium.en"
AUDIO_TEMP_PATH = "temp_audio.wav"

# External interrupt flag — set True to make listen() return immediately
_force_return = False

def set_force_return(val: bool):
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
#
# HOW IT WORKS:
#   1. At startup: record 1.5 seconds of silence, measure RMS, set baseline
#   2. Every rejected clip feeds its RMS into a rolling 20-sample average
#   3. Threshold = rolling_average x MULTIPLIER (2.2)
#   4. Environment gets louder: threshold rises naturally
#   5. Fan turns off: next clips are quieter, average drops, threshold drops
#   6. Hard cap at 500 prevents runaway from music or TV bleed
# =============================================================================

_noise_floor     = 0.0
_noise_samples   = []
_NOISE_WINDOW    = 20
_MULTIPLIER      = 2.2
_MIN_CREST       = 2.2   # lowered from 3.5 — quiet voices and laptop mics dip below 3.5
_MIN_DURATION    = 0.4   # minimum speech duration in seconds
_floor_lock      = threading.Lock()
_initial_floor   = 0.0
_NOISE_FLOOR_CAP = 500


def _update_noise_floor(rms: float):
    global _noise_floor, _noise_samples
    with _floor_lock:
        _noise_samples.append(rms)
        if len(_noise_samples) > _NOISE_WINDOW:
            _noise_samples.pop(0)
        prev         = _noise_floor
        new_floor    = sum(_noise_samples) / len(_noise_samples)
        _noise_floor = min(new_floor, _NOISE_FLOOR_CAP)
        if prev > 0 and abs(_noise_floor - prev) / prev > 0.20:
            print(Fore.CYAN + f"[EARS] Noise floor adjusted: {prev * _MULTIPLIER:.0f} -> {_noise_floor * _MULTIPLIER:.0f}")


def _get_threshold() -> float:
    with _floor_lock:
        if _noise_floor == 0:
            return 300
        return _noise_floor * _MULTIPLIER


def _do_initial_calibration():
    global _noise_samples, _noise_floor, _initial_floor
    try:
        _r = sr.Recognizer()
        with sr.Microphone() as _src:
            print(Fore.CYAN + "[EARS] Calibrating ambient noise — 1.5 seconds, stay quiet...")
            _audio = _r.record(_src, duration=1.5)
            _wav   = _audio.get_wav_data()
            _arr   = np.frombuffer(_wav, dtype=np.int16).astype(np.float32)
            _rms   = float(np.sqrt(np.mean(_arr ** 2)))
            with _floor_lock:
                _noise_samples = [_rms] * 5
                _noise_floor   = _rms
                _initial_floor = _rms
            print(Fore.GREEN + f"[EARS] Noise floor: {_rms:.0f} | Voice threshold: {_rms * _MULTIPLIER:.0f}")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Calibration failed: {e} — using default")
        with _floor_lock:
            _noise_samples = [136.0] * 5
            _noise_floor   = 136.0
            _initial_floor = 136.0


_do_initial_calibration()


# =============================================================================
# SIGNAL QUALITY CHECK
#
# Three gates before Whisper even runs:
#   Gate 1 — RMS energy: is there enough sound energy to be speech?
#   Gate 2 — Duration: is the clip long enough to be a word?
#   Gate 3 — Crest factor: is the sound shaped like speech (spiky) vs noise (flat)?
#
# Noise (fan, AC, hum) is flat — low crest factor.
# Speech is spiky — consonants create sharp peaks relative to average.
# This is the most reliable hardware-level filter before any AI runs.
# =============================================================================

def _check_signal_quality(wav_data: bytes) -> tuple:
    """
    Check if audio signal looks like speech before sending to Whisper.

    Returns:
        (passed: bool, rms: float, reason: str)
    """
    try:
        audio_np  = np.frombuffer(wav_data, dtype=np.int16).astype(np.float32)
        rms       = float(np.sqrt(np.mean(audio_np ** 2)))
        peak      = float(np.max(np.abs(audio_np)))
        dur       = len(audio_np) / 16000.0
        threshold = _get_threshold()

        # Gate 1: energy
        if rms < threshold:
            return False, rms, f"RMS {rms:.0f} < threshold {threshold:.0f} — below noise floor"

        # Gate 2: duration
        if dur < _MIN_DURATION:
            return False, rms, f"Duration {dur:.2f}s < {_MIN_DURATION}s — too short"

        # Gate 3: crest factor
        crest = peak / rms if rms > 0 else 0
        if crest < _MIN_CREST:
            return False, rms, f"Crest {crest:.2f} < {_MIN_CREST} — diffuse noise not speech"

        print(Fore.CYAN + f"[EARS] Signal OK — RMS:{rms:.0f} Crest:{crest:.2f} Dur:{dur:.2f}s Thresh:{threshold:.0f}")
        return True, rms, "ok"

    except Exception as e:
        # If signal check fails, let Whisper decide
        print(Fore.YELLOW + f"[EARS] Signal check error: {e} — passing to Whisper")
        return True, 0.0, "check_failed"


# =============================================================================
# WHISPER OUTPUT FILTER
#
# Only filters things Whisper hallucinates from silence or near-silence.
# Does NOT filter real speech patterns.
# Does NOT filter by word count.
# Does NOT filter by sentence structure.
# Does NOT filter by what word the sentence starts with.
# =============================================================================

# Exact phrases Whisper generates from silence — verified hallucinations
_SILENCE_HALLUCINATIONS = {
    "thank you", "thanks", "you",
    "bye", "goodbye",
    "the", "a", "i",
    "so", "and", "or",
    "hmm", "hm", "uh", "um", "ah", "oh",
    "music", "applause", "laughter",
    "subtitles", "caption", "captions",
    "subscribe", "like and subscribe",
    "thanks for watching", "thank you for watching",
    "see you next time", "see you in the next video",
    "bada ba ba ba", "ba ba ba", "da da da", "la la la",
    ".", "..", "...", " ", "",
}

# Substring patterns that only appear in Whisper hallucinations, never in real voice commands
_HALLUCINATION_SUBSTRINGS = [
    "amara.org",
    "mooji.org",
    "www.",
    ".org",
    "bada ba",
    "ba ba ba ba",
    "da da da da",
    "la la la la",
]

# Filler words — used only for ratio check, not for filtering themselves
_FILLER_WORDS = {
    "the", "a", "an", "is", "it", "to", "of", "and", "or", "but",
    "in", "on", "at", "for", "well", "so", "that", "this", "what",
    "i", "you", "he", "she", "they", "we", "my", "your", "his", "her",
    "up", "with", "be", "are", "was", "do", "did", "have", "has",
}


def _is_hallucination(clean: str) -> tuple:
    """
    Check if Whisper output is a known hallucination.

    Returns:
        (is_hallucination: bool, reason: str)
    """
    # Exact match against known silence outputs
    if clean in _SILENCE_HALLUCINATIONS:
        return True, f"silence hallucination: '{clean}'"

    # Substring match — only genuine hallucination-only patterns
    for pattern in _HALLUCINATION_SUBSTRINGS:
        if pattern in clean:
            return True, f"hallucination pattern: '{pattern}'"

    words = clean.split()

    # Repeated single syllable — "ba ba ba", "da da da"
    if len(words) >= 3:
        unique = set(words)
        if len(unique) == 1 and len(list(unique)[0]) <= 3:
            return True, f"repeated syllable: '{clean}'"

    # Extremely high filler ratio — only for 6+ word clips
    # 0.85 threshold: 85% of words must be pure filler to reject
    # Real sentences like "what is the weather" pass (50% filler)
    # Pure filler noise like "the the the and the and" fails (100%)
    if len(words) >= 6:
        content_words = [w for w in words if w not in _FILLER_WORDS]
        filler_ratio  = 1 - (len(content_words) / len(words))
        if filler_ratio > 0.85:
            return True, f"pure filler ({filler_ratio:.0%}): '{clean}'"

    return False, ""


# =============================================================================
# MAIN LISTEN FUNCTION
# =============================================================================

def listen():
    """
    Listen for speech and return transcribed text.

    Signal pipeline:
        Microphone -> SpeechRecognition energy gate -> WAV
        -> RMS gate -> Duration gate -> Crest gate
        -> Whisper (medium.en, VAD enabled)
        -> Confidence filter -> Hallucination filter
        -> Autocorrect -> Return

    Returns:
        (transcribed_text: str, audio_path: str) on success
        (None, None) on silence, noise, or hallucination
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
            # Do NOT call adjust_for_ambient_noise here.
            # Our adaptive floor is more accurate and does not conflict.
            recognizer.dynamic_energy_threshold = False
            recognizer.energy_threshold         = _get_threshold()
            recognizer.pause_threshold          = 0.8
            recognizer.non_speaking_duration    = 0.4
            recognizer.phrase_threshold         = 0.1

            if _force_return:
                recognizer.energy_threshold = 50
                _listen_timeout = 1.5
                _phrase_limit   = 1
            else:
                _listen_timeout = None
                _phrase_limit   = 15  # raised from 7 — natural speech can be 10-12 seconds

            try:
                audio    = recognizer.listen(
                    source,
                    timeout=_listen_timeout,
                    phrase_time_limit=_phrase_limit
                )
                wav_data = audio.get_wav_data()

            except sr.WaitTimeoutError:
                return None, None
            except OSError as _ose:
                print(Fore.YELLOW + f"[EARS] Microphone disconnected: {_ose}")
                import time as _t
                _t.sleep(1)
                return None, None
            except Exception:
                return None, None

            # ── Gate 1/2/3: Signal quality before Whisper ─────────────────
            passed, rms, reason = _check_signal_quality(wav_data)
            if not passed:
                _update_noise_floor(rms)
                print(Fore.YELLOW + f"[EARS] Rejected — {reason}")
                return None, None

            # ── Write WAV for Whisper ──────────────────────────────────────
            try:
                with open(AUDIO_TEMP_PATH, "wb") as f:
                    f.write(wav_data)
            except Exception as _we:
                print(Fore.YELLOW + f"[EARS] WAV write failed: {_we}")
                return None, None

            # ── Whisper Transcription ──────────────────────────────────────
            # no_speech_threshold=0.7  — raised from 0.6, rejects more silence
            # log_prob_threshold=-0.5  — raised from -0.7, rejects low confidence
            # vad_filter=True          — Silero VAD runs inside Whisper
            # vad threshold=0.5        — raised from 0.4, more aggressive
            # NO initial_prompt        — removed, was biasing Whisper to hallucinate
            try:
                _result = audio_model.transcribe(
                    AUDIO_TEMP_PATH,
                    beam_size=5,
                    language="en",
                    condition_on_previous_text=False,
                    no_speech_threshold=0.7,
                    log_prob_threshold=-0.5,
                    vad_filter=True,
                    vad_parameters={
                        "threshold":               0.5,
                        "min_speech_duration_ms":  200,
                        "min_silence_duration_ms": 300,
                    },
                )
                # faster-whisper returns (generator, info) tuple
                # Must consume generator immediately before info goes out of scope
                if isinstance(_result, tuple):
                    segments = list(_result[0])
                else:
                    segments = list(_result)
            except Exception as _wh:
                print(Fore.YELLOW + f"[EARS] Whisper error: {_wh}")
                return None, None

            # ── Confidence Filter ──────────────────────────────────────────
            confident_segments = []
            for seg in segments:
                if hasattr(seg, 'no_speech_prob') and seg.no_speech_prob > 0.7:
                    print(Fore.YELLOW + f"[EARS] Low confidence segment (no_speech={seg.no_speech_prob:.2f}): '{seg.text.strip()}'")
                    continue
                confident_segments.append(seg)

            full_text = "".join([s.text for s in confident_segments]).strip()
            if not full_text:
                return None, None

            # ── Clean for filter checks ────────────────────────────────────
            clean = full_text.lower().strip()
            for ch in [".", "!", ",", "?", "..."]:
                clean = clean.replace(ch, "")
            clean = clean.strip()

            if len(clean) < 2:
                return None, None

            # ── Hallucination Filter ───────────────────────────────────────
            is_ghost, ghost_reason = _is_hallucination(clean)
            if is_ghost:
                print(Fore.YELLOW + f"[EARS] Hallucination filtered — {ghost_reason}")
                return None, None

            # ── Autocorrect ────────────────────────────────────────────────
            # Corrects common Whisper mishearing of "Seven" and related words
            corrections = {
                "semen":         "seven",
                "savin":         "seven",
                "sibin":         "seven",
                "simon":         "seven",
                "siman":         "seven",
                "heaven":        "seven",
                "siwen":         "seven",
                "so when":       "seven",
                "servant":       "seven",
                "siren":         "seven",
                "sevan":         "seven",
                "i7":            "hi seven",
                "i 7":           "hi seven",
                "fight explorer":"file explorer",
                "five explorer": "file explorer",
                "and roll my voice": "enroll my voice",
                "and roll":      "enroll",
                "in role":       "enroll",
                "in roll":       "enroll",
                "unroll":        "enroll",
                "what's the whether": "what is the weather",
                "what's the weather": "what is the weather",
                "whether":       "weather",
            }
            result_text = full_text.lower().strip()
            for wrong, right in corrections.items():
                if wrong in result_text:
                    result_text = result_text.replace(wrong, right)
                    break

            final = result_text.strip().capitalize()
            if not final:
                return None, None

            print(Fore.GREEN + f"[EARS] Heard: '{final}'")
            return final, AUDIO_TEMP_PATH

    except OSError as _outer_ose:
        print(Fore.YELLOW + f"[EARS] Mic stream error: {_outer_ose}")
        import time as _t
        _t.sleep(1)
        return None, None
    except Exception:
        return None, None


# =============================================================================
# INTERRUPT LISTENER
# Runs during TTS speech. Lightweight. Detects stop words only.
# =============================================================================

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """
    Lightweight listener running while Seven is speaking.
    Uses beam_size=1 for speed. Only checks for interrupt words.
    Does not run the full signal pipeline — speed matters here.
    """
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold         = _get_threshold()
    recognizer.pause_threshold          = 0.6
    recognizer.non_speaking_duration    = 0.3

    _interrupt_ghosts = {
        "thank you", "thanks", "you", "bye", "okay",
        "subtitles", "subscribe", "caption",
    }

    while not stop_event.is_set():
        try:
            with sr.Microphone() as source:
                try:
                    audio = recognizer.listen(source, timeout=1.5, phrase_time_limit=3)
                except sr.WaitTimeoutError:
                    continue

                interrupt_audio_path = "temp_interrupt.wav"
                try:
                    with open(interrupt_audio_path, "wb") as f:
                        f.write(audio.get_wav_data())
                except Exception:
                    continue

                try:
                    _int_result = audio_model.transcribe(
                        interrupt_audio_path,
                        beam_size=1,
                        language="en",
                        no_speech_threshold=0.7,
                        vad_filter=True,
                    )
                    if isinstance(_int_result, tuple):
                        _int_segments = list(_int_result[0])
                    else:
                        _int_segments = list(_int_result)
                    text = "".join([s.text for s in _int_segments]).strip().lower()
                except Exception:
                    continue
                finally:
                    try:
                        os.remove(interrupt_audio_path)
                    except Exception:
                        pass

                if not text or len(text) < 2:
                    continue

                clean = text.replace(".", "").replace("!", "").replace(",", "").strip()

                if clean in _interrupt_ghosts:
                    continue

                for word in interrupt_words:
                    if word in clean:
                        print(Fore.YELLOW + f"[EARS] Interrupt: '{clean}' matched '{word}'")
                        on_interrupt_callback()
                        return

        except Exception:
            continue

    try:
        if os.path.exists("temp_interrupt.wav"):
            os.remove("temp_interrupt.wav")
    except Exception:
        pass