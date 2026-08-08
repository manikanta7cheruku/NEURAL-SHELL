"""
ears/noise_floor.py
Seven — Adaptive noise floor management.

Tracks ambient noise level and provides dynamic energy threshold.
Prevents the energy gate from being set too high (missing speech)
or too low (capturing everything including fan noise).

HOW IT WORKS:
    Startup: calibrate against 1.5s of silence. Retry 3 times.
    Runtime: each rejected clip feeds into 20-sample rolling average.
    Decay:   after 3 silent timeouts, ease floor down 15%.
    Cap:     hard limits prevent runaway in either direction.

PREVIOUS BUG FIXED:
    Old code accepted RMS=0 from calibration silently.
    This set threshold to 1, making SpeechRecognition capture everything.
    Fix: retry 3 times, use 200 as safe default if all fail.
"""

import io
import wave
import threading
import numpy as np
from colorama import Fore

# Tuning constants
_MULTIPLIER          = 2.2   # threshold = floor * MULTIPLIER
_WINDOW              = 20    # rolling average window
_NOISE_FLOOR_CAP     = 500   # never higher than this (TV/music bleed)
_MIN_NOISE_FLOOR     = 50.0  # never lower than this
_MIN_VALID_RMS       = 20.0  # below this = mic not ready
_DEFAULT_FLOOR       = 200.0 # safe default if calibration fails

# State
_noise_floor         = _DEFAULT_FLOOR
_noise_samples       = []
_floor_lock          = threading.Lock()
_initial_floor       = _DEFAULT_FLOOR

# Decay state
_consecutive_timeouts = 0
_timeout_lock         = threading.Lock()
_DECAY_AFTER          = 3    # timeouts before decay
_DECAY_FACTOR         = 0.85


def get_threshold() -> float:
    """
    Return current voice detection threshold.
    Always returns at least MIN_NOISE_FLOOR * MULTIPLIER.
    """
    with _floor_lock:
        floor = max(_noise_floor, _MIN_NOISE_FLOOR)
    return floor * _MULTIPLIER


def update(rms: float):
    """
    Feed a rejected clip's RMS into the rolling average.
    Call this whenever a clip fails signal quality gates.
    """
    global _noise_floor, _noise_samples
    with _floor_lock:
        _noise_samples.append(rms)
        if len(_noise_samples) > _WINDOW:
            _noise_samples.pop(0)

        prev      = _noise_floor
        new_floor = sum(_noise_samples) / len(_noise_samples)
        _noise_floor = min(new_floor, _NOISE_FLOOR_CAP)

        if prev > 0 and abs(_noise_floor - prev) / max(prev, 1.0) > 0.20:
            print(Fore.CYAN + (
                f"[EARS] Noise floor updated: "
                f"threshold {prev * _MULTIPLIER:.0f} -> "
                f"{_noise_floor * _MULTIPLIER:.0f}"
            ))


def on_timeout():
    """
    Call this when listen() times out with no audio.
    After enough consecutive timeouts, ease the floor down.

    Prevents stuck-high threshold after a noisy event ends.
    """
    global _consecutive_timeouts, _noise_floor

    with _timeout_lock:
        _consecutive_timeouts += 1
        if _consecutive_timeouts >= _DECAY_AFTER:
            with _floor_lock:
                if _noise_floor > _MIN_NOISE_FLOOR:
                    old  = _noise_floor * _MULTIPLIER
                    _noise_floor = max(
                        _MIN_NOISE_FLOOR, _noise_floor * _DECAY_FACTOR
                    )
                    print(Fore.CYAN + (
                        f"[EARS] Environment quieter — "
                        f"threshold eased: {old:.0f} -> "
                        f"{_noise_floor * _MULTIPLIER:.0f}"
                    ))
            _consecutive_timeouts = 0


def on_audio_captured():
    """Call this when real audio is captured. Resets timeout decay counter."""
    global _consecutive_timeouts
    with _timeout_lock:
        _consecutive_timeouts = 0


def _measure_rms(duration: float = 1.5) -> float:
    """
    Record ambient audio and return RMS.
    Returns 0.0 on failure.
    """
    import time
    import speech_recognition as sr

    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            audio = r.record(source, duration=duration)
            wav   = audio.get_wav_data()

        with wave.open(io.BytesIO(wav), 'rb') as wf:
            pcm = wf.readframes(wf.getnframes())

        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(arr ** 2)))

    except Exception as e:
        print(Fore.YELLOW + f"[EARS] RMS measurement error: {e}")
        return 0.0


def calibrate():
    """
    Measure ambient noise floor at startup.
    Retries up to 3 times if RMS is below valid minimum.
    Uses safe default if all retries fail.

    Call once at module load.
    """
    global _noise_samples, _noise_floor, _initial_floor
    import time

    print(Fore.CYAN + "[EARS] Calibrating — stay quiet for 1.5 seconds...")

    measured = 0.0
    for attempt in range(1, 4):
        measured = _measure_rms(duration=1.5)
        if measured >= _MIN_VALID_RMS:
            break
        print(Fore.YELLOW + (
            f"[EARS] Calibration attempt {attempt}: "
            f"RMS={measured:.0f} (too low — mic may not be ready)"
        ))
        time.sleep(1.0)

    if measured < _MIN_VALID_RMS:
        print(Fore.YELLOW + (
            f"[EARS] Calibration failed after 3 attempts — "
            f"using safe default: floor={_DEFAULT_FLOOR:.0f}, "
            f"threshold={_DEFAULT_FLOOR * _MULTIPLIER:.0f}"
        ))
        measured = _DEFAULT_FLOOR

    with _floor_lock:
        _noise_samples = [measured] * 5
        _noise_floor   = measured
        _initial_floor = measured

    print(Fore.GREEN + (
        f"[EARS] Calibration complete — "
        f"noise floor: {measured:.0f} | "
        f"voice threshold: {measured * _MULTIPLIER:.0f}"
    ))