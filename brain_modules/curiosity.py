"""
brain_modules/curiosity.py

When and what Seven asks back.

Seven asks only because it has a recorded reason (a knowledge gap), never to
sound engaged. A question budget keeps it from nagging: one question every few
turns at most, none when the user is terse or frustrated, and a cool-down
after questions were ignored. Questions are turned into a pending state so the
next message is read as the answer.
"""

import random
from typing import Optional

from brain_modules import conversation_state as cs
from memory import learning_store

_INTERVAL = {"off": 0, "low": 8, "normal": 4}
_TEMPLATES = {
    "favorite_promotion": ["Is {value} your favorite {kind}, or one of several?",
                           "Would you call {value} your favorite {kind}?"],
    "reason_change": ["What made you switch from {former} to {current}?",
                      "Out of curiosity, what changed from {former} to {current}?"],
    "goal_detail": ["What does done look like for {title}?", "What's the next milestone for {title}?"],
    "entity_interest": ["You keep coming back to {entity}. Is it something you like, or something you're working on?"],
}
_PRIORITY = {"favorite_promotion": 6, "goal_detail": 4, "reason_change": 3, "entity_interest": 2}


def level(config) -> str:
    try:
        lv = str(config.KEY.get("brain", {}).get("curiosity_level", "normal")).lower()
    except Exception:
        lv = "normal"
    return lv if lv in _INTERVAL else "normal"


def open_gap(speaker_key: str, kind: str, subject: str, payload: dict) -> Optional[int]:
    """Record something worth asking about (idempotent per subject)."""
    return learning_store.add_gap(speaker_key, kind, subject, payload, _PRIORITY.get(kind, 3))


def pick_question(ctx, config, reply_text: str = "", rng: Optional[random.Random] = None) -> Optional[str]:
    """Return a question to append to this reply, or None. Updates pending state when it asks."""
    lv = level(config)
    interval = _INTERVAL[lv]
    if not interval or ctx.is_command or ctx.is_action_cmd:
        return None
    st = cs.get(ctx.thread_key)
    if st.turn - st.last_question_turn < interval:
        return None
    if st.ignored >= 2 and st.turn - st.last_question_turn < 20:
        return None
    if len((ctx.prompt_text or "").split()) < 4 or (reply_text or "").rstrip().endswith("?"):
        return None
    try:
        mood = ctx.mood_label
    except AttributeError:
        mood = "neutral"
    if mood in ("frustrated", "down"):
        return None
    gap = learning_store.next_gap(ctx.speaker_key)
    if not gap or gap["kind"] not in _TEMPLATES:
        return None
    try:
        text = (rng or random).choice(_TEMPLATES[gap["kind"]]).format(**gap["payload"])
    except (KeyError, IndexError):
        learning_store.set_gap_status(gap["id"], "expired")
        return None
    learning_store.set_gap_status(gap["id"], "asked")
    st.last_question_turn = st.turn
    cs.set_pending(st, f"gap:{gap['kind']}", {"gap_id": gap["id"], **gap["payload"]}, ttl=3)
    learning_store.record_outcome(ctx.speaker_key, "question", gap["kind"], "asked", conversation_id=ctx.conversation_id)
    return text
