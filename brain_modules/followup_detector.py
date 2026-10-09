"""
=============================================================================
brain_modules/followup_detector.py

Follow-up Detection Engine.

Analyzes Seven's completed responses for signals that the user may
naturally continue the thread on their next turn:

  - Response ends with a question mark
  - Response contains a proactive offer ("Want me to...", "Shall I...")
  - Response was cut short mid-thought (dangling connectives)
  - Response contains explicit continuation cues ("let me know if...")

When detected, stores a short hint on the ConversationThread metadata.
Next turn's prompt builder consumes the hint to prime continuation context.

DESIGN PRINCIPLES:
    - Positive framing only. Matches Phase 4 Batch 1 hint contract.
    - No LLM calls. Pure string analysis. Sub-1ms detection latency.
    - Auto-clears after being consumed once so it never poisons long threads.
=============================================================================
"""

import re
from typing import Optional, Dict


# -- Detection signal lexicons --------------------------------------------

_OFFER_MARKERS = [
    "want me to", "shall i", "should i", "would you like",
    "do you want", "let me know if you want", "if you'd like",
    "if you want", "just say the word", "ready when you are",
]

_DANGLING_CONNECTIVES = {
    "and", "but", "or", "so", "because", "since", "although",
    "while", "unless", "though", "yet", "however", "meanwhile",
}

_CONTINUATION_CUES = [
    "let me know", "tell me more", "more on that", "keep going",
    "there is more", "there's more", "we can go deeper",
    "happy to expand", "if you're curious", "if curious",
]


def _extract_topic_seed(response: str, max_words: int = 8) -> str:
    """
    Extract a short topic seed from the response to hint the follow-up.
    Uses the last complete sentence or trailing clause.
    """
    if not response:
        return ""

    # Strip action tags before analysis
    cleaned = re.sub(r'###\w+:\s*\S+', '', response).strip()

    # Take last sentence or clause
    sentences = re.split(r'[.!?]+', cleaned)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return ""

    last = sentences[-1]
    words = last.split()
    if len(words) > max_words:
        return " ".join(words[-max_words:])
    return last


def detect_followup(response_text: str) -> Optional[Dict]:
    """
    Analyze a completed response for follow-up potential.

    Returns:
        None if no follow-up signal detected.
        Dict {"reason", "topic_seed", "hint"} otherwise.
    """
    if not response_text or not isinstance(response_text, str):
        return None

    text = response_text.strip()
    if len(text) < 10:
        return None

    text_lower = text.lower()
    topic_seed = _extract_topic_seed(text)

    # Signal 1: Response ends with a question mark (open offer or genuine question)
    if text.rstrip().endswith("?"):
        # Prefer offer framing when offer markers are present
        for marker in _OFFER_MARKERS:
            if marker in text_lower:
                return {
                    "reason": "offer",
                    "topic_seed": topic_seed,
                    "hint": (
                        "Your previous reply offered to help with something. "
                        "If the user accepts, agrees, or says yes, act on that offer. "
                        "If they decline or change topic, drop it and move on."
                    ),
                }
        return {
            "reason": "question",
            "topic_seed": topic_seed,
            "hint": (
                "Your previous reply ended with a question. "
                "If the user's next message is a direct answer, respond to that answer naturally. "
                "Do not repeat the question."
            ),
        }

    # Signal 2: Response ends with a dangling connective (cut-off mid-thought)
    tail_word = re.sub(r'[^\w]', '', text_lower.split()[-1]) if text_lower.split() else ""
    if tail_word in _DANGLING_CONNECTIVES:
        return {
            "reason": "cutoff",
            "topic_seed": topic_seed,
            "hint": (
                "Your previous reply may have been cut short. "
                "If the user asks you to continue or finish the thought, pick up where you left off."
            ),
        }

    # Signal 3: Response contains a continuation cue
    for cue in _CONTINUATION_CUES:
        if cue in text_lower:
            return {
                "reason": "continuation",
                "topic_seed": topic_seed,
                "hint": (
                    "You invited the user to continue the conversation. "
                    "If they respond with interest or ask for more, expand naturally."
                ),
            }

    # Signal 4: Response ends with ellipsis or trailing comma (mid-thought)
    if text.rstrip().endswith(("...", "…", ",")):
        return {
            "reason": "elliptical",
            "topic_seed": topic_seed,
            "hint": (
                "Your previous reply trailed off. "
                "If the user prompts you to continue, complete the thought concisely."
            ),
        }

    return None