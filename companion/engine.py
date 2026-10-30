"""
companion/engine.py

Choosing one thing to say, posting it to Seven's chat thread, learning from the answer, and asking back.

The thread is an ordinary conversation (kind "companion"), so what the person writes in it is answered by the normal
brain, with memory and everything. This module adds the friend part around that:

    choose()              one thing worth saying now (content.pick), from what Seven knows and its banks
    post()                write it into the thread as Seven's message; counted as unread until the thread is opened
    note_user_message()   the person wrote in the thread: they answered, so remember a short answer as a fact,
                          queue a deeper question, and honour "not now" by going quiet for a while
    after_reply()         a moment after Seven answers in the thread, ask one thing back, as a second message

Everything takes `now` and `rng` so tests are exact. Nothing here speaks: scheduler.py decides when a message is said aloud.
"""
import datetime
import logging
import random
import re
import threading
from typing import Dict, Optional

from companion import content, settings, store
from companion.content import Candidate

_log = logging.getLogger("seven.companion")

THREAD_TITLE = "Seven"
SNOOZE_AFTER_NOT_NOW_H = 3
VOICE_ANSWER_WINDOW_S = 240          # a spoken reply this soon after Seven asked something is taken as the answer
_STOP = re.compile(r"\b(not now|stop (asking|messaging|texting|pinging)|leave me alone|be quiet|shut up|"
                   r"i'?m busy|busy right now|talk (to you )?later)\b", re.IGNORECASE)
_QUESTION_WORDS = {"what", "why", "how", "who", "when", "where", "which", "can", "could", "would", "do", "does", "is",
                   "are", "will", "should", "tell", "explain"}
_NO = {"no", "nope", "nah", "not really", "none", "nothing", "idk", "i don't know", "dont know", "don't know", "skip", "pass"}
_LEAD = re.compile(r"^(i am|i'm|im|i work as|i work in|i work at|it's|its|it is|i like|i love|i really like|probably|maybe|"
                   r"mostly|usually|just|a|an|the)\s+", re.IGNORECASE)

BY_TOPIC: Dict[str, Candidate] = {c.topic: c for c in content.ABOUT_YOU + content.ABOUT_SEVEN + content.FACTS}


# ------------------------------------------------------------------------------------------------ the thread
def speaker_key() -> str:
    from brain_modules import session
    return session.resolve_key("default")


def conversation_id(create: bool = True) -> Optional[str]:
    """Seven's own chat thread. Created the first time it is needed; always called Seven."""
    from memory import conversation_store as cstore
    key = speaker_key()
    cid = store.get_state("conversation_id")
    conv = cstore.get_conversation(cid) if cid else None
    if conv:
        if conv["speaker_key"] != key:                   # the owner's name changed: the thread is still theirs
            cstore.set_speaker(cid, key)
        return cid
    for conv in cstore._rows("SELECT id FROM conversations WHERE speaker_key=? AND kind='companion' LIMIT 1", (key,)):
        store.set_state("conversation_id", conv["id"])
        return conv["id"]
    if not create:
        return None
    cid = cstore.create_conversation(key, THREAD_TITLE, kind="companion")
    store.set_state("conversation_id", cid)
    return cid


def is_companion(conv_id: Optional[str]) -> bool:
    if not conv_id:
        return False
    try:
        from memory import conversation_store as cstore
        conv = cstore.get_conversation(conv_id)
        return bool(conv) and conv.get("kind") == "companion"
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ what to say
def _user_name() -> str:
    try:
        from brain_modules import session
        return session.get_user_name().split(" ")[0]
    except Exception:
        return ""


def context(now: datetime.datetime) -> dict:
    """What Seven knows that decides what to say: the name, the mood, open goals, a question it has held back, time away."""
    ctx: dict = {"name": _user_name(), "mood": "neutral", "goals": [], "gap": None, "away_hours": 0}
    key = speaker_key()
    try:
        from memory.mood import mood_engine
        ctx["mood"] = mood_engine.get_status()["label"]
    except Exception:
        pass
    try:
        from memory import learning_store
        ctx["goals"] = learning_store.list_goals(key, "active")
        ctx["gap"] = learning_store.next_gap(key)
    except Exception:
        pass
    prev = store.get_state("previous_seen")
    if prev:
        try:
            ctx["away_hours"] = (now - datetime.datetime.strptime(prev, store.FMT)).total_seconds() / 3600
        except ValueError:
            pass
    return ctx


def choose(now: Optional[datetime.datetime] = None, rng: Optional[random.Random] = None,
           cfg: Optional[dict] = None, exclude_kinds: tuple = ()) -> Optional[Candidate]:
    now = now or datetime.datetime.now()
    rng = rng or random.Random()
    cfg = cfg or settings.get()
    ctx = context(now)
    pool = content.personal(ctx, now) + content.library(cfg["topics"])
    asked = {c.topic: store.topic_last_asked(c.topic) for c in pool}
    return content.pick(pool, asked, store.recent_kinds(2), now, rng, exclude_kinds)


def render(cand: Candidate, rng: Optional[random.Random] = None) -> str:
    """The words. Now and then the name is used, the way a friend would, never on every message."""
    rng = rng or random.Random()
    name = _user_name()
    text = cand.text
    if name and cand.kind in ("you", "seven", "facts") and not text.lower().startswith(name.lower()) and rng.random() < 0.3:
        text = f"{name}, {text[0].lower()}{text[1:]}" if text[:2] not in ("I ", "I'") and not text[:1].isdigit() else text
    return text


def _publish_unread() -> None:
    try:
        from backend.api_server import set_state
        set_state("companion", {"unread": store.unread_count()})
    except Exception:
        pass


def post(cand: Candidate, spoken: bool = False, read: bool = False, rng: Optional[random.Random] = None,
         as_followup: bool = False, now: Optional[datetime.datetime] = None) -> int:
    """Write Seven's message into the thread. Returns its message id."""
    from memory import conversation_store as cstore
    conv = conversation_id()
    text = render(cand, rng)
    meta = {"topic": cand.topic, "kind": cand.kind, "companion": True, "spoken": bool(spoken and not as_followup)}
    msg_id = cstore.add_message(conv, "assistant", text, source="companion", meta=meta)
    store.record_sent(msg_id, cand.topic, "followup" if as_followup else cand.kind, spoken=spoken, read=read, at=now)
    _publish_unread()
    return msg_id


# ------------------------------------------------------------------------------------------------ the person answers
def _is_answer(text: str) -> bool:
    words = text.strip().split()
    if not words or len(words) > 12 or "?" in text or words[0].lower().strip(",.!") in _QUESTION_WORDS:
        return False
    return text.strip().lower().strip(".! ") not in _NO


def clean_answer(text: str) -> str:
    out = text.strip().strip(".!")
    for _ in range(2):
        out = _LEAD.sub("", out)
    return out.strip(" ,;")


_THANKS = ("Good to know, thank you.", "Nice. I like knowing that about you.", "Got it, I'll remember that.",
           "Thanks, that helps me know you better.", "Ha, I like that.", "Good to hear.")
_SKIP = ("That's fine, no pressure.", "No problem, we can skip that one.", "All good, there's no wrong answer.")
_SPACE = "Okay, I'll give you some space."


def acknowledge(conv_id: Optional[str], text: str, rng: Optional[random.Random] = None) -> Optional[str]:
    """A short answer to something Seven just asked is a reply from a friend, not a prompt for the brain: on one word the
    brain guesses ("Couple" became an introduction of Seven). Returns Seven's reply, or None when the brain should answer
    (a question, a longer message, or nothing was asked). Call it before note_user_message, which marks the question answered."""
    if not is_companion(conv_id):
        return None
    last = store.last_sent_topic()
    if not last or last.get("answered"):
        return None
    rng = rng or random.Random()
    if len((text or "").split()) <= 12 and _STOP.search(text or ""):
        return _SPACE
    if (text or "").strip().lower().strip(".! ") in _NO:
        return rng.choice(_SKIP)
    return rng.choice(_THANKS) if _is_answer(text) else None


def note_user_message(conv_id: Optional[str], text: str, now: Optional[datetime.datetime] = None) -> None:
    """The person wrote in Seven's thread. Learn from it, and respect a "not now"."""
    if not is_companion(conv_id):
        return
    _learn(text, now or datetime.datetime.now())


def note_voice_message(text: str, now: Optional[datetime.datetime] = None) -> None:
    """The person said something to Seven aloud. It counts as talking to Seven; and if Seven asked something in the last
    few minutes, a short spoken reply is the answer."""
    now = now or datetime.datetime.now()
    try:
        from companion import scheduler
        scheduler.touch()
    except Exception:
        pass
    last = store.last_sent_topic()
    if not last or last["kind"] == "followup":
        return
    try:
        age = (now - datetime.datetime.strptime(last["created_at"], store.FMT)).total_seconds()
    except (ValueError, TypeError):
        return
    if age <= VOICE_ANSWER_WINDOW_S:
        _learn(text, now)


def _learn(text: str, now: datetime.datetime) -> None:
    try:
        from companion import scheduler
        scheduler.touch()
    except Exception:
        pass
    last = store.last_sent_topic()
    store.mark_all_answered(last["topic"] if last else None)
    if _STOP.search(text or ""):
        store.set_state("snooze_until", (now + datetime.timedelta(hours=SNOOZE_AFTER_NOT_NOW_H)).strftime(store.FMT))
        store.set_state("deepen", None)
        return
    store.set_state("deepen", None)
    cand = BY_TOPIC.get(last["topic"]) if last else None
    if last and last["topic"].startswith("goal."):
        cand = Candidate(last["topic"], "goal", "", deepen=None)
    if not cand or not _is_answer(text):
        return
    answer = clean_answer(text)
    if cand.fact and answer:
        try:
            from memory import facts_store
            facts_store.add_fact(cand.fact.format(a=answer), speaker_id=speaker_key(), category="personal", source_text=text)
        except Exception as exc:
            _log.debug("could not remember the answer: %s", exc)
    if cand.deepen:
        store.set_state("deepen", {"topic": cand.topic, "text": cand.deepen})


# ------------------------------------------------------------------------------------------------ asking back
def snoozed(now: datetime.datetime) -> bool:
    until = store.get_state("snooze_until")
    if not until:
        return False
    try:
        return now < datetime.datetime.strptime(until, store.FMT)
    except ValueError:
        return False


def follow_up(now: Optional[datetime.datetime] = None, rng: Optional[random.Random] = None,
              reply: str = "") -> Optional[int]:
    """One thing asked back, as a second message, after Seven answered in the thread. None when it is better to stay quiet.
    `reply` is what Seven just answered: if that already ends with a question, one question at a time is enough."""
    now = now or datetime.datetime.now()
    cfg = settings.get()
    if not cfg["enabled"] or snoozed(now):
        return None
    if not conversation_id(create=False):
        return None
    if (reply or "").rstrip().endswith("?"):
        return None                                   # the answer already asked something: one question at a time
    deepen = store.get_state("deepen")
    if deepen:
        store.set_state("deepen", None)
        cand = Candidate(f"{deepen['topic']}.deepen", "deepen", deepen["text"])
    else:
        cand = choose(now, rng, cfg, exclude_kinds=("care", "welcome"))
    if not cand:
        return None
    return post(cand, spoken=True, read=True, rng=rng, as_followup=True, now=now)   # the person is in the chat: written, not said


def after_reply(conv_id: Optional[str], user_text: str = "", delay: Optional[float] = None, reply: str = "",
                answered: bool = False) -> bool:
    """Schedule the follow-up a moment after Seven answers, so it reads like a second text and not part of the answer.
    `answered`: the person was answering a question, so even one word deserves the next one."""
    if not is_companion(conv_id) or _STOP.search(user_text or ""):
        return False
    if not answered and len((user_text or "").split()) < 2:
        return False
    wait = delay if delay is not None else random.uniform(1.6, 3.4)
    timer = threading.Timer(wait, lambda: _safe(lambda: follow_up(reply=reply)))
    timer.daemon = True
    timer.start()
    return True


def _safe(fn):
    try:
        fn()
    except Exception as exc:
        _log.warning("companion follow-up failed: %s", exc)


def nudge(now: Optional[datetime.datetime] = None, rng: Optional[random.Random] = None) -> Optional[int]:
    """The person pressed "Ask me something": one message now, written into the thread (they are looking at it)."""
    now = now or datetime.datetime.now()
    cand = choose(now, rng, settings.get(), exclude_kinds=("care", "welcome"))
    return post(cand, spoken=True, read=True, rng=rng, now=now) if cand else None
