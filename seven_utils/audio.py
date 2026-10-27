"""
seven_utils/audio.py
One PortAudio (PyAudio) instance per process, shared by everything that records or plays sound.

PortAudio's initialisation (pyaudio.PyAudio()) is not thread-safe. The microphone stream, the voice, the hearing
test and the snap detector each used to create their own, from different threads, and two of them starting at the
same moment crashed Seven with an access violation (0xC0000005) right as it began to speak. Now there is one,
created once under a lock and never torn down; streams are opened and closed through it, also under the lock.
"""
import threading

_lock = threading.RLock()
_pa = None


def pa():
    """The shared PyAudio instance."""
    global _pa
    with _lock:
        if _pa is None:
            import pyaudio
            _pa = pyaudio.PyAudio()
        return _pa


def open_stream(**kwargs):
    """pa().open(...), serialised with every other open and close."""
    with _lock:
        return pa().open(**kwargs)


def close_stream(stream) -> None:
    if stream is None:
        return
    with _lock:
        try:
            stream.stop_stream()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
