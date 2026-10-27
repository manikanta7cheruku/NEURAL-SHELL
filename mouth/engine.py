"""
mouth/engine.py
Seven's voice, kept warm inside the app.

The old path started a Python process and then piper.exe for every sentence, loading the voice from scratch each
time, and only began once the whole reply was ready. Here the natural voice (Kokoro, fp16, about 3.5x faster than
real time on an 8-core laptop CPU) loads once, and speaking is a small pipeline:

    sentences ─► synthesis thread (stays one sentence ahead) ─► playback (PyAudio, stoppable every ~40 ms)

so the first words play about half a second after the first sentence exists, and interrupt() is silence at once.

The engine also remembers what it said and when it stopped, so the ears can ignore Seven hearing itself
(ears/core.py), and it can play a short chime the moment Seven hears its name.
"""
import os
import queue
import threading
import time

import numpy as np

from mouth import tone, voices

_SR = 24000
_CHUNK = 1024                      # ~43 ms of audio between checks for interrupt()


class Engine:
    def __init__(self):
        self._kokoro = None
        self._load_lock = threading.Lock()
        self._say_lock = threading.Lock()
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self._pa = None
        self._said = []            # (time, text) of recent sentences, for echo rejection
        self._ended_at = 0.0

    # ── model ────────────────────────────────────────────────────────────
    def available(self) -> bool:
        return voices.kokoro_ready()

    def _model(self):
        if self._kokoro is None:
            with self._load_lock:
                if self._kokoro is None:
                    import onnxruntime as ort
                    from kokoro_onnx import Kokoro
                    d = voices.models_dir()
                    opts = ort.SessionOptions()
                    opts.intra_op_num_threads = max(2, min(8, (os.cpu_count() or 4) // 2))
                    opts.inter_op_num_threads = 1
                    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    session = ort.InferenceSession(os.path.join(d, "kokoro-v1.0.fp16.onnx"), opts,
                                                   providers=["CPUExecutionProvider"])
                    self._kokoro = Kokoro.from_session(session, os.path.join(d, "voices-v1.0.bin"))
                    self._kokoro.create("Hi.", voice=voices.DEFAULT_VOICE, lang="en-us")   # first run compiles kernels
        return self._kokoro

    def warm(self):
        """Load the voice in the background at startup, so the first reply isn't the slow one."""
        if self.available():
            threading.Thread(target=self._safe_warm, daemon=True, name="VoiceWarmup").start()

    def _safe_warm(self):
        try:
            t = time.time()
            self._model()
            print(f"[MOUTH] Natural voice ready in {time.time() - t:.1f}s")
        except Exception as e:
            print(f"[MOUTH] Natural voice failed to load: {e}")

    def synth(self, text: str, voice: str, speed: float) -> np.ndarray:
        audio, _ = self._model().create(text, voice=voice, speed=speed, lang="en-gb" if voice[:1] == "b" else "en-us")
        return np.clip(audio, -1.0, 1.0).astype(np.float32)

    # ── playback ─────────────────────────────────────────────────────────
    def _out(self):
        import pyaudio
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        return self._pa.open(format=pyaudio.paInt16, channels=1, rate=_SR, output=True, frames_per_buffer=_CHUNK)

    def _play(self, stream, audio: np.ndarray, fade_in: bool = False) -> bool:
        pcm = (audio * 32767).astype(np.int16)
        if fade_in and len(pcm) > 240:                          # no click at the very start
            pcm[:240] = (pcm[:240] * np.linspace(0, 1, 240)).astype(np.int16)
        for i in range(0, len(pcm), _CHUNK):
            if self._stop.is_set():
                return False
            stream.write(pcm[i:i + _CHUNK].tobytes())
        return True

    # ── speaking ─────────────────────────────────────────────────────────
    def say(self, sentences, voice: str = None, speed: float = 1.0, on_sentence=None) -> bool:
        """
        Speak an iterable of sentences (a list, or a generator that is still being written). Returns False if
        interrupted. on_sentence(text) is called as each one starts playing.
        """
        voice = voice if voices.is_natural(voice or "") else voices.DEFAULT_VOICE
        with self._say_lock:
            self._stop.clear()
            self._speaking.set()
            ready = queue.Queue(maxsize=2)

            def produce():
                try:
                    for s in sentences:
                        for part in tone.chunks(s):
                            if self._stop.is_set():
                                return
                            t = tone.of(part)
                            ready.put((part, self.synth(part, voice, speed * t["speed"]), t["pause"]))
                except Exception as e:
                    print(f"[MOUTH] Synthesis error: {e}")
                finally:
                    ready.put(None)

            threading.Thread(target=produce, daemon=True, name="VoiceSynth").start()
            stream = None
            completed = True
            first = True
            try:
                stream = self._out()
                while True:
                    item = ready.get()
                    if item is None:
                        break
                    text, audio, pause = item
                    self._said.append((time.time(), text))
                    self._said = self._said[-12:]
                    if on_sentence:
                        try:
                            on_sentence(text)
                        except Exception:
                            pass
                    if not self._play(stream, audio, fade_in=first):
                        completed = False
                        break
                    first = False
                    self._play(stream, np.zeros(int(_SR * pause), dtype=np.float32))
            except Exception as e:
                print(f"[MOUTH] Playback error: {e}")
            finally:
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                if self._stop.is_set():
                    completed = False
                    while not ready.empty():                       # let a waiting producer finish
                        try:
                            ready.get_nowait()
                        except Exception:
                            break
                self._speaking.clear()
                self._ended_at = time.time()
            return completed

    def stop(self) -> bool:
        was = self._speaking.is_set()
        self._stop.set()
        return was

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    # ── for the ears ─────────────────────────────────────────────────────
    def recently_said(self, within: float = 8.0) -> list:
        now = time.time()
        return [t for at, t in self._said if now - at < within]

    def ended_at(self) -> float:
        return self._ended_at

    def chime(self, kind: str = "wake"):
        """A short, soft two-note sound: 'wake' (heard you), 'done', 'error'. Never blocks."""
        notes = {"wake": [(880, 0.07), (1318.5, 0.11)], "done": [(1046.5, 0.08), (1568, 0.12)],
                 "error": [(392, 0.12), (330, 0.16)]}.get(kind, [(880, 0.1)])

        def play():
            try:
                parts = []
                for f, d in notes:
                    t = np.arange(int(_SR * d)) / _SR
                    env = np.minimum(1, t / 0.008) * np.exp(-t / (d * 0.45))
                    parts.append(0.18 * np.sin(2 * np.pi * f * t) * env)
                s = self._out()
                s.write((np.concatenate(parts) * 32767).astype(np.int16).tobytes())
                s.stop_stream()
                s.close()
            except Exception:
                pass
        threading.Thread(target=play, daemon=True, name="Chime").start()


ENGINE = Engine()
