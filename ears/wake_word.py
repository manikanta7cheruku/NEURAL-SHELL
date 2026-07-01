"""
ears/wake_word.py
Seven — Wake word detection and stripping.

Checks if transcribed text starts with a configured wake word.
Strips the wake word before passing to brain.

Example:
    Input:  "hey seven open chrome"
    Output: ("open chrome", True)  — wake word found and stripped

    Input:  "open chrome"
    Output: ("open chrome", False) — no wake word (blocked if enabled)
"""

import re
from colorama import Fore

# Default wake words — user can add more in Settings
DEFAULT_WAKE_WORDS = [
    "hey seven",
    "ok seven",
    "okay seven",
    "yo seven",
    "seven",
    "hi seven",
    "hello seven",
]


def check_and_strip(text: str, wake_words: list) -> tuple:
    """
    Check if text contains a wake word at the start.
    Strip it if found.

    Args:
        text:       transcribed user speech
        wake_words: list of configured wake words

    Returns:
        (stripped_text: str, found: bool)
        found=True  → wake word detected, stripped_text has wake word removed
        found=False → no wake word detected
    """
    clean = text.lower().strip()

    # Sort by length descending — check longer phrases first
    # Prevents "seven" matching before "hey seven"
    sorted_words = sorted(wake_words, key=len, reverse=True)

    for word in sorted_words:
        word_lower = word.lower().strip()
        if clean.startswith(word_lower):
            # Strip wake word from original text (preserve case of remainder)
            remainder = text[len(word_lower):].strip()
            # Remove leading punctuation/comma
            remainder = remainder.lstrip(",.!? ")
            print(Fore.CYAN + f"[WAKE] Wake word '{word}' detected → '{remainder}'")
            return remainder, True

    return text, False


def get_default_words() -> list:
    """Return default wake word list."""
    return DEFAULT_WAKE_WORDS.copy()