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

        # Gate 2: duration (min)
        if duration < _MIN_DURATION:
            return False, rms, (
                f"duration gate: {duration:.2f}s below minimum {_MIN_DURATION}s"
            )

        # Gate 2b: duration (max)
        # Real voice commands are under 12 seconds.
        # Longer clips are almost always ambient audio — ads, TV, music.
        # 15s is phrase_time_limit in listen() — clips near that limit
        # are almost never real commands.
        _MAX_DURATION = 12.0
        if duration > _MAX_DURATION:
            return False, rms, (
                f"duration gate: {duration:.2f}s above maximum {_MAX_DURATION}s "
                f"— likely ambient audio"
            )

        # Gate 3: crest factor
        crest = (peak / rms) if rms > 0 else 0.0
        if crest < _MIN_CREST:
            return False, rms, (
                f"crest gate: factor {crest:.2f} < {_MIN_CREST} — flat noise"
            )

        # Gate 4: SNR margin
        # If RMS only barely exceeds threshold, the clip is mostly noise
        # with a thin speech signal on top. Whisper will mishear this.
        # Require at least 1.5x the threshold to pass — meaningful margin.
        # Example: threshold=700, RMS must be >= 1050 to pass this gate.
        # This gate only activates when threshold > 400 (loud environment).
        # In quiet rooms the threshold is low enough that any speech passes.
        _SNR_MARGIN = 1.5
        if threshold > 400 and rms < threshold * _SNR_MARGIN:
            return False, rms, (
                f"SNR margin gate: RMS {rms:.0f} < "
                f"{threshold * _SNR_MARGIN:.0f} "
                f"(threshold {threshold:.0f} * {_SNR_MARGIN}) — "
                f"speech too close to noise floor for reliable transcription"
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