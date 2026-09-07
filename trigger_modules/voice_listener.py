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

    def run(self):
        """
        Main listener loop.
        Delays 10s at start to let pynput keyboard hook stabilize
        before opening any audio device (audio device access on
        Windows briefly stalls the OS message pump that pynput
        depends on, which can silently kill the keyboard hook).
        """
        # Single 10s delay — enough for pynput to register and stabilize
        time.sleep(10.0)
        print("[VOICE TRIGGER] Listener started — watching for phrases...")

        # Open microphone ONCE — hold open for daemon lifetime
        try:
            import speech_recognition as sr
            mic     = sr.Microphone()
            mic_ctx = mic.__enter__()
            recognizer = sr.Recognizer()
        except Exception as e:
            print(f"[VOICE TRIGGER] Microphone unavailable: {e}")
            return

        try:
            while not self.stop_event.is_set():

                # Capture audio chunk
                try:
                    audio = recognizer.listen(
                        mic_ctx,
                        timeout=1.5,
                        phrase_time_limit=4
                    )
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"[VOICE TRIGGER] Capture error: {e}")
                    time.sleep(0.5)
                    continue

                if not self._model:
                    continue

                # Transcribe in RAM
                try:
                    import io as _io
                    wav_bytes = audio.get_wav_data()
                    wav_buf   = _io.BytesIO(wav_bytes)

                    result = self._model.transcribe(
                        wav_buf,
                        beam_size=1,
                        language="en",
                        no_speech_threshold=0.6,
                        log_prob_threshold=-1.0,
                        vad_filter=True,
                    )

                    if isinstance(result, tuple):
                        segments = list(result[0])
                    else:
                        segments = list(result)

                    text = "".join(s.text for s in segments).strip().lower()

                except Exception as e:
                    print(f"[VOICE TRIGGER] Transcription error: {e}")
                    continue

                if not text or len(text) < 2:
                    continue

                # Clean punctuation for matching
                clean = text.replace(".", "").replace(",", "") \
                              .replace("?", "").strip()

                # Match against all configured phrases
                best_phrase  = None
                best_score   = 0
                best_trigger = None

                try:
                    from rapidfuzz import fuzz as _rfuzz
                except ImportError:
                    continue

                for phrase, trigger in self._phrase_map.items():
                    score = _rfuzz.partial_ratio(phrase, clean)
                    if score >= 82 and score > best_score:
                        best_score   = score
                        best_phrase  = phrase
                        best_trigger = trigger

                if best_trigger:
                    print(
                        f"[VOICE TRIGGER] Match: '{best_phrase}' "
                        f"in '{clean}' (score={best_score}) "
                        f"-> '{best_trigger.get('name')}'"
                    )
                    threading.Thread(
                        target=execute_trigger,
                        args=(best_trigger,),
                        daemon=True
                    ).start()

                    # Brief pause after firing — prevents double-fire
                    time.sleep(2.0)

        finally:
            try:
                mic.__exit__(None, None, None)
                print("[VOICE TRIGGER] Microphone released")
            except Exception:
                pass

    def stop(self):
        """Signal the listener loop to stop."""
        self.stop_event.set()
        print("[VOICE TRIGGER] Stop signal sent")