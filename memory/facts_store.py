"""
memory/facts_store.py

Structured SQLite facts store. This is Seven's SOURCE OF TRUTH for facts.
ChromaDB is only a semantic INDEX derived from it (see memory/fact_service.py).

WHY SQLITE IS THE TRUTH:
    Keeping two stores "transactional" with rollback across both is fragile.
    Instead every write is one atomic SQLite transaction. A row is flagged
    `indexed=0` until the ChromaDB document exists; a background job retries
    until the two agree. Chroma can be wiped and rebuilt at any time.

SLOTS:
    `key` is the slot ("favorite_framework", "likes:pizza"). Upserting a new
    value into a slot supersedes the old row and keeps the chain for history.

Columns kept from the previous schema (value = full sentence) so the older
readers keep working. New columns are added by an in-place migration.
"""

import datetime
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

_log = logging.getLogger("seven.facts")

_init_lock = threading.Lock()
_initialized = False
_db_path_override: Optional[str] = None

_NEW_COLUMNS = {
    "raw_value": "TEXT",
    "confidence": "REAL DEFAULT 0.8",
    "mentions": "INTEGER DEFAULT 1",
    "indexed": "INTEGER DEFAULT 0",
    "chroma_id": "TEXT",
}


def _default_db_path() -> str:
    """Same location rules as memory/core.py so both stores live side by side."""
    local_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seven_data", "memory")
    if os.path.exists(os.path.join(local_path, "chroma.sqlite3")):
        return os.path.join(local_path, "facts_structured.db")
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        path = os.path.join(appdata, "SEVEN", "seven_data", "memory")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "facts_structured.db")
    os.makedirs(local_path, exist_ok=True)
    return os.path.join(local_path, "facts_structured.db")


def get_db_path() -> str:
    """Resolve the database path (env override, test override, or default)."""
    if _db_path_override:
        return _db_path_override
    return os.environ.get("SEVEN_FACTS_DB") or _default_db_path()


def set_db_path(path: Optional[str]) -> None:
    """Point the store at another file. Used by tests; forces schema re-init."""
    global _db_path_override, _initialized
    with _init_lock:
        _db_path_override = path
        _initialized = False


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_conn() -> sqlite3.Connection:
    """New connection per call: thread-safe without sharing handles."""
    conn = sqlite3.connect(get_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_schema() -> None:
    """Create tables and migrate older databases in place. Idempotent."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn = _get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id    TEXT NOT NULL,
                    category      TEXT NOT NULL,
                    key           TEXT,
                    value         TEXT NOT NULL,
                    source_text   TEXT,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    superseded_by INTEGER,
                    active        INTEGER DEFAULT 1
                )""")
            existing = {r["name"] for r in conn.execute("PRAGMA table_info(facts)").fetchall()}
            for col, ddl in _NEW_COLUMNS.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE facts ADD COLUMN {col} {ddl}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_speaker ON facts(speaker_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_slot ON facts(speaker_id, key, active)")
            conn.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            conn.commit()
            _initialized = True
        finally:
            conn.close()


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def upsert_fact(speaker_id: str, key: str, raw_value: str, text: str,
                category: str = "general", source_text: Optional[str] = None,
                confidence: float = 0.8) -> Dict[str, Any]:
    """
    Atomically write a value into a slot.

    Returns a dict:
        status   "created" | "updated" | "unchanged"
        id       row id of the active fact
        previous previous raw value when status == "updated"
        old_id / old_chroma_id  superseded row, so its index doc can be removed
    """
    if not key or not raw_value or not text:
        raise ValueError("key, raw_value and text are required")
    _init_schema()
    conn = _get_conn()
    conn.isolation_level = None  # manual transaction control
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = _now()
        row = conn.execute(
            "SELECT * FROM facts WHERE speaker_id=? AND key=? AND active=1 ORDER BY id DESC LIMIT 1",
            (speaker_id, key)).fetchone()

        if row and (row["raw_value"] or "").strip().casefold() == raw_value.strip().casefold():
            conn.execute(
                "UPDATE facts SET mentions=COALESCE(mentions,1)+1, updated_at=?, "
                "confidence=MAX(COALESCE(confidence,0), ?) WHERE id=?",
                (now, confidence, row["id"]))
            conn.execute("COMMIT")
            return {"status": "unchanged", "id": row["id"], "previous": None,
                    "old_id": None, "old_chroma_id": None}

        cur = conn.execute(
            "INSERT INTO facts (speaker_id, category, key, value, raw_value, source_text, "
            "created_at, updated_at, confidence, mentions, indexed, active) "
            "VALUES (?,?,?,?,?,?,?,?,?,1,0,1)",
            (speaker_id, category, key, text.strip(), raw_value.strip(), source_text, now, now, confidence))
        new_id = cur.lastrowid
        if row:
            conn.execute("UPDATE facts SET active=0, superseded_by=?, updated_at=? WHERE id=?",
                         (new_id, now, row["id"]))
        conn.execute("COMMIT")
        return {"status": "updated" if row else "created", "id": new_id,
                "previous": row["raw_value"] if row else None,
                "old_id": row["id"] if row else None,
                "old_chroma_id": row["chroma_id"] if row else None}
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def add_fact(value: str, speaker_id: str = "default", category: str = "general",
             key: Optional[str] = None, source_text: Optional[str] = None) -> int:
    """Legacy API: insert an active fact without slot semantics."""
    if not value or not value.strip():
        raise ValueError("Fact value cannot be empty")
    _init_schema()
    conn = _get_conn()
    try:
        now = _now()
        cur = conn.execute(
            "INSERT INTO facts (speaker_id, category, key, value, raw_value, source_text, "
            "created_at, updated_at, indexed, active) VALUES (?,?,?,?,?,?,?,?,0,1)",
            (speaker_id, category, key, value.strip(), value.strip(), source_text, now, now))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def supersede_fact(old_id: int, new_value: str, source_text: Optional[str] = None) -> Optional[int]:
    """Legacy API: deactivate a fact and link it to a replacement."""
    _init_schema()
    conn = _get_conn()
    try:
        row = conn.execute("SELECT speaker_id, category, key FROM facts WHERE id=? AND active=1",
                           (old_id,)).fetchone()
        if not row:
            return None
        now = _now()
        cur = conn.execute(
            "INSERT INTO facts (speaker_id, category, key, value, raw_value, source_text, "
            "created_at, updated_at, indexed, active) VALUES (?,?,?,?,?,?,?,?,0,1)",
            (row["speaker_id"], row["category"], row["key"], new_value.strip(), new_value.strip(),
             source_text, now, now))
        new_id = cur.lastrowid
        conn.execute("UPDATE facts SET active=0, superseded_by=?, updated_at=? WHERE id=?",
                     (new_id, now, old_id))
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_fact(fact_id: int, new_value: str) -> bool:
    """Legacy API: change a fact's sentence in place."""
    _init_schema()
    conn = _get_conn()
    try:
        cur = conn.execute("UPDATE facts SET value=?, updated_at=?, indexed=0 WHERE id=? AND active=1",
                           (new_value.strip(), _now(), fact_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def deactivate(fact_id: int) -> bool:
    """Soft delete. History is kept; the fact stops being recalled."""
    _init_schema()
    conn = _get_conn()
    try:
        cur = conn.execute("UPDATE facts SET active=0, updated_at=? WHERE id=?", (_now(), fact_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_fact(fact_id: int) -> bool:
    """Hard delete a fact row."""
    _init_schema()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM facts WHERE id=?", (fact_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def mark_indexed(fact_id: int, chroma_id: str) -> None:
    """Record that the semantic index document now exists."""
    _init_schema()
    conn = _get_conn()
    try:
        conn.execute("UPDATE facts SET indexed=1, chroma_id=? WHERE id=?", (chroma_id, fact_id))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def _rows(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    _init_schema()
    conn = _get_conn()
    try:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def get_by_id(fact_id: int) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM facts WHERE id=?", (fact_id,))
    return rows[0] if rows else None


def get_active_by_key(speaker_id: str, key: str) -> Optional[Dict[str, Any]]:
    rows = _rows("SELECT * FROM facts WHERE speaker_id=? AND key=? AND active=1 "
                 "ORDER BY id DESC LIMIT 1", (speaker_id, key))
    return rows[0] if rows else None


def find_by_attr(speaker_id: str, slug_key: str, aliases: tuple = ()) -> Optional[Dict[str, Any]]:
    """
    Find the best active fact for an attribute: exact slot, then aliases,
    then any slot whose words contain all words of the query ("framework"
    matches "favorite_framework").
    """
    for k in (slug_key, *aliases):
        row = get_active_by_key(speaker_id, k)
        if row:
            return row
    wanted = set(slug_key.split("_"))
    best = None
    for r in all_active(speaker_id):
        key = r.get("key") or ""
        if ":" in key or r.get("category") == "style":
            continue
        if wanted and wanted <= set(key.split("_")):
            if best is None or r["updated_at"] > best["updated_at"]:
                best = r
    return best


def list_by_prefix(speaker_id: str, prefix: str) -> List[Dict[str, Any]]:
    return _rows("SELECT * FROM facts WHERE speaker_id=? AND active=1 AND key LIKE ? "
                 "ORDER BY updated_at DESC", (speaker_id, prefix.replace("%", "") + "%"))


def all_active(speaker_id: Optional[str] = None) -> List[Dict[str, Any]]:
    if speaker_id:
        return _rows("SELECT * FROM facts WHERE speaker_id=? AND active=1 ORDER BY updated_at DESC",
                     (speaker_id,))
    return _rows("SELECT * FROM facts WHERE active=1 ORDER BY updated_at DESC")


def get_unindexed(limit: int = 50) -> List[Dict[str, Any]]:
    return _rows("SELECT * FROM facts WHERE active=1 AND indexed=0 AND category!='style' "
                 "ORDER BY id LIMIT ?", (limit,))


def get_facts(speaker_id: Optional[str] = None, category: Optional[str] = None,
              active_only: bool = True, limit: int = 500) -> List[Dict[str, Any]]:
    """Legacy API: filtered fact listing."""
    query, params = "SELECT * FROM facts WHERE 1=1", []
    if speaker_id:
        query += " AND speaker_id=?"
        params.append(speaker_id)
    if category:
        query += " AND category=?"
        params.append(category)
    if active_only:
        query += " AND active=1"
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    return _rows(query, tuple(params))


def find_similar_fact(speaker_id: str, key: Optional[str] = None,
                      category: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Legacy API: most recent active fact for speaker plus key/category."""
    query, params = "SELECT * FROM facts WHERE speaker_id=? AND active=1", [speaker_id]
    if key:
        query += " AND key=?"
        params.append(key)
    if category:
        query += " AND category=?"
        params.append(category)
    rows = _rows(query + " ORDER BY updated_at DESC LIMIT 1", tuple(params))
    return rows[0] if rows else None


def get_fact_history(fact_id: int) -> List[Dict[str, Any]]:
    """Trace a correction chain from oldest to newest."""
    chain, current, seen = [], fact_id, set()
    while current and current not in seen:
        seen.add(current)
        row = get_by_id(current)
        if not row:
            break
        chain.append(row)
        current = row.get("superseded_by")
    return chain


def count_facts(speaker_id: Optional[str] = None, active_only: bool = True) -> int:
    query, params = "SELECT COUNT(*) AS c FROM facts WHERE category!='style'", []
    if speaker_id:
        query += " AND speaker_id=?"
        params.append(speaker_id)
    if active_only:
        query += " AND active=1"
    return _rows(query, tuple(params))[0]["c"]


# --------------------------------------------------------------------------
# Meta (one-shot flags such as "legacy migration done")
# --------------------------------------------------------------------------

def meta_get(k: str, default: Optional[str] = None) -> Optional[str]:
    rows = _rows("SELECT v FROM meta WHERE k=?", (k,))
    return rows[0]["v"] if rows else default


def meta_set(k: str, v: str) -> None:
    _init_schema()
    conn = _get_conn()
    try:
        conn.execute("INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
        conn.commit()
    finally:
        conn.close()
