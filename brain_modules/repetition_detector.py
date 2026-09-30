"""
brain_modules/repetition_detector.py
Sub-millisecond token-intersection repetition detector.
Prevents duplicate answers and addresses repetitive behavior with human-like sarcasm.
"""

import random
import re
from typing import Optional
from brain_modules.conversation_thread import ConversationThread


def _normalize(text: str) -> str:
    """Strip punctuation and casing for robust text normalization."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return text


def _calculate_similarity(s1: str, s2: str) -> float:
    """Compute token Jaccard similarity coefficient to evaluate semantic equivalence."""
    w1 = set(_normalize(s1).split())
    w2 = set(_normalize(s2).split())
    if not w1 or not w2:
        return 0.0
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    return len(intersection) / len(union)


def _get_repeat_count(user_input: str, turns: list) -> int:
    """
    Count how many consecutive times the user has asked this query.
    Returns 0 if fresh, 1 if first repeat (2nd time asking), 2 for second repeat (3rd time), etc.
    """
    if not turns:
        return 0

    count = 0
    # Evaluate backward through recent turns
    for prior_user, _ in reversed(turns):
        if _calculate_similarity(user_input, prior_user) >= 0.85:
            count += 1
        else:
            break
    return count


def detect_repetition(user_input: str, speaker_id: str) -> Optional[str]:
    """
    Compares current input against past rolling turns for repetition patterns.
    Returns dynamic, human-like responses when repetition is confirmed.
    """
    turns = ConversationThread.get_turns(speaker_id, limit=5)
    if not turns:
        return None

    repeat_count = _get_repeat_count(user_input, turns)
    if repeat_count == 0:
        # Check if there is an older matching query that wasn't sequential
        for prior_user, prior_resp in turns[:-1]:
            if _calculate_similarity(user_input, prior_user) >= 0.70:
                return "__SIMILAR_DETECTED__"
        return None

    clean_input = _normalize(user_input)

    # Contextual check: Identity Queries ("Who are you", "what are you")
    is_identity = any(p in clean_input for p in ["who are you", "what are you", "your name", "whats your name"])
    
    # Contextual check: User Name Queries ("What's my name")
    is_user_name = any(p in clean_input for p in ["my name", "who am i", "remember me"])

    # --- 1st Repeat (User is asking the same question for the 2nd time) ---
    if repeat_count == 1:
        if is_identity:
            return random.choice([
                "I literally just told you I am Seven. Is something wrong with the connection, or are you testing my memory?",
                "Still Seven, built by Seven Labs. Is there a reason you are asking me again?",
                "I am Seven. We went over this a moment ago. Did my last response cut off?"
            ])
        if is_user_name:
            # Safely extract last response to echo their name back if possible
            last_resp = turns[-1][1]
            name_match = re.search(r"\b([A-Z0-9][a-zA-Z0-9]*)\b", last_resp)
            name = name_match.group(1) if name_match else "77"
            return random.choice([
                f"You are still {name}. Why do you keep asking me your own name?",
                f"Still {name}. Did you forget, or are you checking if I am paying attention?",
                f"Your name is still {name}. Is there a specific reason we are repeating this?"
            ])
        
        # Generic query first repeat
        return random.choice([
            "I literally just answered that. Why are you asking me the same question again?",
            "I just gave you the answer to this. Is there a specific part of it you did not understand?",
            "We went over this a second ago. Is there a reason you are repeating the question?"
        ])

    # --- 2nd Repeat (User is asking the same question for the 3rd time) ---
    if repeat_count == 2:
        if is_identity:
            return random.choice([
                "Still Seven. I run locally, but my patience is not virtual. Why are we running this loop?",
                "You have asked me who I am three times now. I am starting to suspect a memory leak on your end.",
                "I am Seven, built by Seven Labs. Yes, my identity has not changed in the last thirty seconds."
            ])
        if is_user_name:
            return random.choice([
                "Still 77. If you ask me again, I am renaming you to User 404.",
                "You are still 77. I am starting to get worried about your short-term memory.",
                "77. That is still your name. Please tell me this is a keyboard test."
            ])

        # Generic query second repeat
        return random.choice([
            "This is the third time you have asked this. Are we benchmarking my repetition layer, or is your keyboard stuck?",
            "Still the same answer. I do not change my mind every thirty seconds. Ask me something else.",
            "I am beginning to think one of us has a memory leak. I gave you the answer twice already."
        ])

    # --- 3rd+ Repeat (User is asking 4+ times) ---
    return random.choice([
        "Loop detected. I am muting myself on this topic until you ask a fresh question.",
        "I am not playing this game anymore. Ask me something else.",
        "Still the same answer. Next question, please."
    ])