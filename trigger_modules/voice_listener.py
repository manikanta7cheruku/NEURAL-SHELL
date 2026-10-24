"""
trigger_modules/voice_listener.py
Always-on voice trigger phrase listener using Whisper tiny.en.

Runs in trigger_daemon.py — survives Seven UI close.
Only active if at least one trigger has a voice_phrase set.

Model loaded ONCE at class init. Never per-loop.
"""
import os
import json
import time
import sqlite3
import threading
from trigger_modules.config import TRIGGERS_DB
from trigger_modules.executor import execute_trigger

# Safe global import with fallback to prevent NameError inside run() loop
try:
    import speech_recognition as sr
except Exception:
    class DummySR:
        class WaitTimeoutError(Exception): pass
        class Microphone:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Recognizer:
            def listen(self, *args, **kwargs): raise DummySR.WaitTimeoutError()
    sr = DummySR()


class VoiceListener(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name="VoiceListener")
        self.stop_event  = threading.Event()
        self._model      = None
        self._phrase_map = {}

        self._load_phrase_map()
        self._load_model()

    def _load_phrase_map(self):
        """Load all triggers with voice_phrase from DB."""
        self._phrase_map = {}
        if not os.path.exists(TRIGGERS_DB):
            print("[VOICE TRIGGER] DB not found — no voice phrases loaded")
            return

        try:
            conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            rows = conn.execute(
                "SELECT * FROM triggers "
                "WHERE enabled = 1 AND voice_phrase IS NOT NULL "
                "AND TRIM(voice_phrase) != ''"
            ).fetchall()
            conn.close()

            for row in rows:
                d = dict(row)
                phrase = (d.get("voice_phrase") or "").lower().strip()
                if not phrase:
                    continue
                try:
                    d["action_data"] = json.loads(d.get("action_data") or "{}")
                except Exception:
                    d["action_data"] = {}
                d["enabled"] = bool(d.get("enabled", 1))
                d["silent"]  = bool(d.get("silent", 0))
                self._phrase_map[phrase] = d
                print(f"[VOICE TRIGGER] Phrase loaded: '{phrase}' "
                      f"-> '{d.get('name')}'")

            if self._phrase_map:
                print(f"[VOICE TRIGGER] {len(self._phrase_map)} "
                      f"voice phrases active")
            else:
                print("[VOICE TRIGGER] No voice phrases configured")

        except Exception as e:
            print(f"[VOICE TRIGGER] DB load error: {e}")

    def _load_model(self):
        """Load tiny.en Whisper model once at daemon start."""
        if not self._phrase_map:
            return

        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                "tiny.en",
                device="cpu",
                compute_type="int8"
            )
            print("[VOICE TRIGGER] tiny.en Whisper loaded for "
                  "phrase detection")
        except Exception as e:
            print(f"[VOICE TRIGGER] Whisper load failed: {e}")
            self._model = None

    def reload(self):
        """Reload phrase map from DB on trigger_reload.signal."""
        print("[VOICE TRIGGER] Reloading voice phrases...")
        self._load_phrase_map()
        if self._phrase_map and self._model is None:
            self._load_model()
        print(f"[VOICE TRIGGER] Reload complete: "
              f"{len(self._phrase_map)} phrases")

    @staticmethod
    def _seven_is_listening() -> bool:
        """True while the Seven app's backend is running: it hears voice-trigger phrases itself
        (brain layer 4.5h), and two processes on one microphone close each other's streams.
        /api/version exists only in the real backend, not in the offline tab listener on the same port."""
        import urllib.request
        try:
            with urllib.request.urlopen("http://127.0.0.1:7777/api/version", timeout=0.4) as r:
                return r.status == 200
        except Exception:
            return False

    def run(self):
        """
        Main listener loop. Only listens while the Seven app is closed, reopens the microphone with a growing pause
        when the stream drops, and never spins (a dropped stream once logged 19 MB of errors and kept the CPU busy).
        """
        time.sleep(10.0)
        print("[VOICE TRIGGER] Listener started — watching for phrases...")
        failures = 0
        mic = mic_ctx = None
        recognizer = sr.Recognizer() if hasattr(sr, "Recognizer") else None
        if recognizer is None:
            print("[VOICE TRIGGER] speech_recognition unavailable")
            return

        def _close():
            nonlocal mic, mic_ctx
            if mic is not None:
                try:
                    mic.__exit__(None, None, None)
                except Exception:
                    pass
            mic = mic_ctx = None

        try:
            while not self.stop_event.is_set():
                if not self._phrase_map or self._seven_is_listening():
                    _close()                                  # Seven handles phrases; give it the microphone
                    self.stop_event.wait(5.0)
                    continue

                if mic_ctx is None:
                    try:
                        mic = sr.Microphone()
                        mic_ctx = mic.__enter__()
                        failures = 0
                    except Exception as e:
                        failures += 1
                        wait = min(60.0, 2.0 ** min(failures, 6))
                        if failures in (1, 3, 6) or failures % 20 == 0:
                            print(f"[VOICE TRIGGER] Microphone unavailable ({e}); retrying in {wait:.0f}s")
                        _close()
                        self.stop_event.wait(wait)
                        continue

                try:
                    audio = recognizer.listen(mic_ctx, timeout=1.5, phrase_time_limit=4)
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    failures += 1
                    if failures in (1, 3, 6) or failures % 20 == 0:
                        print(f"[VOICE TRIGGER] Capture error ({e}); reopening the microphone")
                    _close()
                    self.stop_event.wait(min(60.0, 2.0 ** min(failures, 6)))
                    continue
                failures = 0

                if not self._model:
                    continue
                self._handle_audio(audio)
        finally:
            _close()
            print("[VOICE TRIGGER] Microphone released")

    def _handle_audio(self, audio):
        try:
            import io as _io
            result = self._model.transcribe(_io.BytesIO(audio.get_wav_data()), beam_size=1, language="en",
                                            no_speech_threshold=0.6, log_prob_threshold=-1.0, vad_filter=True)
            segments = list(result[0]) if isinstance(result, tuple) else list(result)
            text = "".join(s.text for s in segments).strip().lower()
        except Exception as e:
            print(f"[VOICE TRIGGER] Transcription error: {e}")
            return
        if not text or len(text) < 2:
            return
        clean = text.replace(".", "").replace(",", "").replace("?", "").strip()
        try:
            from rapidfuzz import fuzz as _rfuzz
        except ImportError:
            return
        best_phrase, best_score, best_trigger = None, 0, None
        for phrase, trigger in self._phrase_map.items():
            score = _rfuzz.partial_ratio(phrase, clean)
            if score >= 82 and score > best_score:
                best_phrase, best_score, best_trigger = phrase, score, trigger
        if best_trigger:
            print(f"[VOICE TRIGGER] Match: '{best_phrase}' in '{clean}' (score={best_score}) "
                  f"-> '{best_trigger.get('name')}'")
            threading.Thread(target=execute_trigger, args=(best_trigger,), daemon=True).start()
            self.stop_event.wait(2.0)                      # no double fire


    def stop(self):
        """Signal the listener loop to stop.""" 
        self.stop_event.set()
        print("[VOICE TRIGGER] Stop signal sent")