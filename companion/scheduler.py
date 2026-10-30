"""
companion/scheduler.py

When Seven reaches out. A friend does not message on a timer, so the rules are about the person, not the clock:

    never        in quiet hours (set in the chat settings), while snoozed, while Seven is talking or thinking, or just
                 after launch (the first message waits a few minutes), and not while you are typing or using the mouse
    at a pace    a different number each day (3, 5 or 7) and 7 to 17 minutes apart by default (companion/settings.py),
                 twice as far apart once two messages in a row have gone unanswered, and none after three: it gives you space
    aloud        only when you are idle: paused for a moment (not typing) but still at the PC, and not in a conversation
                 with Seven. Otherwise the message waits in the chat as text and is said when you pause or come back
    on launch    anything written but not yet said is said right after the greeting

Every message is written into Seven's chat thread whether or not it is said. tick() is called every few seconds by a daemon
thread; all the outside world (time, idleness, speaking) comes in as arguments so tests can drive it exactly.
"""
import ctypes
import datetime
import logging
import random
import threading
import time
from typing import Callable, Optional

from companion import engine, settings, store

_log = logging.getLogger("seven.companion")

TICK_SECONDS = 15
IDLE_MIN = 20           # seconds without keyboard or mouse before Seven may speak (you have paused)
AWAY_AFTER = 600        # seconds without input after which you are away: written, not said, until you are back
SEVEN_IDLE = 90         # seconds since you last talked to Seven or typed in its chat
START_DELAY = 240       # seconds after launch before the first message
MAX_SPOKEN_AT_ONCE = 3

_last_touch = 0.0


def touch() -> None:
    """You just talked to Seven (said something, or wrote in its chat)."""
    global _last_touch
    _last_touch = time.time()


def system_idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input anywhere in Windows (0 where this cannot be read)."""
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return max(0.0, (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0)
    except Exception:
        pass
    return 0.0


class Companion:
    def __init__(self, speak: Optional[Callable[[str], object]] = None, busy: Optional[Callable[[], bool]] = None,
                 cfg: Optional[Callable[[], dict]] = None, clock: Callable[[], datetime.datetime] = datetime.datetime.now,
                 rng: Optional[random.Random] = None, idle: Callable[[], float] = system_idle_seconds,
                 since_touch: Callable[[], float] = lambda: time.time() - _last_touch):
        self.speak, self.busy = speak, busy or (lambda: False)
        self.cfg = cfg or settings.get
        self.clock, self.rng, self.idle, self.since_touch = clock, rng or random.Random(), idle, since_touch
        self.started_at = clock()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ the gate for a new message
    def blocked(self, now: datetime.datetime, cfg: dict) -> Optional[str]:
        """Why a new message may not be written right now, or None. (The words are for tests and logs.)"""
        if not cfg["enabled"]:
            return "off"
        if settings.in_quiet_hours(cfg, now):
            return "quiet"
        if engine.snoozed(now):
            return "snoozed"
        if (now - self.started_at).total_seconds() < START_DELAY:
            return "start"
        if self.busy():
            return "busy"
        if store.unspoken(1):
            return "waiting"              # one message at a time: say the one that is waiting before writing another
        if self.idle() < IDLE_MIN:
            return "active"
        if self.since_touch() < SEVEN_IDLE:
            return "talking"
        nxt = store.get_state("next_at")
        if nxt:
            try:
                if now < datetime.datetime.strptime(nxt, store.FMT):
                    return "gap"
            except ValueError:
                pass
        if store.sent_today(now.date()) >= settings.daily_target(cfg, now.date()):
            return "cap"
        if store.unanswered_streak() >= 3:
            return "space"
        return None

    def _schedule_next(self, now: datetime.datetime, cfg: dict) -> None:
        gap = settings.gap_minutes(cfg, self.rng) * (2 if store.unanswered_streak() >= 2 else 1)
        store.set_state("next_at", (now + datetime.timedelta(minutes=gap)).strftime(store.FMT))

    # ------------------------------------------------------------------ one pass
    def tick(self) -> Optional[str]:
        """Write a message if now is a good time, then say anything that is waiting. Returns 'wrote' or 'spoke' or None."""
        with self._lock:
            now, cfg = self.clock(), self.cfg()
            store.set_state("last_seen", now.strftime(store.FMT))
            did = None
            if self.blocked(now, cfg) is None:
                cand = engine.choose(now, self.rng, cfg)
                if cand:
                    engine.post(cand, spoken=not cfg["voice"], rng=self.rng, now=now)
                    self._schedule_next(now, cfg)
                    did = "wrote"
            if self.deliver(now, cfg):
                did = "spoke"
            return did

    # ------------------------------------------------------------------ saying what is waiting
    def can_speak(self, now: datetime.datetime, cfg: dict, launch: bool = False) -> bool:
        if not (cfg["enabled"] and cfg["voice"] and self.speak) or self.busy():
            return False
        if launch:
            return True                                   # you just opened Seven: you are here, and Seven is greeting you
        if settings.in_quiet_hours(cfg, now) or engine.snoozed(now):
            return False
        idle = self.idle()
        return IDLE_MIN <= idle <= AWAY_AFTER and self.since_touch() >= SEVEN_IDLE

    def deliver(self, now: Optional[datetime.datetime] = None, cfg: Optional[dict] = None, launch: bool = False) -> bool:
        """Say messages that were written but not yet said. True if anything was said."""
        from memory import conversation_store as cstore
        now, cfg = now or self.clock(), cfg or self.cfg()
        if not self.can_speak(now, cfg, launch):
            return False
        waiting = store.unspoken(MAX_SPOKEN_AT_ONCE)
        if not waiting:
            return False
        said = False
        for i, row in enumerate(waiting):
            msg = cstore.get_message(row["msg_id"])
            if not msg:
                store.mark_spoken(row["msg_id"])
                continue
            text = msg["content"]
            if i == 0 and (launch or _age_minutes(row["created_at"], now) > 20):
                lead = "I left you a few notes while you were away." if len(waiting) > 1 else "I left you a note while you were away."
                text = f"{lead} {text}"
            try:
                self.speak(text)
            except Exception as exc:
                _log.warning("companion could not speak: %s", exc)
                return said
            store.mark_spoken(row["msg_id"])
            meta = dict(_meta(msg), spoken=True)
            cstore.set_message_meta(row["msg_id"], meta)
            said = True
        return said


def _meta(msg: dict) -> dict:
    import json
    try:
        return json.loads(msg.get("meta") or "{}") or {}
    except (ValueError, TypeError):
        return {}


def _age_minutes(created_at: str, now: datetime.datetime) -> float:
    try:
        return (now - datetime.datetime.strptime(created_at, store.FMT)).total_seconds() / 60
    except (ValueError, TypeError):
        return 0.0


# ------------------------------------------------------------------------------------------------ running it
_instance: Optional[Companion] = None


def get() -> Optional[Companion]:
    return _instance


def start(speak: Callable[[str], object], busy: Callable[[], bool]) -> Companion:
    """Start the companion once per launch (voice_loop.py, after the greeting)."""
    global _instance
    if _instance is not None:
        return _instance
    previous = store.get_state("last_seen")
    store.set_state("previous_seen", previous)                # how long you were away, for a welcome back
    _instance = Companion(speak=speak, busy=busy)

    def loop():
        while True:
            time.sleep(TICK_SECONDS)
            try:
                _instance.tick()
            except Exception as exc:
                _log.warning("companion tick failed: %s", exc)

    threading.Thread(target=loop, daemon=True, name="Companion").start()
    return _instance
