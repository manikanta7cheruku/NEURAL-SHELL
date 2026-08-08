"""
=============================================================================
PROJECT SEVEN - ears/core.py
Version: 4.0 - Modular Clean Pipeline

ARCHITECTURE:
    ears/core.py              This file. Orchestrates all sub-modules.
    ears/noise_floor.py       Adaptive noise floor + calibration.
    ears/signal_gates.py      RMS, duration, crest factor gates.
    ears/hallucination_filter.py  Hallucination detection (JSON-backed).
    ears/hallucinations.json  Updatable hallucination phrase list.
    ears/autocorrect.py       RapidFuzz fuzzy autocorrect.
    ears/wake_word.py         Fuzzy wake word detection.
    ears/push_to_talk.py      PTT keyboard gate.
    ears/voice_id.py          TitaNet speaker verification.
    ears/audio_triggers.py    DSP snap/clap detection.

PIPELINE:
    Microphone
    -> SpeechRecognition energy gate (adaptive threshold)
    -> signal_gates: RMS, duration, crest factor
    -> Whisper (in-memory BytesIO, VAD enabled, no temp files)
    -> TranscriptionInfo: avg_logprob + VAD removal ratio
    -> Per-segment: no_speech_prob filter
    -> hallucination_filter: exact, substring, repetition, coherence
    -> autocorrect: RapidFuzz fuzzy correction
    -> Return clean text to main.py

WHAT CHANGED FROM 3.0:
    1. All sub-systems extracted to separate modules.
    2. Audio stays in memory (BytesIO) — no temp_audio.wav.
    3. TranscriptionInfo consumed — avg_logprob + VAD ratio checked.
    4. Interrupt listener holds mic open (not open/close per loop).
    5. Interrupt listener uses BytesIO — no temp_interrupt.wav.
    6. _force_return uses threading.Event (not bare global bool).
    7. Hallucinations loaded from JSON — no code change needed to update.
    8. Fuzzy autocorrect via RapidFuzz.
    9. Calibration retries 3 times — fixes threshold=1 bug.
    10. Logs are clean and consistent.
=============================================================================
"""

import io
import os
import re
import json
import threading
import numpy as np
import colorama
from colorama import Fore

# numpy 2.x compatibility shim
if not hasattr(np, 'iterable'):
    np.iterable = lambda obj: hasattr(obj, '__iter__')

import speech_recognition as sr
from faster_whisper import WhisperModel

# Sub-modules
from ears import noise_floor as _nf
from ears.signal_gates         import check  as _signal_check
from ears.hallucination_filter import (
    is_hallucination,
    is_repetition_loop,
    is_incoherent,
)
from ears.autocorrect import correct as _autocorrect

colorama.init(autoreset=True)


# =============================================================================
# CONFIGURATION
# =============================================================================

def _get_configured_model() -> str:
    try:
        cfg_path = os.path.join(
            os.environ.get('APPDATA', os.path.expanduser('~')),
            'SEVEN', 'config.json'
        )
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            model = cfg.get('brain', {}).get('whisper_model', '').strip()
            if model:
                return model
    except Exception:
        pass
    return "medium.en"


# =============================================================================
# WHISPER LOADER
# =============================================================================

def _load_whisper(model_size: str) -> WhisperModel:
    """Load Whisper on GPU if available, CPU otherwise."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            print(Fore.CYAN + f"[EARS] GPU: {name}")
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            print(Fore.GREEN + f"[EARS] Whisper {model_size} — GPU ready")
            return model
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] GPU init failed: {e}")

    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print(Fore.YELLOW + f"[EARS] Whisper {model_size} — CPU mode")
        return model
    except Exception as e:
        print(Fore.RED + f"[EARS] Whisper load failed: {e}")
        raise


_MODEL_SIZE  = _get_configured_model()
print(Fore.CYAN + f"[EARS] Loading Whisper ({_MODEL_SIZE})...")
audio_model  = _load_whisper(_MODEL_SIZE)

# Run calibration after Whisper loads (mic may be busy during load)
_nf.calibrate()


# =============================================================================
# FORCE RETURN FLAG
# Thread-safe event used to make listen() return immediately.
# Set by mouth/core.py when interrupt is detected.
# =============================================================================

_force_return_event = threading.Event()

def set_force_return(val: bool):
    if val:
        _force_return_event.set()
    else:
        _force_return_event.clear()


# =============================================================================
# WHISPER TRANSCRIPTION — IN MEMORY
# No temp_audio.wav. Audio bytes passed via BytesIO.
# =============================================================================

def _transcribe(wav_bytes: bytes) -> tuple:
    """
    Transcribe WAV bytes using Whisper in-memory.

    Returns:
        (full_text: str, info: TranscriptionInfo or None)
    """
    try:
        wav_buf = io.BytesIO(wav_bytes)
        result  = audio_model.transcribe(
            wav_buf,
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

        if isinstance(result, tuple):
            segments = list(result[0])
            info     = result[1] if len(result) > 1 else None
        else:
            segments = list(result)
            info     = None

        full_text = "".join(s.text for s in segments).strip()
        return full_text, info

    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Whisper error: {e}")
        return "", None


def _check_transcription_confidence(info) -> tuple:
    """
    Check TranscriptionInfo for hallucination signals.

    Two checks:
        avg_logprob:     overall Whisper confidence. Below -1.0 = guessing.
        VAD removal:     if VAD removed >85% of clip = almost no speech.

    Returns:
        (passed: bool, reason: str)
    """
    if info is None:
        return True, "no info"

    try:
        avg_lp = getattr(info, 'avg_logprob', None)
        if avg_lp is not None and avg_lp < -1.0:
            return False, f"avg_logprob {avg_lp:.3f} < -1.0"

        duration     = getattr(info, 'duration', None)
        duration_vad = getattr(info, 'duration_after_vad', None)
        if duration and duration_vad is not None and duration > 0:
            removed = duration - duration_vad
            ratio   = removed / duration
            if ratio > 0.85:
                return False, f"VAD removed {ratio:.0%} of audio"

    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Confidence check error: {e}")
        return True, "check_error"

    return True, "ok"


# =============================================================================
# MAIN LISTEN FUNCTION
# =============================================================================

def listen() -> tuple:
    """
    Listen for one utterance and return transcribed text.

    Full pipeline — see module docstring for stage descriptions.

    Returns:
        (text: str, audio_path: None) on valid speech
        (None, None) on silence, noise, or any rejection
    """
    print(Fore.WHITE + "[EARS] Waiting for input...")

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Microphone unavailable: {e}")
        import time
        time.sleep(2)
        return None, None

    try:
        with mic as source:
            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = False
            recognizer.energy_threshold         = _nf.get_threshold()
            recognizer.pause_threshold          = 0.8
            recognizer.non_speaking_duration    = 0.4
            recognizer.phrase_threshold         = 0.1

            if _force_return_event.is_set():
                recognizer.energy_threshold = _nf._MIN_NOISE_FLOOR
                listen_timeout  = 1.5
                phrase_limit    = 1
            else:
                listen_timeout  = 10
                phrase_limit    = 15

            print(Fore.WHITE + (
                f"[EARS] Listening — "
                f"threshold={recognizer.energy_threshold:.0f}"
            ))

            # ── Capture ─────────────────────────────────────────────────────
            try:
                audio    = recognizer.listen(
                    source,
                    timeout=listen_timeout,
                    phrase_time_limit=phrase_limit
                )
                wav_bytes = audio.get_wav_data()
                print(Fore.WHITE + (
                    f"[EARS] Captured — {len(wav_bytes) // 1024}KB"
                ))
                _nf.on_audio_captured()

            except sr.WaitTimeoutError:
                _nf.on_timeout()
                return None, None
            except OSError as e:
                print(Fore.YELLOW + f"[EARS] Mic error: {e}")
                import time
                time.sleep(1)
                return None, None
            except Exception:
                return None, None

            # ── Signal gates ────────────────────────────────────────────────
            passed, rms, reason = _signal_check(
                wav_bytes, _nf.get_threshold()
            )
            if not passed:
                _nf.update(rms)
                print(Fore.YELLOW + f"[EARS] Gate rejected — {reason}")
                return None, None

            # ── Whisper transcription (in-memory) ───────────────────────────
            full_text, info = _transcribe(wav_bytes)
            if not full_text:
                print(Fore.YELLOW + "[EARS] Whisper returned empty")
                return None, None

            # ── TranscriptionInfo confidence ────────────────────────────────
            conf_passed, conf_reason = _check_transcription_confidence(info)
            if not conf_passed:
                print(Fore.YELLOW + f"[EARS] Confidence rejected — {conf_reason}")
                return None, None

            # ── Normalise for filter checks ─────────────────────────────────
            clean = full_text.lower().strip()
            for ch in [".", "!", ",", "?", "..."]:
                clean = clean.replace(ch, "")
            clean = clean.strip()

            if len(clean) < 2:
                return None, None

            # ── Hallucination filter ────────────────────────────────────────
            is_ghost, ghost_reason = is_hallucination(clean, full_text.lower())
            if is_ghost:
                print(Fore.YELLOW + f"[EARS] Hallucination — {ghost_reason}")
                return None, None

            # ── Repetition loop ─────────────────────────────────────────────
            if is_repetition_loop(clean):
                print(Fore.YELLOW + f"[EARS] Repetition loop — '{clean[:60]}'")
                return None, None

            # ── Semantic coherence ──────────────────────────────────────────
            if is_incoherent(clean):
                print(Fore.YELLOW + f"[EARS] Incoherent input — '{clean[:60]}'")
                return None, None

            # ── Autocorrect ─────────────────────────────────────────────────
            corrected = _autocorrect(full_text)
            final     = corrected.strip().capitalize()
            if not final:
                return None, None

            print(Fore.GREEN + f"[EARS] Transcribed: '{final}'")
            return final, None

    except OSError as e:
        print(Fore.YELLOW + f"[EARS] Stream error: {e}")
        import time
        time.sleep(1)
        return None, None
    except Exception as e:
        print(Fore.RED + f"[EARS] Unexpected error: {e}")
        return None, None


# =============================================================================
# INTERRUPT LISTENER
#
# Runs in a background thread while Seven speaks.
# Mic opened ONCE before the loop — not per iteration.
# Audio processed in RAM — no temp files.
# beam_size=1 for minimum latency.
# =============================================================================

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """
    Lightweight interrupt detector during TTS playback.

    Opens microphone once.
    Processes audio in RAM.
    Returns as soon as interrupt word detected.
    """
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold         = _nf.get_threshold()
    recognizer.pause_threshold          = 0.6
    recognizer.non_speaking_duration    = 0.3

    _interrupt_ghosts = {
        "thank you", "thanks", "you", "bye",
        "okay", "subtitles", "subscribe", "caption",
    }

    try:
        interrupt_mic = sr.Microphone()
        mic_ctx       = interrupt_mic.__enter__()
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Interrupt mic unavailable: {e}")
        return

    try:
        while not stop_event.is_set():
            try:
                audio = recognizer.listen(mic_ctx, timeout=1.5, phrase_time_limit=3)
            except sr.WaitTimeoutError:
                continue
            except Exception:
                break

            try:
                wav_bytes = audio.get_wav_data()
                wav_buf   = io.BytesIO(wav_bytes)

                result = audio_model.transcribe(
                    wav_buf,
                    beam_size=1,
                    language="en",
                    no_speech_threshold=0.7,
                    vad_filter=True,
                )

                if isinstance(result, tuple):
                    segments = list(result[0])
                else:
                    segments = list(result)

                text = "".join(s.text for s in segments).strip().lower()

            except Exception:
                continue

            if not text or len(text) < 2:
                continue

            clean = text.replace(".", "").replace("!", "").replace(",", "").strip()
            if clean in _interrupt_ghosts:
                continue

            for word in interrupt_words:
                if re.search(r'\b' + re.escape(word) + r'\b', clean):
                    print(Fore.YELLOW + f"[EARS] Interrupt: '{word}' in '{clean}'")
                    on_interrupt_callback()
                    return

    finally:
        try:
            interrupt_mic.__exit__(None, None, None)
        except Exception:
            pass