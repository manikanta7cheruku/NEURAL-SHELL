"""
PROJECT SEVEN - backend/routes/tasks.py
Full CRUD API for Task System. SQLite WAL mode.
"""

import sqlite3
import os
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from colorama import Fore

try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception as _pe:
    print(Fore.YELLOW + f"[TASKS] seven_paths unavailable: {_pe}")
    _SEVEN_DATA = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "seven_data")

os.makedirs(_SEVEN_DATA, exist_ok=True)
TASKS_DB = os.path.join(_SEVEN_DATA, "tasks.db")
print(Fore.GREEN + f"[TASKS] DB: {TASKS_DB}")

router = APIRouter()


class TaskCreate(BaseModel):
    text:      str
    due_date:  Optional[str]  = None
    due_time:  Optional[str]  = None
    priority:  Optional[str]  = "medium"
    tags:      Optional[str]  = None


class TaskUpdate(BaseModel):
    text:         Optional[str]  = None
    due_date:     Optional[str]  = None
    due_time:     Optional[str]  = None
    priority:     Optional[str]  = None
    completed:    Optional[bool] = None
    tags:         Optional[str]  = None


def _get_conn():
    conn = sqlite3.connect(TASKS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
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
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_due
                ON tasks(due_date)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_done
                ON tasks(completed)
            """)
            conn.commit()
            print(Fore.GREEN + "[TASKS] DB initialized")
    except Exception as e:
        print(Fore.RED + f"[TASKS] DB init failed: {e}")


init_db()


def _row_to_dict(row):
    d = dict(row)
    d["completed"] = bool(d.get("completed", 0))
    raw = d.get("tags", "") or ""
    d["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
    return d


# =========================================================================
# ROUTES - SPECIFIC FIRST, PARAMETERIZED LAST
# =========================================================================

@router.get("/api/tasks/stats")
def get_task_stats():
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            pending   = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed = 0").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed = 1").fetchone()[0]
            due_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date = ? AND completed = 0",
                (today_str,)
            ).fetchone()[0]
            overdue = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND completed = 0",
                (today_str,)
            ).fetchone()[0]
        return {
            "total": total, "pending": pending, "completed": completed,
            "due_today": due_today, "overdue": overdue,
        }
    except Exception as e:
        print(Fore.RED + f"[TASKS] stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tasks/today")
def get_tasks_today():
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE due_date = ? AND completed = 0 "
                "ORDER BY priority DESC, due_time ASC NULLS LAST",
                (today_str,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.RED + f"[TASKS] today error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tasks/overdue")
def get_tasks_overdue():
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE due_date < ? AND completed = 0 "
                "ORDER BY due_date ASC, priority DESC",
                (today_str,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.RED + f"[TASKS] overdue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tasks")
def list_tasks(
    status:   Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    date_filter: Optional[str] = Query(None, alias="date"),
):
    try:
        with _get_conn() as conn:
            query  = "SELECT * FROM tasks WHERE 1=1"
            params = []

            if status == "pending":
                query += " AND completed = 0"
            elif status == "completed":
                query += " AND completed = 1"

            if priority and priority in ("low", "medium", "high"):
                query += " AND priority = ?"
                params.append(priority)

            if date_filter:
                query += " AND due_date = ?"
                params.append(date_filter)

            query += (" ORDER BY completed ASC, due_date ASC NULLS LAST,"
                      " CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2"
                      " WHEN 'low' THEN 3 END ASC")

            rows = conn.execute(query, params).fetchall()
            return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.RED + f"[TASKS] list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tasks")
def create_task(body: TaskCreate):
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Task text cannot be empty.")

    priority = body.priority or "medium"
    if priority not in ("low", "medium", "high"):
        priority = "medium"

    tags_str = None
    if body.tags:
        tags_str = body.tags.strip() if isinstance(body.tags, str) else ",".join(body.tags)

    now_iso = datetime.now().isoformat()

    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (text, due_date, due_time, priority, completed,"
                " created_at, completed_at, tags) VALUES (?, ?, ?, ?, 0, ?, NULL, ?)",
                (body.text.strip(), body.due_date, body.due_time, priority, now_iso, tags_str)
            )
            conn.commit()
            new_id = cursor.lastrowid

        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()

        created = _row_to_dict(row)
        print(Fore.GREEN + f"[TASKS] Created #{new_id}: {body.text[:50]}")
        return {"success": True, "task": created}
    except Exception as e:
        print(Fore.RED + f"[TASKS] create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    try:
        with _get_conn() as conn:
            existing = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")

            updates = []
            params  = []

            if body.text is not None:
                if not body.text.strip():
                    raise HTTPException(status_code=400, detail="Task text cannot be empty.")
                updates.append("text = ?")
                params.append(body.text.strip())

            if body.due_date is not None:
                updates.append("due_date = ?")
                params.append(body.due_date or None)

            if body.due_time is not None:
                updates.append("due_time = ?")
                params.append(body.due_time or None)

            if body.priority is not None:
                if body.priority not in ("low", "medium", "high"):
                    raise HTTPException(status_code=400, detail="Priority must be low, medium, or high.")
                updates.append("priority = ?")
                params.append(body.priority)

            if body.tags is not None:
                updates.append("tags = ?")
                params.append(body.tags.strip() if body.tags else None)

            if body.completed is not None:
                updates.append("completed = ?")
                params.append(1 if body.completed else 0)
                updates.append("completed_at = ?")
                params.append(datetime.now().isoformat() if body.completed else None)

            if not updates:
                return {"success": True, "task": _row_to_dict(existing)}

            params.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()

            updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

        print(Fore.GREEN + f"[TASKS] Updated #{task_id}")
        return {"success": True, "task": _row_to_dict(updated)}
    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TASKS] update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    try:
        with _get_conn() as conn:
            existing = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

        print(Fore.GREEN + f"[TASKS] Deleted #{task_id}")
        return {"success": True, "deleted_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TASKS] delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# DIRECT DB ACCESS (for main.py morning brief and daemon)
# =========================================================================

def db_get_due_today():
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
        return []


def db_get_overdue():
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
        return []


def db_get_stats():
    try:
        today_str = date.today().isoformat()
        with _get_conn() as conn:
            pending   = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed = 0").fetchone()[0]
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


def db_find_task_by_text(search):
    try:
        search_lower = search.lower().strip().replace("_", " ")
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE LOWER(text) LIKE ? AND completed = 0",
                (f"%{search_lower}%",)
            ).fetchall()
            if rows:
                return _row_to_dict(rows[0])

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
        print(Fore.YELLOW + f"[TASKS] find failed: {e}")
        return None


def db_get_pending_list():
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE completed = 0 "
                "ORDER BY due_date ASC NULLS LAST, "
                "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 "
                "WHEN 'low' THEN 3 END ASC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.YELLOW + f"[TASKS] pending list failed: {e}")
        return []