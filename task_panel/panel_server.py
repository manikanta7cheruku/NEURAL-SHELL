"""
PROJECT SEVEN - task_panel/panel_server.py
Lightweight FastAPI server for the Task Panel.
Port: 7778
Runs independently — does not need Seven to be running.
Reads/writes tasks.db directly via SQLite WAL mode.
"""

import sqlite3
import os
import sys
import json
from datetime import datetime, date
from typing import Optional

# Add project root to path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# ── DB Path ──────────────────────────────────────────────────────────────────

def _get_tasks_db():
    try:
        from seven_paths import paths
        return os.path.join(paths._seven_data, "tasks.db")
    except Exception:
        _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(_appdata, "SEVEN", "seven_data", "tasks.db")

TASKS_DB = _get_tasks_db()

# ── Panel trigger file — daemon writes this to auto-show panel ────────────────
PANEL_TRIGGER = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "SEVEN", "panel_trigger.json"
)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Seven Panel API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    conn = sqlite3.connect(TASKS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _row(row) -> dict:
    d = dict(row)
    d["completed"] = bool(d.get("completed", 0))
    raw = d.get("subtasks", "[]") or "[]"
    try:
        d["subtasks"] = json.loads(raw)
    except Exception:
        d["subtasks"] = []
    raw_tags = d.get("tags", "") or ""
    d["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
    return d

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/panel/health")
def health():
    return {"status": "ok", "db": os.path.exists(TASKS_DB)}


@app.get("/panel/tasks")
def get_tasks():
    """All pending tasks ordered by priority then due date."""
    if not os.path.exists(TASKS_DB):
        return []
    try:
        with _conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE completed = 0
                ORDER BY
                    CASE priority WHEN 'high' THEN 1
                                  WHEN 'medium' THEN 2
                                  WHEN 'low' THEN 3 END ASC,
                    due_date ASC NULLS LAST,
                    created_at ASC
                """
            ).fetchall()
        return [_row(r) for r in rows]
    except Exception as e:
        print(f"[PANEL] get_tasks error: {e}")
        return []


@app.get("/panel/stats")
def get_stats():
    if not os.path.exists(TASKS_DB):
        return {"pending": 0, "due_today": 0, "overdue": 0}
    try:
        today = date.today().isoformat()
        with _conn() as conn:
            pending   = conn.execute("SELECT COUNT(*) FROM tasks WHERE completed=0").fetchone()[0]
            due_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date=? AND completed=0", (today,)
            ).fetchone()[0]
            overdue   = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE due_date<? AND completed=0", (today,)
            ).fetchone()[0]
        return {"pending": pending, "due_today": due_today, "overdue": overdue}
    except Exception as e:
        print(f"[PANEL] stats error: {e}")
        return {"pending": 0, "due_today": 0, "overdue": 0}


@app.put("/panel/tasks/{task_id}/complete")
def complete_task(task_id: int):
    """Mark task as complete. Tries Seven API first, falls back to direct DB."""
    # Try Seven API first (keeps both UIs in sync)
    try:
        import requests as _r
        resp = _r.put(
            f"http://127.0.0.1:7777/api/tasks/{task_id}",
            json={"completed": True},
            timeout=2
        )
        if resp.status_code == 200:
            return {"success": True, "source": "seven"}
    except Exception:
        pass

    # Direct DB fallback
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE tasks SET completed=1, completed_at=? WHERE id=?",
                (datetime.now().isoformat(), task_id)
            )
            conn.commit()
        return {"success": True, "source": "direct"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.put("/panel/tasks/{task_id}/subtasks")
def update_subtasks(task_id: int, body: dict):
    """Update subtasks list for a task."""
    subtasks = body.get("subtasks", [])
    subtasks_json = json.dumps(subtasks) if subtasks else "[]"

    # Try Seven API first
    try:
        import requests as _r
        resp = _r.put(
            f"http://127.0.0.1:7777/api/tasks/{task_id}",
            json={"subtasks": subtasks},
            timeout=2
        )
        if resp.status_code == 200:
            return {"success": True, "source": "seven"}
    except Exception:
        pass

    # Direct DB fallback
    try:
        with _conn() as conn:
            conn.execute(
                "UPDATE tasks SET subtasks=? WHERE id=?",
                (subtasks_json, task_id)
            )
            conn.commit()
        return {"success": True, "source": "direct"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/panel/trigger")
def check_trigger():
    """
    Electron polls this every 3 seconds.
    Returns trigger data if daemon wrote a trigger file.
    Clears trigger after reading.
    """
    if os.path.exists(PANEL_TRIGGER):
        try:
            with open(PANEL_TRIGGER, "r") as f:
                data = json.load(f)
            os.remove(PANEL_TRIGGER)
            return {"triggered": True, "data": data}
        except Exception:
            return {"triggered": False}
    return {"triggered": False}


class QuickTaskCreate(BaseModel):
    text: str


@app.post("/panel/tasks")
def quick_create_task(body: QuickTaskCreate):
    """Create a task directly from the panel without Seven running."""
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=400, detail="Empty task text")

    try:
        now = datetime.now().isoformat()
        with _conn() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (text, due_date, due_time, priority,"
                " completed, created_at, completed_at, tags,"
                " description, subtasks)"
                " VALUES (?, NULL, NULL, 'medium', 0, ?, NULL, NULL, NULL, '[]')",
                (body.text.strip(), now)
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (new_id,)).fetchone()
        return {"success": True, "task": _row(row)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/panel/schedules")
def get_schedules():
    """Get active schedules for panel display."""
    try:
        sched_file = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "SEVEN", "schedules.json"
        )
        if not os.path.exists(sched_file):
            return []
        with open(sched_file, "r") as f:
            scheds = json.load(f)
        active = [s for s in scheds if s.get("status") == "active"]
        active.sort(key=lambda s: s.get("time", ""))
        return active[:5]
    except Exception:
        return []


if __name__ == "__main__":
    print(f"[PANEL SERVER] Starting on port 7778")
    print(f"[PANEL SERVER] Tasks DB: {TASKS_DB}")
    uvicorn.run(app, host="127.0.0.1", port=7778, log_level="warning")