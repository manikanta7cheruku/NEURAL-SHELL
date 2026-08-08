"""
ears/signal_gates.py
Seven — Pre-Whisper signal quality gates.

Three gates must all pass before audio is sent to Whisper.
These run in microseconds — no ML, pure math.

Gate 1: RMS energy
    Is there enough total sound energy to be speech?
    Rejects near-silence, very quiet room noise.

Gate 2: Duration
    Is the clip long enough to contain at least one word?
    Rejects clicks, pops, single noise bursts.

Gate 3: Crest factor (peak / RMS)
    Is the waveform shaped like speech?
    Speech is spiky: consonants create sharp peaks vs average energy.
    Noise (fan, AC, hum) is flat: peak is close to average energy.
    Crest factor < 2.2 = flat noise = reject.
"""

import io
import wave
import numpy as np
from colorama import Fore

_MIN_CREST    = 2.2
_MIN_DURATION = 0.4  # seconds


def check(wav_data: bytes, threshold: float) -> tuple:
    """
    Run all three signal quality gates on raw WAV bytes.

    Args:
        wav_data:  raw WAV bytes from SpeechRecognition
        threshold: current adaptive noise threshold (RMS units)

    Returns:
        (passed: bool, rms: float, reason: str)
        passed=True  — all gates passed, send to Whisper
        passed=False — rejected, update noise floor and discard
    """
    try:
        with wave.open(io.BytesIO(wav_data), 'rb') as wf:
            sample_rate = wf.getframerate()
            pcm_raw     = wf.readframes(wf.getnframes())

        audio_np = np.frombuffer(pcm_raw, dtype=np.int16).astype(np.float32)
        rms      = float(np.sqrt(np.mean(audio_np ** 2)))
        peak     = float(np.max(np.abs(audio_np)))
        duration = len(audio_np) / float(sample_rate)

        # Gate 1: energy
        if rms < threshold:
            return False, rms, (
                f"energy gate: RMS {rms:.0f} < threshold {threshold:.0f}"
            )

        # Gate 2: duration
        if dur < _MIN_DURATION:
            return False, rms, (
                f"duration gate: {dur:.2f}s below minimum {_MIN_DURATION}s"
            )

        # Maximum duration gate
        # Real voice commands are under 12 seconds.
        # Longer clips are almost always ambient audio — ads, TV, music.
        # 15s is phrase_time_limit in listen() — clips near that limit
        # are almost never real commands.
        _MAX_DURATION = 12.0
        if dur > _MAX_DURATION:
            return False, rms, (
                f"duration gate: {dur:.2f}s above maximum {_MAX_DURATION}s "
                f"— likely ambient audio"
            )

        # Gate 3: crest factor
        crest = (peak / rms) if rms > 0 else 0.0
        if crest < _MIN_CREST:
            return False, rms, (
                f"crest gate: factor {crest:.2f} < {_MIN_CREST} — flat noise"
            )

        print(Fore.CYAN + (
            f"[EARS] Signal OK — "
            f"RMS={rms:.0f} crest={crest:.2f} "
            f"dur={duration:.2f}s threshold={threshold:.0f}"
        ))
        return True, rms, "ok"

    except Exception as e:
        # If signal check fails, let Whisper decide
        print(Fore.YELLOW + f"[EARS] Signal gate error: {e} — forwarding to Whisper")
        return True, 0.0, "check_failed"