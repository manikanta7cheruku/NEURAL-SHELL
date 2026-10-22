"""
memory/learning_store.py

Small SQLite store for what Seven learns ABOUT ITS OWN PERFORMANCE and the
user's open threads: knowledge gaps (things worth asking), outcomes (verified
successes, failures, corrections), goals, and entity mention counts.

Kept separate from facts (what the user said) so that a measured outcome or a
guess can never be mistaken for something the user told Seven.
"""

import datetime
import json
import logging
import os
import re
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("seven.learning_store")
_lock = threading.Lock()
_override: Optional[str] = None
_ready: Optional[str] = None


def get_db_path() -> str:
    if _override:
        return _override
    env = os.environ.get("SEVEN_LEARNING_DB")
    if env:
        return env
    from memory import facts_store
    return os.path.join(os.path.dirname(facts_store.get_db_path()), "learning.db")


def set_db_path(path: Optional[str]) -> None:
    global _override, _ready
    with _lock:
        _override, _ready = path, None


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(get_db_path(), timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _init() -> None:
    global _ready
    path = get_db_path()
    if _ready == path:
        return
    with _lock:
        if _ready == path:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        c = _conn()
        try:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT, speaker_key TEXT NOT NULL, kind TEXT NOT NULL,
                subject TEXT NOT NULL, payload TEXT, status TEXT DEFAULT 'open', priority INTEGER DEFAULT 5,
                created_at TEXT, asked_at TEXT, answered_at TEXT, UNIQUE(speaker_key, kind, subject));
            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, speaker_key TEXT, kind TEXT NOT NULL,
                subject TEXT NOT NULL, status TEXT NOT NULL, detail TEXT, conversation_id TEXT);
            CREATE INDEX IF NOT EXISTS idx_outcomes_subject ON outcomes(kind, subject, id);
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, speaker_key TEXT NOT NULL, key TEXT NOT NULL,
                title TEXT NOT NULL, status TEXT DEFAULT 'active', origin TEXT DEFAULT 'explicit',
                deadline_text TEXT, detail TEXT, created_at TEXT, updated_at TEXT,
                mentions INTEGER DEFAULT 1, source_msg_id INTEGER, UNIQUE(speaker_key, key));
            CREATE TABLE IF NOT EXISTS mentions (
                speaker_key TEXT, entity TEXT, count INTEGER DEFAULT 0, last_ts TEXT,
                PRIMARY KEY(speaker_key, entity));
            """)
            c.commit()
        finally:
            c.close()
        _ready = path


def _rows(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    _init()
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
    finally:
        c.close()


def _exec(sql: str, params: tuple = ()) -> int:
    _init()
    c = _conn()
    try:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid or cur.rowcount
    finally:
        c.close()


# ---- gaps ---------------------------------------------------------------

def add_gap(speaker_key: str, kind: str, subject: str, payload: Optional[dict] = None,
            priority: int = 5) -> Optional[int]:
    """Record something worth asking about. Returns None if it already exists."""
    _init()
    c = _conn()
    try:
        cur = c.execute("INSERT OR IGNORE INTO gaps (speaker_key, kind, subject, payload, priority, created_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (speaker_key, kind, subject, json.dumps(payload or {}), priority, _now()))
        c.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        c.close()


def next_gap(speaker_key: str) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM gaps WHERE speaker_key=? AND status='open' "
                 "ORDER BY priority DESC, id ASC LIMIT 1", (speaker_key,))
    if rows:
        rows[0]["payload"] = json.loads(rows[0]["payload"] or "{}")
    return rows[0] if rows else None


def get_gap(gap_id: int) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM gaps WHERE id=?", (gap_id,))
    if rows:
        rows[0]["payload"] = json.loads(rows[0]["payload"] or "{}")
    return rows[0] if rows else None


def set_gap_status(gap_id: int, status: str) -> None:
    col = {"asked": "asked_at", "answered": "answered_at"}.get(status)
    if col:
        _exec(f"UPDATE gaps SET status=?, {col}=? WHERE id=?", (status, _now(), gap_id))
    else:
        _exec("UPDATE gaps SET status=? WHERE id=?", (status, gap_id))


def list_gaps(speaker_key: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    if status:
        return _rows("SELECT * FROM gaps WHERE speaker_key=? AND status=? ORDER BY id", (speaker_key, status))
    return _rows("SELECT * FROM gaps WHERE speaker_key=? ORDER BY id", (speaker_key,))


def expire_old_gaps(days: int = 30) -> int:
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    return _exec("UPDATE gaps SET status='expired' WHERE status='open' AND created_at<?", (cutoff,))


# ---- outcomes -----------------------------------------------------------

def record_outcome(speaker_key: str, kind: str, subject: str, status: str,
                   detail: Optional[str] = None, conversation_id: Optional[str] = None) -> None:
    """kind: action | answer | routing | question | feedback. status: success | failed | unconfirmed | corrected | up | down."""
    try:
        _exec("INSERT INTO outcomes (ts, speaker_key, kind, subject, status, detail, conversation_id) "
              "VALUES (?,?,?,?,?,?,?)", (_now(), speaker_key, kind, subject, status, (detail or "")[:300], conversation_id))
    except sqlite3.Error as exc:
        _log.debug("outcome not recorded: %s", exc)


def reliability(kind: str, subject: str, window: int = 10) -> Dict[str, Any]:
    """Recent success/failure picture for one tool or target."""
    rows = _rows("SELECT status FROM outcomes WHERE kind=? AND subject=? ORDER BY id DESC LIMIT ?",
                 (kind, subject, window))
    failed = sum(1 for r in rows if r["status"] == "failed")
    ok = sum(1 for r in rows if r["status"] == "success")
    return {"total": len(rows), "failed": failed, "success": ok,
            "failure_rate": (failed / len(rows)) if rows else 0.0,
            "last": rows[0]["status"] if rows else None}


def recent_outcomes(limit: int = 50) -> List[Dict[str, Any]]:
    return _rows("SELECT * FROM outcomes ORDER BY id DESC LIMIT ?", (limit,))


# ---- goals --------------------------------------------------------------

def _tokens(text: str) -> set:
    stop = {"a", "an", "the", "to", "my", "of", "and", "for", "in", "on", "is", "it", "i", "called"}
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in stop}


def upsert_goal(speaker_key: str, key: str, title: str, origin: str = "explicit",
                deadline_text: Optional[str] = None, source_msg_id: Optional[int] = None) -> Tuple[int, str]:
    """Create or refresh a goal. Near-duplicate titles merge into one goal."""
    for g in list_goals(speaker_key, status=None):
        a, b = _tokens(g["title"]), _tokens(title)
        if g["key"] == key or (a and b and len(a & b) / len(a | b) >= 0.6):
            _exec("UPDATE goals SET mentions=mentions+1, updated_at=?, "
                  "status=CASE WHEN status='dropped' THEN 'active' ELSE status END, "
                  "deadline_text=COALESCE(?, deadline_text) WHERE id=?", (_now(), deadline_text, g["id"]))
            return g["id"], "updated"
    gid = _exec("INSERT INTO goals (speaker_key, key, title, origin, deadline_text, created_at, updated_at, source_msg_id) "
                "VALUES (?,?,?,?,?,?,?,?)", (speaker_key, key, title, origin, deadline_text, _now(), _now(), source_msg_id))
    return gid, "created"


def list_goals(speaker_key: str, status: Optional[str] = "active") -> List[Dict[str, Any]]:
    if status:
        return _rows("SELECT * FROM goals WHERE speaker_key=? AND status=? ORDER BY updated_at DESC",
                     (speaker_key, status))
    return _rows("SELECT * FROM goals WHERE speaker_key=? ORDER BY updated_at DESC", (speaker_key,))


def get_goal(goal_id: int) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM goals WHERE id=?", (goal_id,))
    return rows[0] if rows else None


def set_goal_status(goal_id: int, status: str) -> None:
    _exec("UPDATE goals SET status=?, updated_at=? WHERE id=?", (status, _now(), goal_id))


def set_goal_detail(goal_id: int, detail: str) -> None:
    _exec("UPDATE goals SET detail=?, updated_at=? WHERE id=?", (detail[:300], _now(), goal_id))


def find_goal(speaker_key: str, text: str, status: Optional[str] = "active") -> Optional[Dict[str, Any]]:
    wanted, best, score = _tokens(text), None, 0.0
    for g in list_goals(speaker_key, status):
        have = _tokens(g["title"])
        if not wanted or not have:
            continue
        s = len(wanted & have) / len(wanted | have)
        if s > score:
            best, score = g, s
    return best if score >= 0.2 else None


# ---- mentions -----------------------------------------------------------

def bump_mention(speaker_key: str, entity: str) -> int:
    _init()
    c = _conn()
    try:
        c.execute("INSERT INTO mentions (speaker_key, entity, count, last_ts) VALUES (?,?,1,?) "
                  "ON CONFLICT(speaker_key, entity) DO UPDATE SET count=count+1, last_ts=excluded.last_ts",
                  (speaker_key, entity.lower(), _now()))
        c.commit()
        return c.execute("SELECT count FROM mentions WHERE speaker_key=? AND entity=?",
                         (speaker_key, entity.lower())).fetchone()["count"]
    finally:
        c.close()


def clear_speaker(speaker_key: str) -> None:
    for table in ("gaps", "goals", "mentions"):
        _exec(f"DELETE FROM {table} WHERE speaker_key=?", (speaker_key,))
    _exec("DELETE FROM outcomes WHERE speaker_key=?", (speaker_key,))


def rename_speaker(old: str, new: str) -> None:
    if not old or not new or old == new:
        return
    for table in ("gaps", "goals", "outcomes"):
        _exec(f"UPDATE OR IGNORE {table} SET speaker_key=? WHERE speaker_key=?", (new, old))
    _exec("UPDATE OR IGNORE mentions SET speaker_key=? WHERE speaker_key=?", (new, old))
