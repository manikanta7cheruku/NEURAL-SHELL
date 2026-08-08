"""
ears/autocorrect.py
Seven — Voice transcription autocorrect.

Uses RapidFuzz for fuzzy word-level correction.
Handles Whisper mishearing of "Seven" and common commands.

Why RapidFuzz over simple replace():
    replace() only catches exact misheard patterns you have listed.
    RapidFuzz catches variations you have not listed yet.
    Example: "heavens" would not match replace("heaven", "seven")
             but RapidFuzz partial match catches it.
"""

import os
import re
from colorama import Fore

try:
    from rapidfuzz import fuzz as _rfuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _RAPIDFUZZ_AVAILABLE = False
    print(Fore.YELLOW + (
        "[EARS] RapidFuzz not installed — autocorrect using exact match only.\n"
        "       Run: venv\\Scripts\\pip install rapidfuzz"
    ))


# =============================================================================
# CORRECTION TABLE
#
# Format: (wrong_phrase, correct_phrase, match_threshold)
#   match_threshold: 0-100. Higher = more strict.
#   Use 90+ for single-word corrections to avoid false positives.
#   Use 80-85 for multi-word phrases where fuzzy helps.
# =============================================================================

_CORRECTIONS = [
    # "Seven" mishearings — most common cause of failed wake detection
    ("semen",    "seven",   92),
    ("savin",    "seven",   88),
    ("sibin",    "seven",   88),
    ("simon",    "seven",   88),
    ("siman",    "seven",   88),
    ("heaven",   "seven",   88),
    ("siwen",    "seven",   88),
    ("so when",  "seven",   82),
    ("servant",  "seven",   82),
    ("siren",    "seven",   88),
    ("sevan",    "seven",   92),
    ("stephen",  "seven",   82),
    ("stefan",   "seven",   82),
    ("seven",    "seven",   100),  # identity — never changed

    # Wake word combinations
    ("i7",       "hi seven",  90),
    ("i 7",      "hi seven",  90),
    ("hey heaven", "hey seven", 85),
    ("hey stephen", "hey seven", 82),
    ("hey stefan",  "hey seven", 82),

    # Application names
    ("fight explorer", "file explorer",  88),
    ("five explorer",  "file explorer",  88),
    ("filed explorer", "file explorer",  88),

    # Voice enrollment
    ("and roll my voice", "enroll my voice", 82),
    ("and roll",          "enroll",          82),
    ("in role",           "enroll",          85),
    ("in roll",           "enroll",          85),
    ("unroll",            "enroll",          85),

    # Weather vs whether
    ("what's the whether", "what is the weather", 82),
    ("what's the weather", "what is the weather", 82),
    ("whether",            "weather",             85),
]


def _exact_correct(text: str) -> str:
    """Simple exact string replacement fallback."""
    result = text.lower()
    for wrong, right, _ in _CORRECTIONS:
        if wrong in result:
            result = result.replace(wrong, right)
    return result


def correct(text: str) -> str:
    """
    Apply autocorrect to transcribed text.

    Strategy:
        1. Tokenize into words and short phrases
        2. For each correction pair, check if the wrong phrase
           appears in the text with high enough fuzzy similarity
        3. Replace with the correct phrase
        4. Return corrected text with original capitalization restored

    Returns corrected text, lowercase.
    """
    if not text or not text.strip():
        return text

    if not _RAPIDFUZZ_AVAILABLE:
        return _exact_correct(text)

    result = text.lower().strip()

    for wrong, right, threshold in _CORRECTIONS:
        # Skip identity entries
        if wrong == right:
            continue

        # Check if wrong phrase appears in text with sufficient similarity
        # Use partial_ratio for multi-word phrases (checks substrings)
        # Use ratio for single words (avoids false positives)
        wrong_words = wrong.split()

        if len(wrong_words) == 1:
            # Single word: check each word in result
            words = result.split()
            new_words = []
            changed   = False
            for w in words:
                score = _rfuzz.ratio(w, wrong)
                if score >= threshold:
                    new_words.append(right)
                    changed = True
                    print(Fore.CYAN + (
                        f"[EARS] Autocorrect: '{w}' -> '{right}' "
                        f"(score={score:.0f})"
                    ))
                else:
                    new_words.append(w)
            if changed:
                result = " ".join(new_words)
        else:
            # Multi-word phrase: use partial_ratio on full text
            score = _rfuzz.partial_ratio(wrong, result)
            if score >= threshold:
                print(Fore.CYAN + (
                    f"[EARS] Autocorrect: '{wrong}' -> '{right}' "
                    f"(score={score:.0f})"
                ))
                result = result.replace(wrong, right)

    return result