"""
trigger_modules/audio_listener.py
Audio trigger listener (snap/clap detection via DSP or YAMNet).
Only active if at least one trigger has an audio_pattern set.
"""
import threading

from trigger_modules.executor import execute_trigger


class AudioListener:
    def __init__(self):
        self._detector  = None
        self._triggers  = []
        self._audio_map = {}
        self._running   = False

    def reload(self, triggers):
        """
        Reload audio triggers from DB.
        Auto-starts detector if triggers appear, stops it if all removed.
        """
        self._triggers  = triggers
        old_count = len(self._audio_map)
        self._audio_map = {}
        for t in triggers:
            pattern = t.get("audio_pattern")
            if pattern:
                self._audio_map[pattern] = t

        new_count = len(self._audio_map)
        print(f"[AUDIO] Loaded {new_count} audio triggers (was {old_count})")

        # Auto-stop detector if all audio triggers removed
        if new_count == 0 and self._detector is not None:
            print("[AUDIO] No audio triggers remain — stopping detector to release mic")
            try:
                self._detector.stop()
            except Exception as e:
                print(f"[AUDIO] Stop failed: {e}")
            self._detector = None
            self._running = False
            return

        # Auto-start detector if new audio triggers appeared
        if new_count > 0 and self._detector is None:
            print("[AUDIO] Audio triggers detected — starting detector")
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
            from ears.audio_triggers import TriggerDetector
            self._detector = TriggerDetector(sensitivity="medium")
            self._detector.on_pattern = self._on_pattern
            self._detector.start()
            print("[AUDIO] Listener started (signature classifier mode)")
        except Exception as e:
            print(f"[AUDIO] Listener failed: {e}")
            self._detector = None
            self._running = False

    def stop(self):
        self._running = False
        if self._detector:
            self._detector.stop()

    def suppress(self, ms=3000):
        if self._detector:
            self._detector.suppress(ms)

    def _on_pattern(self, count):
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
            print(f"[AUDIO] Pattern {pattern_key} — no trigger assigned")