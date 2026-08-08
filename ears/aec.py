"""
ears/aec.py
Seven — Acoustic Echo Cancellation (AEC)

Prevents Seven's own TTS voice from triggering the microphone.

HOW IT WORKS:
    1. Captures system audio output (what speakers are playing) via
       Windows WASAPI loopback — this is the reference signal.
    2. When microphone audio is captured, subtract the reference signal
       from it using normalized cross-correlation alignment + subtraction.
    3. Microphone audio with Seven's voice removed goes to Whisper.

REQUIREMENTS:
    pyaudiowpatch  — WASAPI loopback support for Python
    Install: venv\Scripts\pip install pyaudiowpatch

WHY NOT webrtcvad / webrtc-audio-processing:
    webrtcvad is VAD only — it detects speech but does not remove echo.
    webrtc-audio-processing requires C++ compilation on Windows.
    pyaudiowpatch is pure Python install, no compiler needed.

OFFLINE: Yes. 100% local. No cloud calls.

LIMITATIONS:
    - Only works on Windows (WASAPI loopback is Windows-only).
    - Requires stereo or loopback-capable audio device.
    - Does not work with USB audio devices that lack loopback support.
    - PTT mode is still the most reliable solution for all setups.
"""

import threading
import numpy as np
from colorama import Fore

_loopback_buffer       = np.array([], dtype=np.float32)
_loopback_lock         = threading.Lock()
_loopback_thread       = None
_loopback_running      = False
_loopback_device_found = False   # True only when a real loopback device was opened
_SAMPLE_RATE           = 16000
_CHANNELS              = 1


def _float32_from_bytes(data: bytes, channels: int) -> np.ndarray:
    """Convert raw PCM bytes to float32 mono."""
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767.0
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    return arr


def _loopback_capture_thread():
    """
    Capture system speaker output (loopback) continuously.
    Stores in ring buffer for AEC subtraction.
    """
    global _loopback_running, _loopback_buffer

    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        print(Fore.YELLOW + (
            "[AEC] pyaudiowpatch not installed — AEC disabled.\n"
            "      Run: venv\\Scripts\\pip install pyaudiowpatch"
        ))
        return

    try:
        pa = pyaudio.PyAudio()

        # Find default loopback device
        loopback_device = None
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("isLoopbackDevice", False):
                loopback_device = info
                break

        if loopback_device is None:
            print(Fore.YELLOW + "[AEC] No loopback device found — AEC disabled")
            pa.terminate()
            global _loopback_running
            _loopback_running = False
            return

        device_rate    = int(loopback_device["defaultSampleRate"])
        device_channels = int(loopback_device["maxInputChannels"])

        print(Fore.CYAN + (
            f"[AEC] Loopback device: {loopback_device['name']} "
            f"({device_rate}Hz, {device_channels}ch)"
        ))

        stream = pa.open(
            format=pyaudio.paInt16,
            channels=device_channels,
            rate=device_rate,
            input=True,
            input_device_index=loopback_device["index"],
            frames_per_buffer=1024,
        )

        global _loopback_device_found
        _loopback_device_found = True
        print(Fore.GREEN + "[AEC] Loopback capture started")

        while _loopback_running:
            try:
                raw  = stream.read(1024, exception_on_overflow=False)
                mono = _float32_from_bytes(raw, device_channels)

                with _loopback_lock:
                    # Keep last 2 seconds of reference signal
                    max_samples = device_rate * 2
                    combined    = np.concatenate([_loopback_buffer, mono])
                    _loopback_buffer = combined[-max_samples:]

            except Exception:
                pass

        stream.stop_stream()
        stream.close()
        pa.terminate()

    except Exception as e:
        print(Fore.YELLOW + f"[AEC] Loopback capture error: {e}")


def start():
    """Start AEC loopback capture. Call once at startup."""
    global _loopback_thread, _loopback_running

    try:
        import pyaudiowpatch
    except ImportError:
        print(Fore.YELLOW + (
            "[AEC] pyaudiowpatch not installed — AEC not available.\n"
            "      Install with: venv\\Scripts\\pip install pyaudiowpatch\n"
            "      AEC prevents Seven's own voice from triggering the mic.\n"
            "      Without it: use PTT mode (hold Shift) to avoid false triggers."
        ))
        return

    _loopback_running = True
    _loopback_thread  = threading.Thread(
        target=_loopback_capture_thread,
        daemon=True,
        name="AECLoopback"
    )
    _loopback_thread.start()


def stop():
    """Stop AEC loopback capture."""
    global _loopback_running
    _loopback_running = False


def apply(mic_audio: np.ndarray, mic_rate: int) -> np.ndarray:
    """
    Apply AEC to microphone audio.

    Subtracts the reference (loopback) signal from microphone audio
    using normalized cross-correlation to align the signals first.

    Args:
        mic_audio: float32 numpy array, microphone audio
        mic_rate:  sample rate of mic_audio

    Returns:
        float32 numpy array with echo reduced
    """
    with _loopback_lock:
        if len(_loopback_buffer) == 0:
            return mic_audio
        ref = _loopback_buffer.copy()

    if len(ref) == 0:
        return mic_audio

    mic_len = len(mic_audio)
    ref_len = len(ref)

    if ref_len < mic_len:
        # Reference is shorter than mic — pad with zeros
        ref = np.pad(ref, (0, mic_len - ref_len))
    else:
        # Use only the most recent portion of reference
        ref = ref[-mic_len:]

    # Normalize both signals to same scale
    mic_rms = float(np.sqrt(np.mean(mic_audio ** 2)))
    ref_rms = float(np.sqrt(np.mean(ref ** 2)))

    if ref_rms < 1e-6:
        # Reference is silent — nothing to subtract
        return mic_audio

    if mic_rms < 1e-6:
        return mic_audio

    # Scale reference to match microphone level
    ref_scaled = ref * (mic_rms / ref_rms)

    # Cross-correlation for time alignment
    # Find the delay between mic and reference signal
    corr  = np.correlate(mic_audio, ref_scaled, mode='full')
    delay = int(np.argmax(np.abs(corr)) - (len(mic_audio) - 1))
    # Clamp to 800 samples = 50ms at 16kHz
    # Real speaker-to-microphone delay in a room: 10-50ms
    # Old clamp of 100 samples (6ms) was too small — AEC never aligned correctly
    delay = max(-800, min(800, delay))

    # Shift reference to align with mic
    if delay > 0:
        ref_aligned = np.pad(ref_scaled, (delay, 0))[:mic_len]
    elif delay < 0:
        ref_aligned = ref_scaled[-delay:][:mic_len]
        if len(ref_aligned) < mic_len:
            ref_aligned = np.pad(ref_aligned, (0, mic_len - len(ref_aligned)))
    else:
        ref_aligned = ref_scaled[:mic_len]

    # Subtract reference from mic
    # Subtract only a fraction (0.7) to avoid over-subtraction artifacts
    result = mic_audio - (ref_aligned * 0.7)

    # Clip to valid range
    result = np.clip(result, -1.0, 1.0)

    return result.astype(np.float32)


def is_available() -> bool:
    """
    Check if AEC loopback is running AND a device was found.
    _loopback_device_found is set True only after a real loopback
    device was opened — avoids the race window where the thread
    has started but not yet confirmed a device exists.
    """
    return (
        _loopback_device_found and
        _loopback_thread is not None and
        _loopback_thread.is_alive()
    )