"""
trigger_modules/audio_listener.py
Audio trigger listener (snap/clap detection via DSP).
Only active if at least one trigger has an audio_pattern set.

Auto-adapts sensitivity based on detected mic type.
Auto-restarts detector when triggers or calibration change.
"""
import threading
import os

from trigger_modules.executor import execute_trigger


def _snap_sensitivity() -> str:
    """Settings, Voice, Snap sensitivity: relaxed, balanced (default) or strict."""
    try:
        import json
        p = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "config.json")
        with open(p, encoding="utf-8") as f:
            s = json.load(f).get("voice", {}).get("snap_sensitivity", "balanced")
        return s if s in ("relaxed", "balanced", "strict") else "balanced"
    except Exception:
        return "balanced"


class AudioListener:
    def __init__(self):
        self._detector  = None
        self._triggers  = []
        self._audio_map = {}
        self._running   = False
        self._current_sensitivity = None

    def reload(self, triggers):
        """
        Reload audio triggers from DB.
        Auto-stops detector if all snap triggers removed.
        Auto-restarts detector if calibration changed.
        """
        self._triggers = triggers
        old_count = len(self._audio_map)
        self._audio_map = {}
        for t in triggers:
            pattern = t.get("audio_pattern")
            if pattern:
                self._audio_map[pattern] = t

        new_count = len(self._audio_map)
        print(f"[AUDIO] Loaded {new_count} audio triggers (was {old_count})")

        # No triggers → stop detector, release mic
        if new_count == 0:
            if self._detector is not None:
                print("[AUDIO] No audio triggers — stopping detector, releasing mic")
                try:
                    self._detector.stop()
                except Exception as e:
                    print(f"[AUDIO] Stop failed: {e}")
                self._detector = None
                self._running = False
            return

        # Triggers present but detector not running → start
        if self._detector is None:
            print("[AUDIO] Audio triggers detected — starting detector")
            self.start()
            return

        # Detector already running → force restart so it picks up any
        # calibration changes from disk
        print("[AUDIO] Restarting detector to reload calibration")
        try:
            self._detector.stop()
        except Exception:
            pass
        self._detector = None
        self.start()

    def start(self):
        if not self._audio_map:
            print("[AUDIO] No audio triggers configured — skipping")
            return

        # Already running
        if self._detector is not None:
            return

        self._running = True

        try:
            from ears.audio_triggers import _find_best_input_device
            from ears.snap_detector import SnapDetector

            # The detector measures sounds against the room's own level, so one setting suits laptop mics and
            # headsets alike; the user can make it stricter or more relaxed in Settings.
            device_idx, mic_name = _find_best_input_device()
            sens = _snap_sensitivity()

            self._current_sensitivity = sens
            self._detector = SnapDetector(
                sensitivity=sens,
                device_index=device_idx
            )
            self._detector.on_pattern = self._on_pattern
            self._detector.start()
            print(f"[AUDIO] Listener started (sensitivity={sens}, mic={mic_name})")
        except Exception as e:
            print(f"[AUDIO] Listener failed: {e}")
            import traceback
            traceback.print_exc()
            self._detector = None
            self._running = False

    def stop(self):
        self._running = False
        if self._detector:
            try:
                self._detector.stop()
            except Exception:
                pass
        self._detector = None

    def suppress(self, ms=3000):
        if self._detector:
            self._detector.suppress(ms)

    def _on_pattern(self, count):
        """Called when the detector recognizes a tap pattern."""
        pattern_key = f"{count}_tap"
        trigger = self._audio_map.get(pattern_key)
        if trigger:
            print(f"[AUDIO] Pattern {pattern_key} -> {trigger['name']}")
            threading.Thread(
                target=execute_trigger,
                args=(trigger,),
                daemon=True
            ).start()
        else:
            print(f"[AUDIO] Pattern {pattern_key} — no trigger assigned "
                  f"(available: {list(self._audio_map.keys())})")