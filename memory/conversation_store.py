"""
memory/conversation_store.py

Durable chat sessions and messages (SQLite, optional FTS5 search).

WHY THIS EXISTS:
    The old "conversation" was one Chroma document per exchange, capped at 7.
    There was no session, so "start a new chat" could not exist and history
    could not be searched or exported. A conversation is now a session with an
    id; messages are the permanent transcript. Facts, summaries and the
    semantic index are derived from it and link back to message ids.

GUARANTEES:
    - Nothing is deleted to make room. There is no count limit.
    - add_message() raises StorageUnavailable instead of pretending to save.
    - Search never loads the whole history; the model only ever sees a few
      retrieved snippets.
"""

import datetime
import json
import logging
import os
import re
import sqlite3
import threading
import uuid
from typing import Any, Dict, List, Optional

from memory import limits

_log = logging.getLogger("seven.conversations")

_lock = threading.Lock()
_override: Optional[str] = None
_ready_path: Optional[str] = None
_fts = False


class StorageUnavailable(Exception):
    """Raised when a message cannot be durably saved."""


def get_db_path() -> str:
    if _override:
        return _override
    env = os.environ.get("SEVEN_CONV_DB")
    if env:
        return env
    from memory import facts_store
    return os.path.join(os.path.dirname(facts_store.get_db_path()), "conversations.db")


def set_db_path(path: Optional[str]) -> None:
    global _override, _ready_path
    with _lock:
        _override, _ready_path = path, None


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(get_db_path(), timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _init() -> None:
    global _ready_path, _fts
    path = get_db_path()
    if _ready_path == path:
        return
    with _lock:
        if _ready_path == path:
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        c = _conn()
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, speaker_key TEXT NOT NULL, title TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                message_count INTEGER DEFAULT 0, summary TEXT, summarized_at TEXT,
                archived INTEGER DEFAULT 0)""")
            c.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL,
                source TEXT, meta TEXT)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_conv_speaker ON conversations(speaker_key, updated_at)")
            try:
                c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5("
                          "content, content='messages', content_rowid='id')")
                c.execute("""CREATE TRIGGER IF NOT EXISTS msg_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content); END""")
                c.execute("""CREATE TRIGGER IF NOT EXISTS msg_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content)
                    VALUES ('delete', old.id, old.content); END""")
                _fts = True
            except sqlite3.OperationalError:
                _fts = False
            c.commit()
        finally:
            c.close()
        _ready_path = path


def _rows(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    _init()
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
    finally:
        c.close()


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------

def create_conversation(speaker_key: str, title: Optional[str] = None) -> str:
    _init()
    cid, now = uuid.uuid4().hex[:12], _now()
    c = _conn()
    try:
        c.execute("INSERT INTO conversations (id, speaker_key, title, created_at, updated_at) "
                  "VALUES (?,?,?,?,?)", (cid, speaker_key, title, now, now))
        c.commit()
    finally:
        c.close()
    return cid


def get_conversation(conv_id: str) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM conversations WHERE id=?", (conv_id,))
    return rows[0] if rows else None


def current_conversation(speaker_key: str, max_idle_s: int = 6 * 3600) -> str:
    """Latest conversation for this speaker, or a new one if it has gone cold."""
    rows = _rows("SELECT id, updated_at FROM conversations WHERE speaker_key=? AND archived=0 "
                 "ORDER BY updated_at DESC, rowid DESC LIMIT 1", (speaker_key,))
    if rows:
        try:
            age = (datetime.datetime.now() - datetime.datetime.strptime(
                rows[0]["updated_at"], "%Y-%m-%d %H:%M:%S")).total_seconds()
            if age <= max_idle_s:
                return rows[0]["id"]
        except ValueError:
            return rows[0]["id"]
    return create_conversation(speaker_key)


def ensure(speaker_key: str, conv_id: Optional[str] = None) -> str:
    """Validate a client-supplied id, or fall back to the current conversation."""
    if conv_id:
        conv = get_conversation(conv_id)
        if conv and conv["speaker_key"] == speaker_key:
            return conv_id
    return current_conversation(speaker_key)


def rename(conv_id: str, title: str) -> bool:
    _init()
    c = _conn()
    try:
        cur = c.execute("UPDATE conversations SET title=? WHERE id=?", (title.strip()[:120], conv_id))
        c.commit()
        return cur.rowcount > 0
    finally:
        c.close()


def delete_conversation(conv_id: str) -> bool:
    _init()
    c = _conn()
    try:
        c.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
        cur = c.execute("DELETE FROM conversations WHERE id=?", (conv_id,))
        c.commit()
        return cur.rowcount > 0
    finally:
        c.close()


def delete_all(speaker_key: str) -> int:
    n = 0
    for conv in _rows("SELECT id FROM conversations WHERE speaker_key=?", (speaker_key,)):
        n += 1 if delete_conversation(conv["id"]) else 0
    return n


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------

def add_message(conv_id: str, role: str, content: str, source: str = "chat",
                meta: Optional[dict] = None, ts: Optional[str] = None) -> int:
    """Durably save a message. Raises StorageUnavailable; never fails silently."""
    text = (content or "").strip()
    if not text:
        raise StorageUnavailable("empty message")
    ok, why = limits.can_write(get_db_path())
    if not ok:
        raise StorageUnavailable(why)
    try:
        _init()
        c = _conn()
        try:
            now = ts or _now()
            cur = c.execute("INSERT INTO messages (conversation_id, role, content, ts, source, meta) "
                            "VALUES (?,?,?,?,?,?)",
                            (conv_id, role, text, now, source, json.dumps(meta) if meta else None))
            from brain_modules import speech_acts
            title = (re.sub(r"\s+", " ", text)[:48] if role == "user" and len(text) > 3
                     and not speech_acts.is_greeting(speech_acts.normalize(text)) else None)
            c.execute("UPDATE conversations SET updated_at=?, message_count=message_count+1, "
                      "title=COALESCE(title, ?) WHERE id=?", (now, title, conv_id))
            c.commit()
            return cur.lastrowid
        finally:
            c.close()
    except sqlite3.Error as exc:
        raise StorageUnavailable(f"could not save the message ({exc})")


def get_messages(conv_id: str, limit: int = 200, before_id: Optional[int] = None) -> List[Dict[str, Any]]:
    if before_id:
        rows = _rows("SELECT * FROM messages WHERE conversation_id=? AND id<? ORDER BY id DESC LIMIT ?",
                     (conv_id, before_id, limit))
        return list(reversed(rows))
    rows = _rows("SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?", (conv_id, limit))
    return list(reversed(rows))


def get_message(msg_id: int) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT m.*, c.title AS conversation_title FROM messages m "
                 "JOIN conversations c ON c.id=m.conversation_id WHERE m.id=?", (msg_id,))
    return rows[0] if rows else None


def list_conversations(speaker_key: Optional[str], limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Conversations for one speaker, or for everyone when speaker_key is None (the Memory page)."""
    cols = ("SELECT id, title, created_at, updated_at, message_count, summary, speaker_key, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=conversations.id AND m.source='voice') "
            "AS voice_count FROM conversations ")
    if speaker_key is None:
        return _rows(cols + "WHERE archived=0 AND message_count>0 ORDER BY updated_at DESC, rowid DESC LIMIT ? OFFSET ?",
                     (limit, offset))
    return _rows(cols + "WHERE speaker_key=? AND archived=0 AND message_count>0 "
                 "ORDER BY updated_at DESC, rowid DESC LIMIT ? OFFSET ?", (speaker_key, limit, offset))


def search(speaker_key: Optional[str], query: str, limit: int = 20,
           exclude_conv: Optional[str] = None) -> List[Dict[str, Any]]:
    """Find messages across every conversation (of one speaker, or everyone when None). FTS5 or LIKE."""
    terms = [t for t in re.findall(r"[A-Za-z0-9]+", query or "") if len(t) > 1]
    if not terms:
        return []
    _init()
    excl = exclude_conv or ""
    who = "c.speaker_key=?" if speaker_key is not None else "(?='' OR 1=1)"
    speaker_key = speaker_key if speaker_key is not None else ""
    if _fts:
        match = " OR ".join(f'"{t}"' for t in terms[:8])
        try:
            return _rows(
                "SELECT m.id, m.conversation_id, m.role, m.content, m.ts, m.source, c.title FROM messages_fts f "
                "JOIN messages m ON m.id=f.rowid JOIN conversations c ON c.id=m.conversation_id "
                f"WHERE messages_fts MATCH ? AND {who} AND c.id!=? "
                "ORDER BY rank LIMIT ?", (match, speaker_key, excl, limit))
        except sqlite3.OperationalError:
            pass
    like = " OR ".join("m.content LIKE ?" for _ in terms[:8])
    params = tuple(f"%{t}%" for t in terms[:8]) + (speaker_key, excl, limit)
    return _rows("SELECT m.id, m.conversation_id, m.role, m.content, m.ts, m.source, c.title FROM messages m "
                 f"JOIN conversations c ON c.id=m.conversation_id WHERE ({like}) AND {who} "
                 "AND c.id!=? ORDER BY m.id DESC LIMIT ?", params)


def count_conversations(speaker_key: Optional[str] = None) -> int:
    if speaker_key:
        rows = _rows("SELECT COUNT(*) AS n FROM conversations WHERE speaker_key=? AND message_count>0",
                     (speaker_key,))
    else:
        rows = _rows("SELECT COUNT(*) AS n FROM conversations WHERE message_count>0")
    return rows[0]["n"]


def count_messages() -> int:
    return _rows("SELECT COUNT(*) AS n FROM messages")[0]["n"]


def activity() -> Dict[str, Any]:
    """Message counts by role and source, and the first and last message times (for the Memory page)."""
    _init()
    rows = _rows("SELECT role, COALESCE(source, 'chat') AS source, COUNT(*) AS n, MIN(ts) AS first, MAX(ts) AS last "
                 "FROM messages GROUP BY role, COALESCE(source, 'chat')")
    out = {"messages": 0, "from_user": 0, "by_source": {}, "first_at": None, "last_at": None}
    for r in rows:
        out["messages"] += r["n"]
        if r["role"] == "user":
            out["from_user"] += r["n"]
            out["by_source"][r["source"]] = out["by_source"].get(r["source"], 0) + r["n"]
        out["first_at"] = min(filter(None, [out["first_at"], r["first"]]), default=None)
        out["last_at"] = max(filter(None, [out["last_at"], r["last"]]), default=None)
    return out


def delete_everything() -> int:
    """Delete every conversation for every speaker. Returns how many were removed."""
    n = 0
    for conv in _rows("SELECT id FROM conversations"):
        n += 1 if delete_conversation(conv["id"]) else 0
    return n


def export_all() -> List[Dict[str, Any]]:
    """Every conversation of every speaker with all its messages, oldest first: what a backup keeps."""
    out = []
    for conv in _rows("SELECT * FROM conversations ORDER BY created_at, id"):
        conv["messages"] = _rows("SELECT role, content, ts, source, meta FROM messages WHERE conversation_id=? "
                                 "ORDER BY id", (conv["id"],))
        out.append(conv)
    return out


def import_conversation(conv: Dict[str, Any], speaker_key: Optional[str] = None) -> int:
    """
    Restore one conversation from a backup, keeping its id, title, times and messages. A conversation whose id is
    already here is skipped, so importing the same file twice adds nothing. Returns the messages restored (0 if skipped).
    """
    msgs = [m for m in (conv.get("messages") or []) if isinstance(m, dict) and str(m.get("content") or "").strip()]
    if not msgs:
        return 0
    _init()
    cid = str(conv.get("id") or uuid.uuid4().hex[:12])
    now = _now()
    c = _conn()
    try:
        if c.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
            return 0
        created = conv.get("created_at") or msgs[0].get("ts") or now
        c.execute("INSERT INTO conversations (id, speaker_key, title, created_at, updated_at, message_count, summary, "
                  "summarized_at, archived) VALUES (?,?,?,?,?,?,?,?,?)",
                  (cid, speaker_key or conv.get("speaker_key") or "default", conv.get("title"), created,
                   conv.get("updated_at") or msgs[-1].get("ts") or created, len(msgs), conv.get("summary"),
                   conv.get("summarized_at"), 1 if conv.get("archived") else 0))
        for m in msgs:
            meta = m.get("meta")
            c.execute("INSERT INTO messages (conversation_id, role, content, ts, source, meta) VALUES (?,?,?,?,?,?)",
                      (cid, m.get("role") or "user", str(m["content"]).strip(), m.get("ts") or created,
                       m.get("source") or "chat", meta if isinstance(meta, str) or meta is None else json.dumps(meta)))
        c.commit()
        return len(msgs)
    finally:
        c.close()


def export(conv_id: Optional[str] = None, speaker_key: Optional[str] = None) -> Dict[str, Any]:
    """Full transcript(s) as plain data, for the user's own backup."""
    convs = [get_conversation(conv_id)] if conv_id else _rows(
        "SELECT * FROM conversations WHERE speaker_key=? ORDER BY created_at", (speaker_key or "",))
    out = []
    for conv in filter(None, convs):
        conv["messages"] = get_messages(conv["id"], limit=1_000_000)
        out.append(conv)
    return {"exported_at": _now(), "conversations": out}


def set_summary(conv_id: str, summary: str) -> None:
    _init()
    c = _conn()
    try:
        c.execute("UPDATE conversations SET summary=?, summarized_at=? WHERE id=?", (summary, _now(), conv_id))
        c.commit()
    finally:
        c.close()


def unsummarized(min_idle_s: int = 1800, limit: int = 20) -> List[Dict[str, Any]]:
    cutoff = (datetime.datetime.now() - datetime.timedelta(seconds=min_idle_s)).strftime("%Y-%m-%d %H:%M:%S")
    return _rows("SELECT * FROM conversations WHERE message_count>=2 AND summary IS NULL "
                 "AND updated_at<=? ORDER BY updated_at LIMIT ?", (cutoff, limit))


def rename_speaker(old: str, new: str) -> int:
    if not old or not new or old == new:
        return 0
    _init()
    c = _conn()
    try:
        cur = c.execute("UPDATE conversations SET speaker_key=? WHERE speaker_key=?", (new, old))
        c.commit()
        return cur.rowcount
    finally:
        c.close()
