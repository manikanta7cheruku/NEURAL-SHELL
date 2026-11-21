"""
ears/barge_in.py
A request said over Seven while it was talking.

"Seven, what's the weather" in the middle of an answer is two things: a stop word and the next question. The interrupt listener stops
Seven (ears/core.py, listen_for_interrupt) and keeps the question, so it is answered next instead of being thrown away with the
interruption.
"""
import re


def request_after(text: str, word: str) -> str:
    """The request that follows a stop word at the start of what was said, or "" when there is none:

        request_after("Seven, what's the weather", "seven")   -> "what's the weather"
        request_after("Hey Seven what time is it", "seven")   -> "what time is it"
        request_after("stop, set a timer for five minutes", "stop") -> "set a timer for five minutes"
        request_after("Seven", "seven")                       -> ""      (nothing follows: it is only the interruption)
        request_after("what's the weather, wait", "wait")     -> ""      (the stop word is not at the start)
    """
    text = (text or "").strip()
    rest = re.sub(r"^\W*(?:hey |ok |okay )?" + re.escape(word) + r"\b[\s,.!?]*", "", text, count=1, flags=re.IGNORECASE).strip()
    if rest == text or len(rest.split()) < 2:
        return ""
    return rest
