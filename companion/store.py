"""
companion/store.py

What the companion has sent, asked and answered. A small SQLite file next to the chats. The messages themselves live in
the chat thread (memory/conversation_store.py); this file only knows how each one was delivered and what came of it, so
Seven never repeats a question, never nags, and can say unread messages when you come back.
"""
import datetime
import json
import os
import sqlite3
import threading
from typing import Any, List, Optional

_lock = threading.Lock()
_override: Optional[str] = None
_ready: Optional[str] = None

FMT = "%Y-%m-%d %H:%M:%S"


def get_db_path() -> str:
    if _override:
        return _override
    env = os.environ.get("SEVEN_COMPANION_DB")
    if env:
        return env
    from memory import conversation_store
    return os.path.join(os.path.dirname(conversation_store.get_db_path()), "companion.db")


def set_db_path(path: Optional[str]) -> None:
    global _override, _ready
    with _lock:
        _override, _ready = path, None


def _now() -> str:
    return datetime.datetime.now().strftime(FMT)


def _conn() -> sqlite3.Connection:
    global _ready
    path = get_db_path()
    if _ready != path:
        with _lock:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            c = sqlite3.connect(path, timeout=10.0)
            try:
                c.execute("CREATE TABLE IF NOT EXISTS sent (msg_id INTEGER PRIMARY KEY, topic TEXT, kind TEXT, "
                          "created_at TEXT, spoken INTEGER DEFAULT 0, read INTEGER DEFAULT 0, answered INTEGER DEFAULT 0)")
                c.execute("CREATE TABLE IF NOT EXISTS asked (topic TEXT PRIMARY KEY, last_at TEXT, times INTEGER DEFAULT 0, "
                          "answered INTEGER DEFAULT 0)")
                c.execute("CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT)")
                c.commit()
            finally:
                c.close()
            _ready = path
    c = sqlite3.connect(path, timeout=10.0)
    c.row_factory = sqlite3.Row
    return c


def _run(sql: str, params: tuple = ()) -> None:
    c = _conn()
    try:
        c.execute(sql, params)
        c.commit()
    finally:
        c.close()


def _rows(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    c = _conn()
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


# ------------------------------------------------------------------ state (small values)
def get_state(key: str, default: Any = None) -> Any:
    rows = _rows("SELECT v FROM state WHERE k=?", (key,))
    if not rows:
        return default
    try:
        return json.loads(rows[0]["v"])
    except (ValueError, TypeError):
        return default


def set_state(key: str, value: Any) -> None:
    _run("INSERT INTO state (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, json.dumps(value)))


# ------------------------------------------------------------------ messages sent
def record_sent(msg_id: int, topic: str, kind: str, spoken: bool = False, read: bool = False,
                at: Optional[datetime.datetime] = None) -> None:
    stamp = (at or datetime.datetime.now()).strftime(FMT)
    _run("INSERT OR REPLACE INTO sent (msg_id, topic, kind, created_at, spoken, read, answered) VALUES (?,?,?,?,?,?,0)",
         (msg_id, topic, kind, stamp, int(spoken), int(read)))
    _run("INSERT INTO asked (topic, last_at, times, answered) VALUES (?,?,1,0) "
         "ON CONFLICT(topic) DO UPDATE SET last_at=excluded.last_at, times=times+1", (topic, stamp))


def mark_spoken(msg_id: int) -> None:
    _run("UPDATE sent SET spoken=1 WHERE msg_id=?", (msg_id,))


def mark_read_all() -> int:
    c = _conn()
    try:
        n = c.execute("UPDATE sent SET read=1 WHERE read=0").rowcount
        c.commit()
        return n
    finally:
        c.close()


def unread_count() -> int:
    return _rows("SELECT COUNT(*) AS n FROM sent WHERE read=0")[0]["n"]


def unspoken(limit: int = 10) -> List[dict]:
    """Messages written but not yet said aloud, oldest first."""
    return [dict(r) for r in _rows("SELECT msg_id, topic, kind, created_at FROM sent WHERE spoken=0 AND kind<>'followup' "
                                   "ORDER BY msg_id LIMIT ?", (limit,))]


def mark_all_answered(topic_answered: Optional[str] = None) -> None:
    """The person wrote back: nothing sent so far is waiting for a reply any more."""
    _run("UPDATE sent SET answered=1 WHERE answered=0")
    if topic_answered:
        _run("UPDATE asked SET answered=1 WHERE topic=?", (topic_answered,))


def unanswered_streak() -> int:
    """How many of Seven's own messages in a row went unanswered (follow-ups to a reply don't count)."""
    return _rows("SELECT COUNT(*) AS n FROM sent WHERE answered=0 AND kind<>'followup'")[0]["n"]


def last_sent_topic() -> Optional[dict]:
    rows = _rows("SELECT msg_id, topic, kind, created_at FROM sent ORDER BY msg_id DESC LIMIT 1")
    return dict(rows[0]) if rows else None


def recent_kinds(n: int = 3) -> List[str]:
    return [r["kind"] for r in _rows("SELECT kind FROM sent WHERE kind<>'followup' ORDER BY msg_id DESC LIMIT ?", (n,))]


def sent_today(day: Optional[datetime.date] = None) -> int:
    day = (day or datetime.date.today()).strftime("%Y-%m-%d")
    return _rows("SELECT COUNT(*) AS n FROM sent WHERE created_at LIKE ? AND kind<>'followup'", (day + "%",))[0]["n"]


def topic_last_asked(topic: str) -> Optional[datetime.datetime]:
    rows = _rows("SELECT last_at FROM asked WHERE topic=?", (topic,))
    if not rows:
        return None
    try:
        return datetime.datetime.strptime(rows[0]["last_at"], FMT)
    except (ValueError, TypeError):
        return None


def clear_all() -> None:
    for table in ("sent", "asked", "state"):
        _run(f"DELETE FROM {table}")
