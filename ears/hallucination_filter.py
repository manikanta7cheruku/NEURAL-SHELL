"""
ears/hallucination_filter.py
Seven — Hallucination detection.

Reads phrases from ears/hallucinations.json.
Updating the JSON file is enough to change filter behavior.
No code changes needed when Whisper model updates its hallucination patterns.
"""

import os
import json
from colorama import Fore

_HALLUCINATIONS_PATH = os.path.join(
    os.path.dirname(__file__), "hallucinations.json"
)

_cache = None


def _load() -> dict:
    """
    Load hallucinations.json once, cache in memory.
    Falls back to minimal hardcoded set if file missing.
    """
    global _cache
    if _cache is not None:
        return _cache

    try:
        with open(_HALLUCINATIONS_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        return _cache
    except FileNotFoundError:
        print(Fore.YELLOW + "[EARS] hallucinations.json not found — using fallback")
    except json.JSONDecodeError as e:
        print(Fore.RED + f"[EARS] hallucinations.json corrupt: {e} — using fallback")
    except Exception as e:
        print(Fore.YELLOW + f"[EARS] hallucinations.json load error: {e} — using fallback")

    _cache = {
        "exact": [
            "thank you", "thanks", "you", "bye", "goodbye",
            "the", "a", "i", "hmm", "hm", "uh", "um", ".", "..", "...", " ", ""
        ],
        "substrings": ["amara.org", "mooji.org", "www.", ".org"],
        "filler_words": [
            "the", "a", "an", "is", "it", "to", "of", "and", "or", "but"
        ],
        "intent_words": [
            "open", "close", "what", "how", "seven", "hey", "hello"
        ]
    }
    return _cache


def reload():
    """Force reload from disk. Call after editing hallucinations.json."""
    global _cache
    _cache = None
    _load()
    print(Fore.CYAN + "[EARS] Hallucination list reloaded from disk")


def is_hallucination(clean: str, raw_lower: str = "") -> tuple:
    """
    Check if Whisper output is a known hallucination.

    Args:
        clean:     lowercase, punctuation stripped
        raw_lower: lowercase with punctuation — needed for substring checks
                   like www. and .org which require the period character

    Returns:
        (is_hallucination: bool, reason: str)
    """
    data = _load()

    # Exact match against known silence outputs
    if clean in data["exact"]:
        return True, f"exact match: '{clean}'"

    # Partial match — text starts with a known hallucination phrase
    # Catches: "thank you bye bye", "thanks for watching everyone"
    # where the full string is not in exact list but starts with one
    exact_set = set(data["exact"])
    for phrase in exact_set:
        if not phrase:
            continue
        if clean.startswith(phrase + " ") or clean.startswith(phrase + "."):
            return True, f"starts with hallucination: '{phrase}'"

    # Hallucination saturation — more than half the words are known hallucinations
    # Catches: "thank you bye bye" where 3/3 words are hallucination phrases
    words = clean.split()
    if len(words) >= 2:
        # Check individual words against single-word hallucinations
        single_word_hallucinations = {
            p for p in exact_set
            if p and len(p.split()) == 1
        }
        hallucination_word_count = sum(
            1 for w in words if w in single_word_hallucinations
        )
        if hallucination_word_count / len(words) >= 0.75:
            return True, (
                f"hallucination saturation "
                f"({hallucination_word_count}/{len(words)} words): '{clean}'"
            )

    # Outro hallucinations — Whisper invents these from TV/audio bleed
    if clean.startswith(("thank you", "thanks")):
        if any(k in clean for k in (
            "watching", "having me", "joining",
            "listening", "for me", "for watching", "for having me"
        )):
            return True, f"outro phrase: '{clean}'"

    # Substring match — use punctuation-preserved text
    check_text = raw_lower if raw_lower else clean
    for pattern in data["substrings"]:
        if pattern in check_text:
            return True, f"substring match: '{pattern}'"

    words = clean.split()

    # Repeated single syllable — "ba ba ba", "da da da"
    if len(words) >= 3:
        unique = set(words)
        if len(unique) == 1 and len(list(unique)[0]) <= 3:
            return True, f"repeated syllable: '{clean}'"

    # Pure filler — 85%+ of words are connectors with no intent
    if len(words) >= 6:
        filler_set    = set(data.get("filler_words", []))
        content_words = [w for w in words if w not in filler_set]
        filler_ratio  = 1 - (len(content_words) / len(words))
        if filler_ratio > 0.85:
            return True, f"pure filler ({filler_ratio:.0%}): '{clean}'"

    # Music/singing detection
    # Whisper transcribes sung lyrics with characteristic patterns:
    # repetitive syllables, phonetic spellings, hyphenated sounds
    words = clean.split() if not words else words
    if len(words) >= 4:
        # Check for sung phonetics: "o-o-o-o", "we-e-e", "la-la-la"
        hyphenated = [w for w in words if '-' in w and len(w) > 3]
        if len(hyphenated) >= 2:
            return True, f"sung phonetics detected: {hyphenated[:3]}"

        # Check for music emoji patterns already cleaned
        if any(c in clean for c in ['♪', '♫', '🎵', '🎶']):
            return True, "music emoji in transcription"

        # High ratio of very short words (1-2 chars) = phonetic singing
        short_words = [w for w in words if len(w) <= 2]
        if len(words) >= 6 and len(short_words) / len(words) > 0.5:
            return True, f"high ratio of short phonemes ({len(short_words)}/{len(words)})"

    # Commercial / advertisement detection
    # TV ads and phone ads have specific patterns that are never commands:
    # prices, brand delivery platforms, calls to action
    _ad_patterns = {
        "rupees", "swiggy", "zomato", "amazon", "flipkart",
        "order now", "download", "offer valid", "call now",
        "buy now", "shop now", "subscribe now", "click here",
        "visit", "terms and conditions", "limited time",
        "never go out of style", "all the traditions",
        "soft kulab", "crisp chale",
    }
    _ad_matches = [p for p in _ad_patterns if p in clean]
    if _ad_matches:
        return True, f"commercial content detected: {_ad_matches[:2]}"

    # Long transcriptions with no command structure
    # Real commands are under 20 words. 25+ words = ambient audio (ads, TV, radio)
    words = clean.split() if not words else words
    if len(words) > 25:
        # Check if there are any intent words at all
        intent_set = set(data.get("intent_words", []))
        has_intent = any(w in intent_set for w in words)
        if not has_intent:
            return True, (
                f"long non-command transcription ({len(words)} words, "
                f"no intent words)"
            )

    return False, ""


def is_repetition_loop(clean: str) -> bool:
    """
    Detect Whisper's repetition hallucination.
    When Whisper cannot understand audio, it loops the same phrase.
    Example: "i don't know i don't know i don't know"

    Returns True if repetition loop detected.
    """
    words = clean.split()
    if len(words) < 8:
        return False

    chunk_size = 4
    seen       = set()
    for i in range(len(words) - chunk_size + 1):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk in seen:
            return True
        seen.add(chunk)
    return False


def is_incoherent(clean: str) -> bool:
    """
    Detect word salad from background noise.
    Example: "on a new place of time week" — no human says this.

    Checks:
        1. Connector density > 70% with no intent word = word salad
        2. Only runs on 5+ word clips

    Returns True if text appears incoherent.
    """
    words = clean.split()
    if len(words) < 5:
        return False

    data = _load()
    connector_set  = set(data.get("filler_words", []))
    intent_set     = set(data.get("intent_words", []))

    connector_count = sum(1 for w in words if w in connector_set)
    connector_ratio = connector_count / len(words)
    has_intent      = any(w in intent_set for w in words)

    if connector_ratio > 0.70 and not has_intent:
        return True

    return False