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
        self._triggers  = triggers
        self._audio_map = {}
        for t in triggers:
            pattern = t.get("audio_pattern")
            if pattern:
                self._audio_map[pattern] = t
        print(f"[AUDIO] Loaded {len(self._audio_map)} audio triggers")

    def start(self):
        if not self._audio_map:
            print("[AUDIO] No audio triggers configured — skipping")
            return

        self._running = True

        try:
            from ears.audio_triggers import TriggerDetector
            self._detector = TriggerDetector(sensitivity="high")
            self._detector.on_pattern = self._on_pattern
            self._detector.start()
            print("[AUDIO] Listener started (DSP mode)")
        except Exception as e:
            print(f"[AUDIO] Listener failed: {e}")

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