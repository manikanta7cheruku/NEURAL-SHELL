"""
=============================================================================
PROJECT SEVEN - ears/core.py
Version: 1.2.7 - Final Production Pipeline

PIPELINE (in order):
    1. Microphone capture (SpeechRecognition, adaptive threshold)
    2. AGC — normalize volume (ears/agc.py)
    3. AEC — remove echo if speaking (ears/aec.py)
    4. Signal gates — RMS, duration, crest factor (ears/signal_gates.py)
    5. Whisper transcription — in memory via BytesIO
    6. TranscriptionInfo confidence — avg_logprob, VAD removal ratio
    7. Per-segment confidence — no_speech_prob filter
    8. Non-ASCII / emoji filter — catches music emoji output
    9. Hallucination filter — exact, substring, saturation, music patterns
    10. Repetition loop detection
    11. Semantic coherence check
    12. Autocorrect — RapidFuzz fuzzy correction
    13. Return clean text

ARCHITECTURE:
    ears/core.py              This file. Orchestrator only.
    ears/noise_floor.py       Adaptive noise floor + calibration.
    ears/signal_gates.py      RMS, duration, crest factor gates.
    ears/hallucination_filter.py  Hallucination detection (JSON-backed).
    ears/hallucinations.json  Updatable phrase list.
    ears/autocorrect.py       RapidFuzz fuzzy autocorrect.
    ears/agc.py               Automatic gain control.
    ears/aec.py               Acoustic echo cancellation.

NO TEMP FILES:
    Audio stays in RAM via BytesIO throughout.
    temp_audio.wav written only when Voice ID is enabled in config.

SOURCE TAGGING:
    Returns ("__voice__", audio_path) on valid speech from microphone.
    audio_path is "__voice__" sentinel when Voice ID disabled.
    audio_path is "temp_audio.wav" when Voice ID enabled.
    main.py uses audio_path to set speaker_id correctly.
=============================================================================
"""

import io
import os
import re
import json
import time
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
from ears.signal_gates import check as _signal_check
from ears.hallucination_filter import (
    is_hallucination,
    is_repetition_loop,
    is_incoherent,
)
from ears.autocorrect import correct as _autocorrect
from ears import agc as _agc
from ears import aec as _aec

colorama.init(autoreset=True)

# Start AEC loopback capture
# Gracefully disables itself if pyaudiowpatch not installed
_aec.start()


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


def _is_voice_id_enabled() -> bool:
    """Read Voice ID gate state from config."""
    try:
        cfg_path = os.path.join(
            os.environ.get('APPDATA', os.path.expanduser('~')),
            'SEVEN', 'config.json'
        )
        if os.path.exists(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return (
                cfg
                .get('voice_gates', {})
                .get('speaker_verify', {})
                .get('enabled', False)
            )
    except Exception:
        pass
    return False


# =============================================================================
# WHISPER LOADER
# =============================================================================

def _load_whisper(model_size: str) -> WhisperModel:
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            print(Fore.CYAN + f"[EARS] GPU: {name}")
            model = WhisperModel(
                model_size, device="cuda", compute_type="float16"
            )
            print(Fore.GREEN + f"[EARS] Whisper {model_size} — GPU ready")
            return model
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] GPU init failed: {e}")

    try:
        model = WhisperModel(
            model_size, device="cpu", compute_type="int8"
        )
        print(Fore.YELLOW + f"[EARS] Whisper {model_size} — CPU mode")
        return model
    except Exception as e:
        print(Fore.RED + f"[EARS] Whisper load failed: {e}")
        raise


_MODEL_SIZE = _get_configured_model()
print(Fore.CYAN + f"[EARS] Loading Whisper ({_MODEL_SIZE})...")
audio_model = _load_whisper(_MODEL_SIZE)

# Calibrate after Whisper loads — mic may be busy during model load
_nf.calibrate()


# =============================================================================
# INTERRUPT FLAG
# =============================================================================

_force_return_event = threading.Event()


def set_force_return(val: bool):
    if val:
        _force_return_event.set()
    else:
        _force_return_event.clear()


# =============================================================================
# SPEAKING STATE HOOK
# Injected by main.py after mouth module loads.
# Returns True if Seven is currently playing TTS audio.
# Prevents main listen() from processing mic audio while Seven speaks.
# =============================================================================

_is_speaking_fn = lambda: False


def set_speaking_fn(fn):
    """
    Register the function that returns True when Seven is speaking.
    Called by main.py after ctx.mouth is loaded:
        ears.core.set_speaking_fn(ctx.mouth.is_speaking)
    """
    global _is_speaking_fn
    _is_speaking_fn = fn


# =============================================================================
# WHISPER TRANSCRIPTION — IN MEMORY
# =============================================================================

def _transcribe(wav_bytes: bytes) -> tuple:
    """
    Transcribe WAV bytes using Whisper via BytesIO.
    No temp files written.

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
            no_speech_threshold=0.6,
            # Reduced from 0.7 — stricter silence rejection.
            # 0.7 meant Whisper would accept segments it was 30% unsure about.
            # 0.6 means it must be 40% sure there is real speech.
            log_prob_threshold=-0.4,
            # Tightened from -0.5 — rejects low-confidence segments sooner.
            # -0.5 let through many borderline guesses ("Bonjour", "Can save").
            # -0.4 requires Whisper to be more confident before accepting.
            vad_filter=True,
            vad_parameters={
                "threshold":               0.6,
                # Raised from 0.5 — Silero VAD must be 60% sure speech
                # is present before passing segment to Whisper decoder.
                # This is the most impactful single parameter for
                # reducing ambient audio transcription.
                "min_speech_duration_ms":  300,
                # Raised from 200 — segments shorter than 300ms are
                # almost never real voice commands. Rejects clicks,
                # coughs, brief noise bursts that Silero misclassifies.
                "min_silence_duration_ms": 400,
            },
        )

        if isinstance(result, tuple):
            segments = list(result[0])
            info     = result[1] if len(result) > 1 else None
        else:
            segments = list(result)
            info     = None

        # Per-segment confidence filter
        # Whisper sets no_speech_prob per segment — high value means
        # Whisper detected that segment contains no real speech.
        # Filter out segments where Whisper is not confident.
        # Threshold: 0.6 — above this the segment is likely silence/noise.
        clean_segments = []
        for seg in segments:
            seg_no_speech = getattr(seg, 'no_speech_prob', 0.0)
            seg_avg_logp  = getattr(seg, 'avg_logprob',    0.0)
            if seg_no_speech > 0.6:
                # Whisper says this segment has no speech — skip it
                continue
            if seg_avg_logp < -1.2:
                # Whisper had very low confidence on this segment — skip it
                continue
            clean_segments.append(seg)

        full_text = "".join(s.text for s in clean_segments).strip()
        return full_text, info

    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Whisper error: {e}")
        return "", None


def _check_confidence(info) -> tuple:
    """
    Check TranscriptionInfo for hallucination signals.

    Duration-aware thresholds:
        Short clips (< 1.5s) require higher confidence.
        Whisper is much less reliable on short clips — the decoder
        has less context to work with and guesses more aggressively.
        A 1-second clip that passes VAD with low logprob is almost
        certainly a mishearing.

    Returns: (passed: bool, reason: str)
    """
    if info is None:
        return True, "no info"

    try:
        duration = getattr(info, 'duration', None)

        # Duration-aware logprob threshold
        # Short clips need stricter confidence requirement
        if duration is not None and duration < 1.5:
            logprob_threshold = -0.35
            # Stricter than normal (-0.4 in Whisper params) for short clips
            # "Bonjour" from 1.09s clip would have been caught here
        else:
            logprob_threshold = -0.8

        avg_lp = getattr(info, 'avg_logprob', None)
        if avg_lp is not None and avg_lp < logprob_threshold:
            return False, (
                f"avg_logprob {avg_lp:.3f} below "
                f"{'strict ' if duration and duration < 1.5 else ''}"
                f"threshold {logprob_threshold} "
                f"(clip duration: {duration:.2f}s)"
            )

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
# NON-ASCII / EMOJI / MUSIC DETECTION
# =============================================================================

def _check_text_validity(text: str) -> tuple:
    """
    Reject non-ASCII content and detected music patterns.

    Whisper outputs emoji (🎵🎶) when it detects music but cannot
    transcribe words. These are never valid voice commands.

    Whisper also transcribes sung lyrics with phonetic patterns like
    "o-o-o-o-oh" and "we-e-e" which are never commands.

    Returns: (valid: bool, reason: str)
    """
    if not text or not text.strip():
        return False, "empty text"

    # Check ASCII ratio — music emoji fail this
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    total_chars = len(text.replace(" ", ""))
    if total_chars > 0 and ascii_chars / total_chars < 0.85:
        return False, (
            f"non-ASCII content ({ascii_chars}/{total_chars} ASCII chars) "
            f"— likely music emoji"
        )

    # Check for music-specific unicode characters
    music_chars = set('♪♫🎵🎶🎤🎼')
    if any(c in music_chars for c in text):
        return False, "music unicode characters in transcription"

    words = text.lower().split()
    hyphenated_count = sum(
        1 for w in words
        if '-' in w and len(w) > 3 and w.count('-') >= 2
    )
    if len(words) >= 4 and hyphenated_count >= 2:
        return False, (
            f"sung phonetics detected "
            f"({hyphenated_count} hyphenated syllable words)"
        )

    return True, "ok"


# =============================================================================
# MAIN LISTEN FUNCTION
# =============================================================================

def listen() -> tuple:
    """
    Listen for one utterance and return transcribed text.

    Returns:
        (text: str, audio_path: str) on valid speech
            audio_path = "__voice__" when Voice ID disabled
            audio_path = "temp_audio.wav" when Voice ID enabled
        (None, None) on silence, noise, or any rejection
    """
    print(Fore.WHITE + "[EARS] Waiting for input...")

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Microphone unavailable: {e}")
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
                recognizer.energy_threshold = _nf.get_min_noise_floor()
                listen_timeout              = 1.5
                phrase_limit                = 1
            else:
                listen_timeout  = 10
                phrase_limit    = 15

            print(Fore.WHITE + (
                f"[EARS] Listening — "
                f"threshold={recognizer.energy_threshold:.0f}"
            ))

            # ── Capture ─────────────────────────────────────────────────
            try:
                audio     = recognizer.listen(
                    source,
                    timeout=listen_timeout,
                    phrase_time_limit=phrase_limit
                )
                wav_bytes = audio.get_wav_data()
                print(Fore.WHITE + (
                    f"[EARS] Captured — "
                    f"{len(wav_bytes) // 1024}KB"
                ))
                _nf.on_audio_captured()

            except sr.WaitTimeoutError:
                _nf.on_timeout()
                return None, None
            except OSError as e:
                print(Fore.YELLOW + f"[EARS] Mic error: {e}")
                time.sleep(1)
                return None, None
            except Exception:
                return None, None

            # ── AGC — normalize volume ───────────────────────────────────
            wav_bytes = _agc.apply_to_wav_bytes(wav_bytes)

            # ── AEC — remove echo ────────────────────────────────────────
            if _aec.is_available():
                try:
                    import wave as _wv
                    with _wv.open(io.BytesIO(wav_bytes), 'rb') as wf:
                        _sr  = wf.getframerate()
                        _pcm = wf.readframes(wf.getnframes())
                    _mic_f32 = (
                        np.frombuffer(_pcm, dtype=np.int16)
                        .astype(np.float32) / 32767.0
                    )
                    _cleaned = _aec.apply(_mic_f32, _sr)
                    _buf = io.BytesIO()
                    with _wv.open(_buf, 'wb') as wf_out:
                        wf_out.setnchannels(1)
                        wf_out.setsampwidth(2)
                        wf_out.setframerate(_sr)
                        wf_out.writeframes(
                            (_cleaned * 32767.0)
                            .astype(np.int16)
                            .tobytes()
                        )
                    wav_bytes = _buf.getvalue()
                except Exception as e:
                    print(Fore.YELLOW + f"[EARS] AEC error: {e}")

            # ── Signal gates ─────────────────────────────────────────────
            passed, rms, reason = _signal_check(
                wav_bytes, _nf.get_threshold()
            )
            if not passed:
                _nf.update(rms)
                print(Fore.YELLOW + f"[EARS] Gate rejected — {reason}")
                return None, None

            # ── Speaking guard ────────────────────────────────────────────
            # If Seven is currently speaking, audio captured now is either:
            # (a) Seven's own TTS feeding back through the mic, or
            # (b) User trying to interrupt — handled by listen_for_interrupt.
            # Either way, the main pipeline should not process this clip.
            # main.py double-speech lock handles this at a higher level,
            # but checking here prevents Whisper from running unnecessarily.
            if _is_speaking_fn():
                return None, None

            # ── Whisper transcription ────────────────────────────────────
            full_text, info = _transcribe(wav_bytes)
            if not full_text:
                print(Fore.YELLOW + "[EARS] Whisper returned empty")
                return None, None

            # ── TranscriptionInfo confidence ─────────────────────────────
            conf_ok, conf_reason = _check_confidence(info)
            if not conf_ok:
                print(Fore.YELLOW + f"[EARS] Confidence rejected — {conf_reason}")
                return None, None

            # ── Non-ASCII / emoji / music filter ─────────────────────────
            text_ok, text_reason = _check_text_validity(full_text)
            if not text_ok:
                print(Fore.YELLOW + f"[EARS] Content rejected — {text_reason}")
                return None, None

            # ── Normalise for filter checks ──────────────────────────────
            clean = full_text.lower().strip()
            for ch in [".", "!", ",", "?", "..."]:
                clean = clean.replace(ch, "")
            clean = clean.strip()

            if len(clean) < 2:
                return None, None

            # Single word guard
            # Single isolated words from Whisper are almost always
            # mishearings or hallucinations unless they are a known command.
            # "Bonjour", "Yes", "Okay", "Sure" — these are not commands.
            # Exception: single-word wake words like "Seven" are handled
            # by the wake word gate in main.py, not here.
            _single_word_passthrough = {
                "stop", "seven", "pause", "resume", "yes", "no",
                "open", "close", "help", "back", "next", "play",
            }
            words_check = clean.split()
            if len(words_check) == 1 and clean not in _single_word_passthrough:
                print(Fore.YELLOW + (
                    f"[EARS] Single word rejected — '{clean}' "
                    f"(not in passthrough list)"
                ))
                return None, None

            # ── Hallucination filter ─────────────────────────────────────
            is_ghost, ghost_reason = is_hallucination(clean, full_text.lower())
            if is_ghost:
                print(Fore.YELLOW + f"[EARS] Hallucination — {ghost_reason}")
                return None, None

            # ── Repetition loop ──────────────────────────────────────────
            if is_repetition_loop(clean):
                print(Fore.YELLOW + (
                    f"[EARS] Repetition loop — '{clean[:60]}'"
                ))
                return None, None

            # ── Semantic coherence ───────────────────────────────────────
            if is_incoherent(clean):
                print(Fore.YELLOW + (
                    f"[EARS] Incoherent input — '{clean[:60]}'"
                ))
                return None, None

            # ── Autocorrect ──────────────────────────────────────────────
            corrected = _autocorrect(full_text)
            final     = corrected.strip().capitalize()
            if not final:
                return None, None

            print(Fore.GREEN + f"[EARS] Transcribed: '{final}'")

            # ── Determine audio path for Voice ID ────────────────────────
            # Write temp file only when Voice ID is enabled.
            # Avoids unnecessary disk writes in the common case.
            audio_out_path = "__voice__"
            if _is_voice_id_enabled():
                try:
                    with open("temp_audio.wav", "wb") as f:
                        f.write(wav_bytes)
                    audio_out_path = "temp_audio.wav"
                except Exception as e:
                    print(Fore.YELLOW + f"[EARS] Audio save failed: {e}")

            return final, audio_out_path

    except OSError as e:
        print(Fore.YELLOW + f"[EARS] Stream error: {e}")
        time.sleep(1)
        return None, None
    except Exception as e:
        print(Fore.RED + f"[EARS] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None, None


# =============================================================================
# INTERRUPT LISTENER
# Mic opened ONCE. Audio in RAM. beam_size=1 for speed.
# =============================================================================

def listen_for_interrupt(interrupt_words, on_interrupt_callback, stop_event):
    """
    Lightweight interrupt detector during TTS playback.
    Runs in background thread. Returns on first match.
    """
    recognizer                          = sr.Recognizer()
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold         = _nf.get_threshold()
    recognizer.pause_threshold          = 0.6
    recognizer.non_speaking_duration    = 0.3

    _interrupt_ghosts = {
        "thank you", "thanks", "you", "bye",
        "okay", "subtitles", "subscribe", "caption",
    }

    # Open mic once — hold for duration of TTS
    try:
        interrupt_mic = sr.Microphone()
        mic_ctx       = interrupt_mic.__enter__()
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] Interrupt mic unavailable: {e}")
        return

    try:
        while not stop_event.is_set():
            try:
                audio = recognizer.listen(
                    mic_ctx, timeout=1.5, phrase_time_limit=3
                )
            except sr.WaitTimeoutError:
                continue
            except Exception:
                break

            try:
                wav_bytes = audio.get_wav_data()

                # Quick energy check — if clip is near-silent, skip Whisper.
                # This prevents 3 unnecessary Whisper runs while Seven speaks.
                # The interrupt listener runs during TTS — most clips are
                # just Seven's own voice or room noise. Check energy first.
                import wave as _wv_int
                with _wv_int.open(io.BytesIO(wav_bytes), 'rb') as _wf_int:
                    _pcm_int = _wf_int.readframes(_wf_int.getnframes())
                _arr_int = np.frombuffer(_pcm_int, dtype=np.int16).astype(np.float32)
                _rms_int = float(np.sqrt(np.mean(_arr_int ** 2)))
                # Use a lower threshold than main pipeline — interrupt words
                # might be spoken quietly. But reject near-silence entirely.
                _interrupt_threshold = max(_nf.get_threshold() * 0.5, 200.0)
                if _rms_int < _interrupt_threshold:
                    continue

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

                text = "".join(
                    s.text for s in segments
                ).strip().lower()

            except Exception:
                continue

            if not text or len(text) < 2:
                continue

            clean = (
                text
                .replace(".", "")
                .replace("!", "")
                .replace(",", "")
                .strip()
            )

            if clean in _interrupt_ghosts:
                continue

            for word in interrupt_words:
                if re.search(
                    r'\b' + re.escape(word) + r'\b', clean
                ):
                    print(Fore.YELLOW + (
                        f"[EARS] Interrupt: '{word}' in '{clean}'"
                    ))
                    on_interrupt_callback()
                    return

    finally:
        try:
            interrupt_mic.__exit__(None, None, None)
        except Exception:
            pass