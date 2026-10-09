"""
=============================================================================
brain_modules/tone_tracker.py

Tone Tracking Engine.

Tracks user sentiment, playful signals, frustration cues, and sequential
corrections. Computes dynamic humor and honesty biases to adjust Seven's
personality settings dynamically per conversation.

Biases are kept within a safe bounds system, sliding back to baseline
naturally over peaceful turns.
=============================================================================
"""

import re
import threading
from typing import Dict, List, Tuple

# -- Playful and Frustration indicators ------------------------------------

_PLAYFUL_MARKERS = {
    "haha", "lol", "lmao", "rofl", "hehe", "xd", "lmfao", "joke",
    "funny", "sarcastic", "sarcasm", "hilarious", "good one"
}

_FRUSTRATION_MARKERS = {
    "annoying", "annoyed", "frustrated", "stop", "stupid", "dumb",
    "useless", "wrong", "incorrect", "false", "terrible", "bad",
    "not what i asked", "nonsense", "garbage", "waste"
}

# -- Speaker Tone State Class ----------------------------------------------

class SpeakerToneState:
    """Tracks running metric history for an individual speaker."""
    def __init__(self):
        self.consecutive_corrections: int = 0
        self.recent_humor_adjustments: List[int] = []
        self.recent_honesty_adjustments: List[int] = []
        self.turn_history_size: int = 5

    def add_turn_metrics(self, playful: bool, frustrated: bool, is_correction: bool) -> None:
        """Process metrics for a new dialogue turn."""
        if is_correction:
            self.consecutive_corrections += 1
        else:
            self.consecutive_corrections = 0

        # Base adjustments for this turn
        humor_adj = 0
        honesty_adj = 0

        if playful:
            # Playful markers increase humor bias +10 (Phase 4 Success Criteria)
            humor_adj += 10
            honesty_adj -= 5

        if frustrated:
            humor_adj -= 20
            honesty_adj += 15

        # 3 consecutive corrections shift tone to neutral and direct
        # (Phase 4 Success Criteria: humor neutralized, directness maximized)
        if self.consecutive_corrections >= 3:
            # Heavy override biases
            humor_adj = -100
            honesty_adj = 100
        elif is_correction:
            # Single correction nudge
            humor_adj -= 10
            honesty_adj += 10

        self.recent_humor_adjustments.append(humor_adj)
        self.recent_honesty_adjustments.append(honesty_adj)

        # Enforce sliding history window
        if len(self.recent_humor_adjustments) > self.turn_history_size:
            self.recent_humor_adjustments.pop(0)
        if len(self.recent_honesty_adjustments) > self.turn_history_size:
            self.recent_honesty_adjustments.pop(0)

    def get_aggregate_bias(self) -> Tuple[int, int]:
        """Aggregate sliding-window metrics to return dynamic bias tuple."""
        # Hard lock takes precedence
        if self.consecutive_corrections >= 3:
            return -100, 100

        if not self.recent_humor_adjustments:
            return 0, 0

        # Weighted average prioritizing the most recent turns
        total_humor = 0
        total_honesty = 0
        total_weight = 0

        for idx, (h, o) in enumerate(zip(self.recent_humor_adjustments, self.recent_honesty_adjustments)):
            weight = idx + 1
            total_humor += h * weight
            total_honesty += o * weight
            total_weight += weight

        return int(total_humor / total_weight), int(total_honesty / total_weight)


# -- Dynamic Tone Manager --------------------------------------------------

_tone_states: Dict[str, SpeakerToneState] = {}
_lock = threading.Lock()


def observe(speaker_id: str, text: str, is_correction: bool) -> None:
    """
    Examine incoming user utterance and update speaker's tone metrics.
    Safe, fast string token matches run locally under 1ms.
    """
    if not text:
        return

    text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
    words = set(text_clean.split())

    playful = bool(words & _PLAYFUL_MARKERS)
    frustrated = bool(words & _FRUSTRATION_MARKERS)

    with _lock:
        if speaker_id not in _tone_states:
            _tone_states[speaker_id] = SpeakerToneState()
        _tone_states[speaker_id].add_turn_metrics(playful, frustrated, is_correction)


def get_bias(speaker_id: str) -> Tuple[int, int]:
    """
    Retrieve dynamic bias metrics for a given speaker.
    Returns: Tuple of (humor_bias_adjustment, honesty_bias_adjustment)
    """
    with _lock:
        if speaker_id not in _tone_states:
            return 0, 0
        return _tone_states[speaker_id].get_aggregate_bias()    


def reset_tone_state(speaker_id: str) -> None:
    """Clear tone tracking records for a clean restart."""
    with _lock:
        _tone_states.pop(speaker_id, None)