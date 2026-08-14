"""
ears/vad.py
Silero VAD wrapper for Seven.
Segments audio into speech/non-speech regions.
"""

import torch
import numpy as np
import io
import wave
from typing import List, Tuple

# Silero VAD model
_model, _utils = None, None

def _load_vad_model():
    global _model, _utils
    if _model is None:
        torch.hub.set_dir(".cache/torch/hub")
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        _model, _utils = model, utils
    return _model, _utils

def _read_wav_bytes(wav_bytes: bytes) -> Tuple[np.ndarray, int]:
    """Read WAV bytes into numpy array and sample rate."""
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        sr = wf.getframerate()
        pcm = wf.readframes(wf.getnframes())
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767.0
    return audio, sr

def segment_audio(wav_bytes: bytes) -> List[Tuple[float, float]]:
    """
    Segment audio into speech regions using Silero VAD.
    Returns list of (start_sec, end_sec) tuples.
    """
    audio, sr = _read_wav_bytes(wav_bytes)
    model, utils = _load_vad_model()
    (get_speech_timestamps, _, _, _, _) = utils

    speech_timestamps = get_speech_timestamps(
        audio,
        model,
        sampling_rate=sr,
        threshold=0.5,
        min_speech_duration_ms=200,
        min_silence_duration_ms=300,
        window_size_samples=512
    )

    segments = []
    for ts in speech_timestamps:
        start = ts['start'] / sr
        end = ts['end'] / sr
        segments.append((start, end))

    return segments