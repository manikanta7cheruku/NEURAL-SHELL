"""
=============================================================================
PROJECT SEVEN - backend/routes/tasks.py
Version: 1.0.0

PURPOSE:
    Full CRUD API for the Task System.
    SQLite storage — structured data, not semantic.
    
ARCHITECTURE: Modular Monolith — APIRouter pattern
    Registered in api_server.py exactly like schedules router.
    
STORAGE:
    Dev:       M:\Manikanta\Apps\MK-Projects\SEVEN\seven_data\tasks.db
    Installed: %APPDATA%\SEVEN\seven_data\tasks.db
    Resolved via seven_paths.paths._seven_data

DB PATTERN: SQLite WAL mode
    WAL (Write-Ahead Logging) = concurrent reads during writes
    Essential: schedule_daemon.py reads tasks.db at same time
    Context manager guarantees connection closure on error

ERROR HANDLING: Graceful Degradation
    Every endpoint returns structured error, never raises unhandled
    Main.py handler and frontend both receive clean error messages

IPC PATTERN: Shared Database
    main.py voice pipeline → POST /api/tasks → tasks.db
    schedule_daemon.py     → direct SQLite read → tasks.db
    Both processes share state via DB — no direct process calls
=============================================================================
"""

import sqlite3
import os
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from colorama import Fore

# ── Path Resolution ───────────────────────────────────────────────────────────
# Uses seven_paths singleton — same pattern as all other data files
# Dev:  ./seven_data/tasks.db
# Prod: %APPDATA%/SEVEN/seven_data/tasks.db

try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception as _pe:
    # Graceful degradation — fall back to local directory
    print(Fore.YELLOW + f"[TASKS] seven_paths unavailable: {_pe}. Using local path.")
    _SEVEN_DATA = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "seven_data")

os.makedirs(_SEVEN_DATA, exist_ok=True)
TASKS_DB = os.path.join(_SEVEN_DATA, "tasks.db")

print(Fore.GREEN + f"[TASKS] Database path: {TASKS_DB}")

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter()


# ── Schema ────────────────────────────────────────────────────────────────────
# Pydantic models handle deserialization (HTTP JSON → Python objects)
# and serialization (Python objects → HTTP JSON response)

class TaskCreate(BaseModel):
    """Deserialization model for POST /api/tasks"""
    text:      str
    due_date:  Optional[str]  = None   # ISO date: "2025-07-15"
    due_time:  Optional[str]  = None   # "17:00"
    priority:  Optional[str]  = "medium"
    tags:      Optional[str]  = None   # comma-separated: "work,urgent"


class TaskUpdate(BaseModel):
    """Deserialization model for PUT /api/tasks/{id}"""
    text:         Optional[str]  = None
    due_date:     Optional[str]  = None
    due_time:     Optional[str]  = None
    priority:     Optional[str]  = None
    completed:    Optional[bool] = None
    tags:         Optional[str]  = None


# ── Database Initialization ───────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """
    Open SQLite connection with WAL mode.
    
    WAL MODE: Write-Ahead Logging
        Allows concurrent reads while a write is in progress.
        Critical for our IPC pattern: schedule_daemon.py reads
        tasks.db while main.py is writing to it.
        Without WAL: database locked errors under concurrent access.
    
    Row factory: sqlite3.Row
        Rows behave like dicts — row["text"] instead of row[0]
        Makes serialization to JSON trivial
    """
    conn = sqlite3.connect(TASKS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL mode for concurrent access between main.py and daemon
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """
    Initialize tasks table if it does not exist.
    Called once at module import — safe to call multiple times (IF NOT EXISTS).
    
    SCHEMA DECISIONS:
        completed INTEGER (0/1) not BOOLEAN — SQLite has no bool type
        tags TEXT comma-separated — avoids join table for simple use case
        all datetimes as TEXT ISO strings — SQLite has no datetime type
        priority TEXT with CHECK constraint — enforced at DB level
    """
    try:
        with _get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    text         TEXT NOT NULL,
                    due_date     TEXT,
                    due_time     TEXT,
                    priority     TEXT DEFAULT 'medium'
                                 CHECK(priority IN ('low', 'medium', 'high')),
                    completed    INTEGER DEFAULT 0
                                 CHECK(completed IN (0, 1)),
                    created_at   TEXT NOT NULL,
                    completed_at TEXT,
                    tags         TEXT
                )
            """)
            # Index on due_date — most common query pattern
            # "get tasks due today" runs this index every 30s from daemon
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_due_date
                ON tasks(due_date)
            """)
            # Index on completed — list/filter operations
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_completed
                ON tasks(completed)
            """)
            conn.commit()
            print(Fore.GREEN + "[TASKS] Database initialized.")
    except Exception as e:
        # Graceful degradation — log error but do not crash startup
        print(Fore.RED + f"[TASKS] DB init failed: {e}")


# Run at import time — module-level initialization
init_db()


# ── Serialization Helper ──────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    """
    Serialize SQLite Row → Python dict for JSON response.
    
    SERIALIZATION: Converting internal data format to transport format.
        sqlite3.Row → dict → FastAPI auto-converts dict → JSON
        
    Handles type coercions:
        completed: INTEGER (0/1) → bool (True/False) for frontend
        tags: "work,urgent" → ["work", "urgent"] for frontend
        due_date/due_time: kept as strings (ISO format)
    """
    d = dict(row)
    # Coerce INTEGER to bool for clean JSON
    d["completed"] = bool(d.get("completed", 0))
    # Deserialize comma-separated tags to list
    raw_tags = d.get("tags", "") or ""
    d["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
    return d


def _is_overdue(task: dict) -> bool:
    """Check if task is overdue — past due_date and not completed."""
    if task.get("completed") or not task.get("due_date"):
        return False
    try:
        due = date.fromisoformat(task["due_date"])
        return due < date.today()
    except Exception:
        return False


def _is_due_today(task: dict) -> bool:
    """Check if task is due today."""
    if task.get("completed") or not task.get("due_date"):
        return False
    try:
        due = date.fromisoformat(task["due_date"])
        return due == date.today()
    except Exception:
        return False


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@router.get("/api/tasks")
def list_tasks(
    status:   Optional[str] = Query(None),   # "pending" | "completed"
    priority: Optional[str] = Query(None),   # "low" | "medium" | "high"
    date:     Optional[str] = Query(None),   # ISO date filter
):
    """
    List all tasks with optional filters.
    
    CACHING NOTE: Frontend useTasks.js Zustand store caches this response.
    Components read from store, not directly from this endpoint.
    Store invalidates cache on any mutation (add/update/delete).
    """
    try:
        with _get_conn() as conn:
            query  = "SELECT * FROM tasks WHERE 1=1"
            params: List = []

            if status == "pending":
                query += " AND completed = 0"
            elif status == "completed":
                query += " AND completed = 1"

            if priority:
                query += " AND priority = ?"
                params.append(priority)

            if date:
                query += " AND due_date = ?"
                params.append(date)

            query += " ORDER BY completed ASC, due_date ASC NULLS LAST, priority DESC"

            rows = conn.execute(query, params).fetchall()
            return [_row_to_dict(r) for r in rows]

    except Exception as e:
        print(Fore.RED + f"[TASKS] list_tasks error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tasks: {str(e)}")


@router.post("/api/tasks")
def create_task(body: TaskCreate):
    """
    Create a new task.
    
    DESERIALIZATION: FastAPI + Pydantic automatically:
        HTTP JSON body → TaskCreate Python object
        Validates types, sets defaults, raises 422 on invalid data
    
    SERIALIZATION: Return dict → FastAPI auto-converts to JSON response
    """
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Task text cannot be empty.")

    priority = body.priority or "medium"
    if priority not in ("low", "medium", "high"):
        priority = "medium"

    # Serialize tags: list or string → comma-separated string for storage
    tags_str = None
    if body.tags:
        if isinstance(body.tags, list):
            tags_str = ",".join(t.strip() for t in body.tags if t.strip())
        else:
            tags_str = body.tags.strip()

    now_iso = datetime.now().isoformat()

    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (text, due_date, due_time, priority, completed,
                                   created_at, completed_at, tags)
                VALUES (?, ?, ?, ?, 0, ?, NULL, ?)
                """,
                (body.text.strip(), body.due_date, body.due_time,
                 priority, now_iso, tags_str)
            )
            conn.commit()
            new_id = cursor.lastrowid

        # Return created task for frontend optimistic update
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (new_id,)
            ).fetchone()

        created = _row_to_dict(row)
        print(Fore.GREEN + f"[TASKS] Created task #{new_id}: {body.text[:50]}")
        return {"success": True, "task": created}

    except Exception as e:
        print(Fore.RED + f"[TASKS] create_task error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.put("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    """
    Update task fields. Partial update — only provided fields change.
    
    Handles: complete/uncomplete, edit text, change due date, change priority.
    Completing a task sets completed_at timestamp automatically.
    """
    try:
        with _get_conn() as conn:
            # Verify task exists
            existing = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

            updates: List[str] = []
            params:  List      = []

            if body.text is not None:
                if not body.text.strip():
                    raise HTTPException(status_code=400, detail="Task text cannot be empty.")
                updates.append("text = ?")
                params.append(body.text.strip())

            if body.due_date is not None:
                updates.append("due_date = ?")
                params.append(body.due_date if body.due_date else None)

            if body.due_time is not None:
                updates.append("due_time = ?")
                params.append(body.due_time if body.due_time else None)

            if body.priority is not None:
                if body.priority not in ("low", "medium", "high"):
                    raise HTTPException(status_code=400, detail="Priority must be low, medium, or high.")
                updates.append("priority = ?")
                params.append(body.priority)

            if body.tags is not None:
                tags_str = body.tags.strip() if body.tags else None
                updates.append("tags = ?")
                params.append(tags_str)

            if body.completed is not None:
                updates.append("completed = ?")
                params.append(1 if body.completed else 0)
                # Set or clear completed_at timestamp
                updates.append("completed_at = ?")
                params.append(
                    datetime.now().isoformat() if body.completed else None
                )

            if not updates:
                return {"success": True, "task": _row_to_dict(existing)}

            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

            updated = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()

        result = _row_to_dict(updated)
        action = "completed" if body.completed else "updated"
        print(Fore.GREEN + f"[TASKS] Task #{task_id} {action}")
        return {"success": True, "task": result}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TASKS] update_task error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")


@router.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """
    Permanently delete a task.
    Hard delete — no soft delete needed at this scale.
    """
    try:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT id, text FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

        print(Fore.GREEN + f"[TASKS] Deleted task #{task_id}")
        return {"success": True, "deleted_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TASKS] delete_task error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")


@router.get("/api/tasks/today")
def get_tasks_today():
    """
    Tasks due today, not completed.
    Called by morning brief and sidebar badge.
    
    PERFORMANCE: Uses idx_tasks_due_date index — O(log n) lookup.
    """
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE due_date = ? AND completed = 0
                ORDER BY priority DESC, due_time ASC NULLS LAST
                """,
                (today_str,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    except Exception as e:
        print(Fore.RED + f"[TASKS] get_tasks_today error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tasks/overdue")
def get_tasks_overdue():
    """
    Tasks past their due_date, not completed.
    Called by morning brief and schedule_daemon.py.
    """
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE due_date < ? AND completed = 0
                ORDER BY due_date ASC, priority DESC
                """,
                (today_str,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    except Exception as e:
        print(Fore.RED + f"[TASKS] get_tasks_overdue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tasks/stats")
def get_task_stats():
    """
    Aggregate counts for sidebar badge and morning brief.
    
    CACHING: Frontend polls this every 30s for the badge count.
    Lightweight query — aggregate only, no row data returned.
    """
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            pending   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE completed = 0"
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE completed = 1"
            ).fetchone()[0]
            due_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND completed = 0",
                (today_str,)
            ).fetchone()[0]
            overdue   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND completed = 0",
                (today_str,)
            ).fetchone()[0]

        return {
            "total":     total,
            "pending":   pending,
            "completed": completed,
            "due_today": due_today,
            "overdue":   overdue,
        }

    except Exception as e:
        print(Fore.RED + f"[TASKS] get_task_stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Direct DB Access for main.py (no HTTP overhead) ──────────────────────────
# These functions are called directly by main.py morning brief
# and schedule_daemon.py — IPC via shared SQLite, not HTTP

def db_get_due_today() -> List[dict]:
    """
    Direct DB call — bypasses HTTP for internal use.
    Used by: main.py morning brief, schedule_daemon.py
    
    IPC PATTERN: Shared database access
        No network call — direct SQLite read
        WAL mode ensures no lock conflict with concurrent writes
    """
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE due_date = ? AND completed = 0",
                (today_str,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.YELLOW + f"[TASKS] db_get_due_today failed: {e}")
        return []   # Graceful degradation — morning brief skips section


def db_get_overdue() -> List[dict]:
    """Direct DB call for overdue tasks. Used by morning brief and daemon."""
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE due_date < ? AND completed = 0",
                (today_str,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.YELLOW + f"[TASKS] db_get_overdue failed: {e}")
        return []   # Graceful degradation


def db_get_stats() -> dict:
    """Direct DB call for stats. Used by morning brief."""
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            pending   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE completed = 0"
            ).fetchone()[0]
            due_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND completed = 0",
                (today_str,)
            ).fetchone()[0]
            overdue   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND completed = 0",
                (today_str,)
            ).fetchone()[0]
        return {"pending": pending, "due_today": due_today, "overdue": overdue}
    except Exception as e:
        print(Fore.YELLOW + f"[TASKS] db_get_stats failed: {e}")
        return {"pending": 0, "due_today": 0, "overdue": 0}


def db_find_task_by_text(search: str) -> Optional[dict]:
    """
    Fuzzy find task by text — used by voice complete/delete commands.
    
    MATCHING STRATEGY:
        1. Exact match on normalized text
        2. Contains match (search term in task text)
        3. All words present (partial word match)
    Returns first match or None.
    """
    try:
        search_lower = search.lower().strip().replace("_", " ")
        with _get_conn() as conn:
            # Strategy 1: contains
            rows = conn.execute(
                "SELECT * FROM tasks WHERE LOWER(text) LIKE ? AND completed = 0",
                (f"%{search_lower}%",)
            ).fetchall()
            if rows:
                return _row_to_dict(rows[0])

            # Strategy 2: all words present
            words = search_lower.split()
            if len(words) > 1:
                all_tasks = conn.execute(
                    "SELECT * FROM tasks WHERE completed = 0"
                ).fetchall()
                for row in all_tasks:
                    task_text = row["text"].lower()
                    if all(w in task_text for w in words):
                        return _row_to_dict(row)

        return None
    except Exception as e:
        print(Fore.YELLOW + f"[TASKS] db_find_task_by_text failed: {e}")
        return None


def db_get_pending_list() -> List[dict]:
    """Get all pending tasks ordered by due date then priority."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks WHERE completed = 0
                ORDER BY due_date ASC NULLS LAST,
                         CASE priority
                             WHEN 'high'   THEN 1
                             WHEN 'medium' THEN 2
                             WHEN 'low'    THEN 3
                         END ASC
                """
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.YELLOW + f"[TASKS] db_get_pending_list failed: {e}")
        return []