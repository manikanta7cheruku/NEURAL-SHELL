"""
ears/wake_word.py
Seven — Wake word detection with fuzzy matching.

check_and_strip() is called on every transcribed phrase when wake word
gate is enabled. Returns the command without the wake word, and whether
a wake word was found.

Fuzzy matching catches Whisper mishearing:
    "hey seven"  -> "hey stephen", "hey heaven", "hey stefan"
    All of these will now correctly trigger Seven.

Uses RapidFuzz for phonetic similarity scoring.
Falls back to difflib if RapidFuzz not installed.

Example:
    "hey seven open chrome" -> ("open chrome", True)
    "hey heaven open chrome" -> ("open chrome", True)   <- fuzzy catch
    "open chrome"            -> ("open chrome", False)  <- blocked if gate on
"""

import re

from colorama import Fore

try:
    from rapidfuzz import fuzz as _rfuzz
    _FUZZY_ENGINE = "rapidfuzz"
except ImportError:
    import difflib as _difflib
    _FUZZY_ENGINE = "difflib"
    print(Fore.YELLOW + (
        "[WAKE] RapidFuzz not installed — using difflib fuzzy matching.\n"
        "       Run: venv\\Scripts\\pip install rapidfuzz"
    ))


def _fuzzy_score(a: str, b: str) -> float:
    """
    Return similarity score 0-100 between two strings.
    Uses RapidFuzz if available, difflib otherwise.
    """
    if _FUZZY_ENGINE == "rapidfuzz":
        return _rfuzz.ratio(a, b)
    else:
        return _difflib.SequenceMatcher(None, a, b).ratio() * 100


def check_and_strip(text: str, wake_words: list) -> tuple:
    """
    Check if text contains a configured wake word. Strip it if found.

    Strategy:
        1. Exact match first (fastest).
        2. Fuzzy match on first N words of transcription (N = wake word length).
           Catches Whisper mishearings like "hey heaven" -> "hey seven".

    Fuzzy threshold: 78/100
        Low enough to catch common mishearings.
        High enough to avoid false positives on unrelated speech.

    Args:
        text:       transcribed user speech (original case)
        wake_words: list of wake word strings from config

    Returns:
        (stripped_text, found)
        found=True  — wake word found, stripped_text is command after it
        found=False — no wake word found
    """
    if not text or not wake_words:
        return text, False

    clean     = text.lower().strip()
    clean_words = clean.split()
    orig_words  = text.split()

    # Sort longest first — "hey seven" checked before "seven"
    sorted_words = sorted(
        [w.lower().strip() for w in wake_words if w.strip()],
        key=len,
        reverse=True
    )

    # Pass 1: exact match — fastest and most reliable
    for word in sorted_words:
        if re.match(re.escape(word) + r"(?![\w-])", clean):          # a whole word: "seventeen" isn't "seven"
            remainder = text[len(word):].strip().lstrip(",.!? ")
            print(Fore.CYAN + f"[WAKE] Exact match: '{word}' — command: '{remainder}'")
            return remainder, True

        # Also check if wake word appears anywhere in short clips
        # (user may say "seven" without "hey" prefix)
        if len(clean_words) <= len(word.split()) + 2 and re.search(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", clean):
            remainder = clean.replace(word, "").strip().lstrip(",.!? ")
            print(Fore.CYAN + f"[WAKE] Contains match: '{word}' — command: '{remainder}'")
            return remainder or text, True

    # Pass 2: fuzzy match — catches Whisper mishearings
    for word in sorted_words:
        word_len  = len(word.split())
        if len(clean_words) < word_len:
            continue

        candidate = " ".join(clean_words[:word_len])
        score     = _fuzzy_score(candidate, word)

        if score >= 78:
            remainder = " ".join(orig_words[word_len:]).strip().lstrip(",.!? ")
            print(Fore.CYAN + (
                f"[WAKE] Fuzzy match: '{candidate}' ~ '{word}' "
                f"(score={score:.0f}) — command: '{remainder}'"
            ))
            return remainder, True

    return text, False


def get_defaults() -> list:
    """Default wake words used when none configured."""
    return ["hey seven", "ok seven", "okay seven", "yo seven", "seven"]


# Whisper writes Seven's name as a digit, and the wake phrase in many shapes: "Hey 7", "H7", "A7", "Hay 7", "7,".
_WAKE_SPELLINGS = re.compile(r"^\s*(?:(?:hey|hay|hi|hei|ok|okay|o\.?k\.?)[\s,.\-]*(?:7|seven)|(?:a|h)[\s\-]?7|7|seven)"
                             r"(?![\w-])[\s,.!?]*", re.I)


_VERBS = {"open", "close", "show", "play", "stop", "set", "turn", "what", "what's", "whats", "who", "how", "when", "where",
          "remind", "start", "find", "search", "tell", "read", "mute", "pause", "resume", "save", "restore", "can",
          "could", "please", "volume", "brightness", "take", "go", "launch", "add", "list", "do", "is", "are"}


def normalize_wake(text: str) -> str:
    """'Hey 7, open chrome' -> 'Hey seven, open chrome', so the wake-word check sees Seven's name."""
    m = _WAKE_SPELLINGS.match(text)
    if not m:
        return text
    rest = text[m.end():].strip()
    bare = re.match(r"^\s*(?:7|seven)", text, re.I) is not None
    if bare and rest:                                # "7 tasks are due" is a sentence, not Seven's name
        paused = re.search(r"[,.!?]", text[:m.end()]) is not None
        first = rest.split()[0].lower().strip(",.!?") if rest.split() else ""
        if not paused and first not in _VERBS:
            return text
    return f"Hey seven, {rest}" if rest else "Hey seven"
