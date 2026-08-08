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
_MULTIPLIER          = 1.8   # threshold = floor * MULTIPLIER
#                            # Reduced from 2.2 — at 2.2, a floor of 300
#                            # gives threshold=660, normal speech at 800
#                            # barely passes. 1.8 gives threshold=540,
#                            # normal speech passes with margin.
_WINDOW              = 20    # rolling average window
_NOISE_FLOOR_CAP     = 400   # reduced from 500
#                            # At 500 * 2.2 = 1100 threshold, only loud
#                            # close-range speech passes. 400 * 1.8 = 720,
#                            # which is achievable by normal speech in a
#                            # moderately loud room.
_MIN_NOISE_FLOOR     = 80.0  # reduced from 150
#                            # 150 was too conservative — in a quiet room
#                            # the floor is 60-100, so 150 minimum was
#                            # artificially raising the threshold.
_MIN_VALID_RMS       = 20.0  # below this = mic not ready
_DEFAULT_FLOOR       = 150.0 # safe default if calibration fails
#                            # reduced from 200 — 200 * 1.8 = 360 threshold
#                            # which is achievable in a quiet room

def get_min_noise_floor() -> float:
    """Public accessor for minimum noise floor. Use instead of _MIN_NOISE_FLOOR directly."""
    return _MIN_NOISE_FLOOR


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
    Hard maximum: 700. Above this, normal speech cannot reliably
    trigger Seven. If environment is louder than this, PTT mode
    is the correct solution — no threshold tuning fixes a loud room.
    """
    with _floor_lock:
        floor = max(_noise_floor, _MIN_NOISE_FLOOR)
    raw = floor * _MULTIPLIER
    # Hard ceiling — never return a threshold so high that normal
    # speech at 0.5m distance (RMS ~1000-2000) cannot pass.
    return min(raw, 700.0)


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

    Lock order: always acquire _floor_lock first, then _timeout_lock.
    Never hold one while acquiring the other in reverse order.
    Here we read/write _noise_floor outside _timeout_lock to avoid
    nested acquisition deadlock risk.
    """
    global _consecutive_timeouts, _noise_floor

    # Step 1: check and increment timeout counter under its own lock
    should_decay = False
    with _timeout_lock:
        _consecutive_timeouts += 1
        if _consecutive_timeouts >= _DECAY_AFTER:
            should_decay          = True
            _consecutive_timeouts = 0

    # Step 2: apply decay under floor lock only — no nesting
    if should_decay:
        with _floor_lock:
            if _noise_floor > _MIN_NOISE_FLOOR:
                old          = _noise_floor * _MULTIPLIER
                _noise_floor = max(
                    _MIN_NOISE_FLOOR, _noise_floor * _DECAY_FACTOR
                )
                print(Fore.CYAN + (
                    f"[EARS] Environment quieter — "
                    f"threshold eased: {old:.0f} -> "
                    f"{_noise_floor * _MULTIPLIER:.0f}"
                ))


def on_audio_captured():
    """Call this when real audio is captured. Resets timeout decay counter."""
    global _consecutive_timeouts
    with _timeout_lock:
        _consecutive_timeouts = 0


def _measure_rms(duration: float = 1.5) -> float:
    """
    Record ambient audio and return RMS.
    Returns 0.0 on failure.
    Handles device-busy errors from concurrent audio listeners.
    """
    import speech_recognition as sr

    try:
        r = sr.Recognizer()
        # Do not call adjust_for_ambient_noise — it interferes with our
        # own calibration and can cause the returned audio to be silence
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

    Strategy:
        Take 3 measurements of 1.0s each.
        Use the MINIMUM valid measurement.
        A single noisy event (TV ad, phone alert) should not permanently
        raise the threshold — minimum gives the true quiet floor.

    Hard cap:
        If measured floor exceeds 1000, cap at 500.
        Reason: if room is extremely loud during calibration, a cap
        prevents threshold from becoming so high Seven never triggers.
        User will need to re-calibrate in a quieter moment (restart Seven).

    Fallback:
        If all measurements are below MIN_VALID_RMS (mic not ready):
        use DEFAULT_FLOOR = 200.
    """
    global _noise_samples, _noise_floor, _initial_floor
    import time

    print(Fore.CYAN + (
        "[EARS] Calibrating — 3 samples, using minimum..."
    ))

    measurements = []
    for attempt in range(1, 4):
        m = _measure_rms(duration=1.0)
        if m >= _MIN_VALID_RMS:
            measurements.append(m)
            print(Fore.CYAN + (
                f"[EARS] Calibration sample {attempt}: {m:.0f}"
            ))
        else:
            print(Fore.YELLOW + (
                f"[EARS] Calibration sample {attempt}: {m:.0f} "
                f"(below minimum — mic may not be ready)"
            ))
        if attempt < 3:
            time.sleep(0.8)

    if not measurements:
        print(Fore.YELLOW + (
            f"[EARS] No valid calibration samples — "
            f"using default: floor={_DEFAULT_FLOOR:.0f} "
            f"threshold={_DEFAULT_FLOOR * _MULTIPLIER:.0f}"
        ))
        measured = _DEFAULT_FLOOR
    else:
        measured = min(measurements)

        # Hard cap — if environment is very loud during calibration,
        # cap the floor so Seven can still hear normal speech.
        # Without this cap: threshold can reach 1000+, nothing triggers.
        # New cap: 350 (was 500). At 350 * 1.8 = 630 threshold, normal
        # speech at 800-2000 RMS still passes comfortably.
        if measured > 350:
            print(Fore.YELLOW + (
                f"[EARS] Measured floor {measured:.0f} is high "
                f"(loud environment during calibration). "
                f"Capping at 350 — threshold will be {350 * _MULTIPLIER:.0f}. "
                f"If Seven mishears, reduce background noise or use PTT mode."
            ))
            measured = 350

        print(Fore.GREEN + (
            f"[EARS] Calibration complete — "
            f"floor: {measured:.0f} | "
            f"threshold: {measured * _MULTIPLIER:.0f}"
        ))

    with _floor_lock:
        _noise_samples = [measured] * 5
        _noise_floor   = measured
        _initial_floor = measured
    # Single completion message — the earlier branch already printed one
    # when measurements succeeded; this prints only for the default-floor path