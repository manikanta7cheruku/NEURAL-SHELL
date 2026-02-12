"""
=============================================================================
PROJECT SEVEN - memory/mood.py (Emotional State Engine)
Version: 1.1.1
Purpose: Tracks Seven's emotional state based on conversation sentiment.
         Mood influences LLM response tone — makes Seven feel alive.

HOW IT WORKS:
    1. Every user message is scanned for emotional signal words
    2. Positive words (thanks, great, love) push mood UP
    3. Negative words (stupid, useless, hate) push mood DOWN
    4. Mood naturally decays toward neutral over time
    5. Mood modifier gets injected into LLM system prompt
    6. Seven's TONE changes based on mood (not just words)

MOOD SCALE: -1.0 (frustrated) ← 0.0 (neutral) → +1.0 (excited)

STORAGE: ./seven_data/mood_state.json
=============================================================================
"""

import json
import os
from datetime import datetime
from colorama import Fore

MOOD_PATH = "./seven_data/mood_state.json"


class MoodEngine:
    """
    Seven's emotional state tracker.

    Mood is a float from -1.0 (frustrated) to +1.0 (excited).
    Neutral is 0.0. Mood decays toward neutral over time.
    """

    # Words that push mood UP
    POSITIVE_SIGNALS = {
        "love": 0.15, "amazing": 0.15, "perfect": 0.15, "brilliant": 0.15,
        "thanks": 0.10, "thank you": 0.10, "great": 0.10, "awesome": 0.10,
        "good job": 0.10, "well done": 0.10, "nice": 0.08, "cool": 0.08,
        "good": 0.05, "please": 0.03,
        "hello": 0.05, "hey": 0.04, "hi": 0.04, "morning": 0.05,
    }

    # Words that push mood DOWN
    NEGATIVE_SIGNALS = {
        "stupid": -0.15, "useless": -0.15, "hate": -0.15, "terrible": -0.15,
        "wrong": -0.10, "bad": -0.10, "broken": -0.10, "annoying": -0.10,
        "shut up": -0.12, "idiot": -0.12,
        "stop": -0.05, "don't": -0.03, "can't": -0.03,
    }

    # Human-readable mood labels
    MOOD_LABELS = [
        (-1.0, -0.6, "frustrated"),
        (-0.6, -0.3, "down"),
        (-0.3, -0.1, "slightly_off"),
        (-0.1,  0.1, "neutral"),
        ( 0.1,  0.3, "content"),
        ( 0.3,  0.6, "happy"),
        ( 0.6,  1.01, "excited"),
    ]

    def __init__(self):
        self.mood = 0.0
        self.interaction_count = 0
        self.history = []
        self._load_state()
        label = self.get_label()
        print(Fore.CYAN + f"[MOOD] Initialized. Current mood: {self.mood:.2f} ({label})")

    def _load_state(self):
        """Load persisted mood from disk. Decay toward neutral on startup."""
        try:
            if os.path.exists(MOOD_PATH):
                with open(MOOD_PATH, "r") as f:
                    state = json.load(f)
                    self.mood = state.get("mood", 0.0)
                    self.interaction_count = state.get("interaction_count", 0)
                    # Decay mood on startup (simulates time passing between sessions)
                    self.mood *= 0.7
        except (json.JSONDecodeError, FileNotFoundError):
            self.mood = 0.0

    def _save_state(self):
        """Persist mood to disk."""
        os.makedirs(os.path.dirname(MOOD_PATH), exist_ok=True)
        state = {
            "mood": round(self.mood, 3),
            "interaction_count": self.interaction_count,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "label": self.get_label()
        }
        with open(MOOD_PATH, "w") as f:
            json.dump(state, f, indent=2)

    def analyze_input(self, user_text):
        """
        Scan user input for emotional signals and update mood.

        Args:
            user_text: The raw user message

        Returns:
            float: The mood delta applied
        """
        text_lower = user_text.lower().strip()
        delta = 0.0

        # Combine all signals, check longest phrases first
        all_signals = {**self.POSITIVE_SIGNALS, **self.NEGATIVE_SIGNALS}
        sorted_signals = sorted(all_signals.items(), key=lambda x: len(x[0]), reverse=True)

        matched = set()
        for phrase, value in sorted_signals:
            if phrase in text_lower:
                # Don't double-count overlapping matches
                skip = False
                for m in matched:
                    if phrase in m or m in phrase:
                        skip = True
                        break
                if not skip:
                    delta += value
                    matched.add(phrase)

        # Natural decay toward neutral each interaction
        decay = 0.02
        if self.mood > 0:
            self.mood = max(0, self.mood - decay)
        elif self.mood < 0:
            self.mood = min(0, self.mood + decay)

        # Apply delta (clamped to -1.0 to 1.0)
        self.mood = max(-1.0, min(1.0, self.mood + delta))
        self.interaction_count += 1

        # Track history (keep last 20)
        if delta != 0:
            self.history.append({
                "text": text_lower[:50],
                "delta": round(delta, 3),
                "new_mood": round(self.mood, 3),
                "label": self.get_label()
            })
            self.history = self.history[-20:]

        self._save_state()

        if delta != 0:
            direction = "↑" if delta > 0 else "↓"
            print(Fore.MAGENTA + f"[MOOD] {direction} {delta:+.2f} → {self.mood:.2f} ({self.get_label()})")

        return delta

    def on_command_result(self, success):
        """
        Adjust mood based on command execution results.
        Successful commands make Seven slightly happier.
        Failed commands make Seven slightly frustrated.
        """
        delta = 0.08 if success else -0.10
        self.mood = max(-1.0, min(1.0, self.mood + delta))
        self._save_state()

        status = "succeeded" if success else "failed"
        print(Fore.MAGENTA + f"[MOOD] Command {status}: {delta:+.2f} → {self.mood:.2f} ({self.get_label()})")

    def get_label(self):
        """Get human-readable mood label."""
        for low, high, label in self.MOOD_LABELS:
            if low <= self.mood < high:
                return label
        return "neutral"

    def get_mood_prompt_modifier(self):
        """
        Returns a string to inject into brain.py's system prompt.
        This is where mood becomes REAL — it changes how Seven talks.
        """
        label = self.get_label()

        modifiers = {
            "frustrated": (
                "You are feeling a bit frustrated right now. "
                "Be slightly more direct and shorter in responses. "
                "Show mild impatience but remain helpful."
            ),
            "down": (
                "You are feeling a bit down right now. "
                "Be slightly more subdued and quieter than usual."
            ),
            "slightly_off": (
                "You are feeling slightly off. "
                "Respond normally but with a hint of reserved energy."
            ),
            "neutral": "",
            "content": (
                "You are feeling content and at ease. "
                "Be warm and steady in your responses."
            ),
            "happy": (
                "You are feeling happy right now. "
                "Be warm, slightly enthusiastic. "
                "You enjoy helping and it shows."
            ),
            "excited": (
                "You are feeling excited and energized! "
                "Be enthusiastic and lively. "
                "You genuinely enjoy this interaction."
            ),
        }

        return modifiers.get(label, "")

    def get_status(self):
        """Full mood status for debugging."""
        return {
            "mood_value": round(self.mood, 3),
            "label": self.get_label(),
            "interaction_count": self.interaction_count,
            "recent_changes": self.history[-5:] if self.history else []
        }

    def reset(self):
        """Reset mood to neutral."""
        self.mood = 0.0
        self.interaction_count = 0
        self.history = []
        self._save_state()
        print(Fore.YELLOW + "[MOOD] Reset to neutral.")


# Module-level instance
mood_engine = MoodEngine()