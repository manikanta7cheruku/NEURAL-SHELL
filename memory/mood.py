"""
memory/mood.py

Seven's emotional state, driven by the conversation.

Mood is a float from -1.0 (frustrated) to +1.0 (excited) that decays toward
neutral. The label feeds a short, positively framed line in the system prompt
(prompt_builder), so tone shifts subtly instead of by scripted outbursts.

BUGS FIXED:
    - The state file used a path relative to the working directory
      ("./seven_data/mood_state.json"). In the packaged app the working
      directory is not writable, so mood silently never persisted. It now
      lives in %APPDATA%/SEVEN.
    - The state was written to disk on every single message. Writes are now
      throttled.
    - Signals matched as substrings ("hi" inside "this"). They now match whole
      words.
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime

_log = logging.getLogger("seven.mood")


def _state_path() -> str:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "SEVEN", "mood_state.json")


MOOD_PATH = _state_path()
_SAVE_INTERVAL_SECONDS = 20.0


class MoodEngine:
    """Seven's emotional state tracker."""

    POSITIVE_SIGNALS = {
        "love": 0.15, "amazing": 0.15, "perfect": 0.15, "brilliant": 0.15,
        "thanks": 0.10, "thank you": 0.10, "great": 0.10, "awesome": 0.10,
        "good job": 0.10, "well done": 0.10, "nice": 0.08, "cool": 0.08,
        "good": 0.05, "please": 0.03, "hello": 0.05, "hey": 0.04, "hi": 0.04,
        "morning": 0.05,
    }
    NEGATIVE_SIGNALS = {
        "stupid": -0.15, "useless": -0.15, "hate": -0.15, "terrible": -0.15,
        "wrong": -0.10, "bad": -0.10, "broken": -0.10, "annoying": -0.10,
        "shut up": -0.12, "idiot": -0.12, "stop": -0.05,
    }
    MOOD_LABELS = [
        (-1.0, -0.6, "frustrated"), (-0.6, -0.3, "down"), (-0.3, -0.1, "slightly_off"),
        (-0.1, 0.1, "neutral"), (0.1, 0.3, "content"), (0.3, 0.6, "happy"),
        (0.6, 1.01, "excited"),
    ]

    def __init__(self):
        self.mood = 0.0
        self.interaction_count = 0
        self.history = []
        self._lock = threading.Lock()
        self._last_save = 0.0
        self._load_state()

    def _load_state(self) -> None:
        try:
            if os.path.exists(MOOD_PATH):
                with open(MOOD_PATH, "r", encoding="utf-8") as fh:
                    state = json.load(fh)
                self.mood = float(state.get("mood", 0.0)) * 0.7  # time passed between sessions
                self.interaction_count = int(state.get("interaction_count", 0))
        except Exception as exc:
            _log.debug("mood load failed: %s", exc)
            self.mood = 0.0

    def _save_state(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_save < _SAVE_INTERVAL_SECONDS:
            return
        self._last_save = now
        try:
            os.makedirs(os.path.dirname(MOOD_PATH), exist_ok=True)
            with open(MOOD_PATH, "w", encoding="utf-8") as fh:
                json.dump({"mood": round(self.mood, 3),
                           "interaction_count": self.interaction_count,
                           "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                           "label": self.get_label()}, fh, indent=2)
        except Exception as exc:
            _log.debug("mood save failed: %s", exc)

    def analyze_input(self, user_text) -> float:
        """Scan input for emotional signals and update mood. Returns the delta applied."""
        text = " " + re.sub(r"[^a-z0-9' ]", " ", (user_text or "").lower()) + " "
        delta, matched = 0.0, []
        signals = {**self.POSITIVE_SIGNALS, **self.NEGATIVE_SIGNALS}
        for phrase, value in sorted(signals.items(), key=lambda kv: len(kv[0]), reverse=True):
            if f" {phrase} " in text and not any(phrase in m or m in phrase for m in matched):
                delta += value
                matched.append(phrase)

        with self._lock:
            decay = 0.02
            if self.mood > 0:
                self.mood = max(0.0, self.mood - decay)
            elif self.mood < 0:
                self.mood = min(0.0, self.mood + decay)
            self.mood = max(-1.0, min(1.0, self.mood + delta))
            self.interaction_count += 1
            if delta:
                self.history = (self.history + [{
                    "text": text.strip()[:50], "delta": round(delta, 3),
                    "new_mood": round(self.mood, 3), "label": self.get_label()}])[-20:]
            self._save_state()
        return delta

    def on_command_result(self, success: bool) -> None:
        """Successful commands lift mood slightly; failures lower it."""
        with self._lock:
            self.mood = max(-1.0, min(1.0, self.mood + (0.08 if success else -0.10)))
            self._save_state()

    def get_label(self) -> str:
        for low, high, label in self.MOOD_LABELS:
            if low <= self.mood < high:
                return label
        return "neutral"

    def get_mood_prompt_modifier(self) -> str:
        """Legacy accessor. The prompt builder now maps the label itself."""
        return self.get_label()

    def get_status(self) -> dict:
        return {"mood_value": round(self.mood, 3), "label": self.get_label(),
                "interaction_count": self.interaction_count,
                "recent_changes": self.history[-5:]}

    def reset(self) -> None:
        """Reset to neutral."""
        with self._lock:
            self.mood, self.interaction_count, self.history = 0.0, 0, []
            self._save_state(force=True)


mood_engine = MoodEngine()
