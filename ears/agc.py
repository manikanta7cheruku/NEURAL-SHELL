"""
ears/agc.py
Seven — Automatic Gain Control (AGC)

Normalizes microphone audio volume before Whisper transcription.
Prevents whispered speech from being too quiet and shouted speech
from clipping.

HOW IT WORKS:
    Target RMS: 0.1 (10% of full scale float32)
    If mic audio RMS is below target: amplify.
    If mic audio RMS is above target: attenuate.
    Max gain: 20x (prevents extreme amplification of pure silence).
    Min gain: 0.1x (prevents extreme attenuation of very loud input).

WHY THIS MATTERS:
    Whisper performance degrades on very quiet audio.
    A user whispering may produce RMS of 0.005 — too quiet for good STT.
    AGC brings that to 0.1 — Whisper hears it clearly.
    A user shouting may produce RMS of 0.8 — clipping artifacts.
    AGC brings that to 0.1 — Whisper gets clean audio.

OFFLINE: Yes. Pure numpy. No external dependencies.
"""

import numpy as np
from colorama import Fore

_TARGET_RMS      = 0.08   # target output RMS level
_MAX_GAIN        = 3.0    # conservative — never amplify more than 3x
_MIN_GAIN        = 0.5    # never attenuate more than 2x
_NOISE_FLOOR_AGC = 0.02   # below this RMS — do not touch, it is noise

# Smoothed gain — prevents sudden volume jumps between clips
_smoothed_gain = 1.0
_SMOOTH_FACTOR = 0.3   # how quickly gain adapts (0=no adapt, 1=instant)


def apply(audio: np.ndarray) -> np.ndarray:
    """
    Conservative AGC.

    Rules:
        Below 0.02 RMS: do nothing — that is noise, not speech.
        Already in acceptable range (0.04-0.16): do nothing.
        Outside range: gentle correction only, max 3x gain.

    This means AGC only activates for:
        Very loud input (shouting): gentle attenuation.
        Reasonably quiet speech: gentle amplification.
    It never activates for near-silence.
    """
    global _smoothed_gain

    if len(audio) == 0:
        return audio

    rms = float(np.sqrt(np.mean(audio ** 2)))

    # Hard floor — below this is noise, not speech
    # Do not amplify noise. Return untouched.
    if rms < _NOISE_FLOOR_AGC:
        _smoothed_gain = 1.0
        return audio

    # If already in acceptable range, skip correction entirely
    # Acceptable band: 50% to 200% of target RMS
    lower = _TARGET_RMS * 0.5   # 0.04
    upper = _TARGET_RMS * 2.0   # 0.16
    if lower <= rms <= upper:
        _smoothed_gain = 1.0
        return audio

    # Outside acceptable range — apply gentle correction
    raw_gain = _TARGET_RMS / rms
    raw_gain = max(_MIN_GAIN, min(_MAX_GAIN, raw_gain))

    # Smooth gain transitions
    _smoothed_gain = (
        _SMOOTH_FACTOR * raw_gain +
        (1.0 - _SMOOTH_FACTOR) * _smoothed_gain
    )

    applied = np.clip(audio * _smoothed_gain, -1.0, 1.0)
    output_rms = float(np.sqrt(np.mean(applied ** 2)))

    # Only print when gain correction is significant (>20% change)
    if abs(_smoothed_gain - 1.0) > 0.2:
        print(Fore.CYAN + (
            f"[AGC] gain={_smoothed_gain:.2f}x "
            f"input={rms:.4f} output={output_rms:.4f}"
        ))

    return applied.astype(np.float32)


def apply_to_wav_bytes(wav_bytes: bytes) -> bytes:
    """
    Apply AGC to raw WAV bytes.
    Returns WAV bytes with normalized volume.
    Used to normalize before signal quality check.
    """
    import io
    import wave
    import struct

    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            sr         = wf.getframerate()
            channels   = wf.getnchannels()
            sampwidth  = wf.getsampwidth()
            pcm_bytes  = wf.readframes(wf.getnframes())

        # Convert to float32
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        audio = audio / 32767.0

        # Handle stereo — convert to mono for processing, back to stereo
        if channels == 2:
            stereo = audio.reshape(-1, 2)
            mono   = stereo.mean(axis=1)

            mono_rms = float(np.sqrt(np.mean(mono ** 2)))
            if mono_rms < _NOISE_FLOOR_AGC:
                # Below noise floor — return untouched (same logic as apply())
                audio_out = audio
            else:
                # Compute the same gain apply() would use, reuse it on stereo
                # Do NOT call apply() and then reverse-engineer the gain —
                # that circular calculation gave gain ≈ 1.0 always.
                lower = _TARGET_RMS * 0.5
                upper = _TARGET_RMS * 2.0
                if lower <= mono_rms <= upper:
                    audio_out = audio
                else:
                    raw_gain  = _TARGET_RMS / mono_rms
                    raw_gain  = max(_MIN_GAIN, min(_MAX_GAIN, raw_gain))
                    normalized_stereo = np.clip(stereo * raw_gain, -1.0, 1.0)
                    audio_out = normalized_stereo.flatten()
        else:
            audio_out = apply(audio)

        # Convert back to int16 PCM
        pcm_out = (audio_out * 32767.0).astype(np.int16).tobytes()

        # Pack back into WAV
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf_out:
            wf_out.setnchannels(channels)
            wf_out.setsampwidth(sampwidth)
            wf_out.setframerate(sr)
            wf_out.writeframes(pcm_out)

        return buf.getvalue()

    except Exception as e:
        print(Fore.YELLOW + f"[AGC] Processing error: {e} — returning original")
        return wav_bytes


def reset():
    """Reset smoothed gain to neutral. Call if context changes (new speaker, etc.)"""
    global _smoothed_gain
    _smoothed_gain = 1.0