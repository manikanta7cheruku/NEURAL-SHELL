"""
mouth/tone.py
How a sentence should sound, from what it says.

A neural voice already reads punctuation and phrasing naturally; tone adds the human part people notice: slowing and
softening for bad news or sympathy, a little lift for good news, a breath after a question. Returned as a speed factor
(multiplied with the user's chosen speed) and a pause in seconds after the sentence.
"""
import re

_GENTLE = re.compile(r"\b(sorry|sad|loss|lost|passed away|condolence|hard time|difficult|tough|hurt|miss (?:you|them|her|him)|"
                     r"grief|unfortunately|i understand|take care|be kind to yourself|that must)\b", re.I)
_BRIGHT = re.compile(r"(!|\b(great|awesome|congrat\w*|well done|nice|done|ready|all set|good news|perfect|yay)\b)", re.I)
_URGENT = re.compile(r"\b(overdue|now|urgent|immediately|battery (?:is )?(?:low|critical))\b", re.I)


def of(sentence: str) -> dict:
    s = sentence.strip()
    if _GENTLE.search(s):
        return {"tone": "gentle", "speed": 0.9, "pause": 0.35}
    if _URGENT.search(s):
        return {"tone": "clear", "speed": 1.0, "pause": 0.2}
    if _BRIGHT.search(s):
        return {"tone": "bright", "speed": 1.05, "pause": 0.15}
    if s.endswith("?"):
        return {"tone": "asking", "speed": 1.0, "pause": 0.3}
    return {"tone": "neutral", "speed": 1.0, "pause": 0.12}


def chunks(text: str) -> list:
    """Split into sentences, and split a long first sentence at a comma, so the first words play sooner."""
    text = re.sub(r"\s+", " ", text.split("###")[0]).strip()            # action tags are for the hands, not the voice
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text) if p.strip()]
    if parts and len(parts[0]) > 110:
        head, sep, rest = parts[0].partition(", ")
        if sep and 8 <= len(head) <= 90:
            parts = [head + ",", rest] + parts[1:]
    return parts
