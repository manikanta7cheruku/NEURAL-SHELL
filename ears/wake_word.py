"""
ears/wake_word.py
Seven — Wake word detection and command stripping.

check_and_strip() is called on every transcribed phrase when wake word gate is enabled.
Returns the command without the wake word, and whether a wake word was found.

Example:
    "hey seven open chrome" → ("open chrome", True)
    "open chrome"           → ("open chrome", False)  ← blocked if gate enabled
"""

from colorama import Fore


def check_and_strip(text: str, wake_words: list) -> tuple:
    """
    Check if text starts with a configured wake word. Strip it if found.

    Args:
        text:       transcribed user speech (original case)
        wake_words: list of wake word strings from config

    Returns:
        (stripped_text, found)
        found=True  — wake word found, stripped_text is the command after it
        found=False — no wake word found
    """
    if not text or not wake_words:
        return text, False

    clean = text.lower().strip()

    # Sort longest first — "hey seven" must be checked before "seven"
    sorted_words = sorted(
        [w.lower().strip() for w in wake_words if w.strip()],
        key=len,
        reverse=True
    )

    for word in sorted_words:
        if clean.startswith(word):
            # Strip from original text to preserve case of remainder
            remainder = text[len(word):].strip().lstrip(",.!? ")
            print(Fore.CYAN + f"[WAKE] '{word}' detected → command: '{remainder}'")
            return remainder, True

    return text, False


def get_defaults() -> list:
    """Default wake words used when none configured."""
    return ["hey seven", "ok seven", "okay seven", "yo seven", "seven"]