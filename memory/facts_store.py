"""
=============================================================================
memory/facts_store.py

Structured SQLite facts store for Seven's long-term memory.
Isolated from ChromaDB. Supports:
    - Speaker-partitioned facts
    - Structured queries (by category, date, speaker)
    - Correction chaining (superseded_by link)
    - Soft delete via active flag

Schema:
    facts (
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
    )

Thread-safe via connection-per-call pattern.
=============================================================================
"""

import os
import sqlite3
import datetime
import threading
from typing import Optional, List, Dict, Any


# ── Path resolution: matches memory/core.py logic ──
def _get_facts_db_path() -> str:
    local_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "seven_data", "memory"
    )
    if os.path.exists(local_path):
        chroma_db = os.path.join(local_path, "chroma.sqlite3")
        if os.path.exists(chroma_db):
            return os.path.join(local_path, "facts_structured.db")

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        path = os.path.join(appdata, "SEVEN", "seven_data", "memory")
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, "facts_structured.db")

    os.makedirs(local_path, exist_ok=True)
    return os.path.join(local_path, "facts_structured.db")


FACTS_DB_PATH = _get_facts_db_path()
_init_lock = threading.Lock()
_initialized = False


def _get_conn() -> sqlite3.Connection:
    """Returns a new connection with row factory enabled."""
    conn = sqlite3.connect(FACTS_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_schema():
    """One-time table creation. Safe to call repeatedly."""
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
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_speaker ON facts(speaker_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_category ON facts(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(speaker_id, key)")
            conn.commit()
            _initialized = True
        finally:
            conn.close()


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Public API ──

def add_fact(
    value: str,
    speaker_id: str = "default",
    category: str = "general",
    key: Optional[str] = None,
    source_text: Optional[str] = None
) -> int:
    """Insert a new active fact. Returns the new fact ID."""
    _init_schema()
    if not value or not value.strip():
        raise ValueError("Fact value cannot be empty")

    conn = _get_conn()
    try:
        now = _now()
        cur = conn.execute(
            """INSERT INTO facts
               (speaker_id, category, key, value, source_text, created_at, updated_at, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (speaker_id, category, key, value.strip(), source_text, now, now)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def supersede_fact(old_id: int, new_value: str, source_text: Optional[str] = None) -> Optional[int]:
    """
    Marks old fact inactive and links it to a new replacement fact.
    Returns the new fact ID or None if old fact not found.
    """
    _init_schema()
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT speaker_id, category, key FROM facts WHERE id = ? AND active = 1",
            (old_id,)
        ).fetchone()
        if not row:
            return None

        now = _now()
        cur = conn.execute(
            """INSERT INTO facts
               (speaker_id, category, key, value, source_text, created_at, updated_at, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            (row["speaker_id"], row["category"], row["key"], new_value.strip(),
             source_text, now, now)
        )
        new_id = cur.lastrowid

        conn.execute(
            "UPDATE facts SET active = 0, superseded_by = ?, updated_at = ? WHERE id = ?",
            (new_id, now, old_id)
        )
        conn.commit()
        return new_id
    finally:
        conn.close()


def update_fact(fact_id: int, new_value: str) -> bool:
    """Directly updates a fact value in place. Returns True on success."""
    _init_schema()
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE facts SET value = ?, updated_at = ? WHERE id = ? AND active = 1",
            (new_value.strip(), _now(), fact_id)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_fact(fact_id: int) -> bool:
    """Hard delete a fact record. Returns True on success."""
    _init_schema()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_facts(
    speaker_id: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Query facts with optional filters. Returns list of dicts."""
    _init_schema()
    conn = _get_conn()
    try:
        query = "SELECT * FROM facts WHERE 1=1"
        params: list = []
        if speaker_id:
            query += " AND speaker_id = ?"
            params.append(speaker_id)
        if category:
            query += " AND category = ?"
            params.append(category)
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def find_similar_fact(
    speaker_id: str,
    key: Optional[str] = None,
    category: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Finds the most recent active fact matching speaker + key/category."""
    _init_schema()
    conn = _get_conn()
    try:
        query = "SELECT * FROM facts WHERE speaker_id = ? AND active = 1"
        params: list = [speaker_id]
        if key:
            query += " AND key = ?"
            params.append(key)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY updated_at DESC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_fact_history(fact_id: int) -> List[Dict[str, Any]]:
    """
    Traces the full correction chain for a fact.
    Returns list ordered oldest to newest.
    """
    _init_schema()
    conn = _get_conn()
    try:
        chain = []
        current_id = fact_id
        visited = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            row = conn.execute("SELECT * FROM facts WHERE id = ?", (current_id,)).fetchone()
            if not row:
                break
            chain.append(dict(row))
            current_id = row["superseded_by"]
        return chain
    finally:
        conn.close()


def count_facts(speaker_id: Optional[str] = None, active_only: bool = True) -> int:
    """Returns count of stored facts."""
    _init_schema()
    conn = _get_conn()
    try:
        query = "SELECT COUNT(*) as c FROM facts WHERE 1=1"
        params: list = []
        if speaker_id:
            query += " AND speaker_id = ?"
            params.append(speaker_id)
        if active_only:
            query += " AND active = 1"
        row = conn.execute(query, params).fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()