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
import subprocess
import webbrowser
from datetime import datetime, date

# Add project root to path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ── DB Path ──────────────────────────────────────────────────────────────────

def _get_seven_data():
    try:
        from seven_paths import paths
        return paths._seven_data
    except Exception as e:
        _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(_appdata, "SEVEN", "seven_data")

SEVEN_DATA_DIR = _get_seven_data()
RELOAD_SIGNAL = os.path.join(SEVEN_DATA_DIR, "trigger_reload.signal")

def _get_tasks_db():
    db_path = os.path.join(SEVEN_DATA_DIR, "tasks.db")
    print(f"[PANEL DB] Loaded tasks.db: {db_path}")
    return db_path

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

@app.get("/panel/triggers")
def get_triggers_direct():
    """
    Direct SQLite read of triggers.db — fallback when Seven's main
    backend (port 7777) is not running. Read-only: toggling, editing,
    deleting, and firing a trigger all still require the main app.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        return []

    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT * FROM triggers ORDER BY "
            "CASE WHEN hotkey IS NOT NULL THEN 0 "
            "WHEN voice_phrase IS NOT NULL THEN 1 "
            "WHEN audio_pattern IS NOT NULL THEN 2 "
            "ELSE 3 END, name ASC"
        ).fetchall()
        conn.close()

        result = []
        for r in rows:
            d = dict(r)
            d["enabled"] = bool(d.get("enabled", 1))
            d["silent"] = bool(d.get("silent", 0))
            try:
                d["action_data"] = json.loads(d.get("action_data") or "{}")
            except Exception:
                d["action_data"] = {}
            result.append(d)
        return result
    except Exception as e:
        print(f"[PANEL] triggers fallback error: {e}")
        return []


@app.put("/panel/triggers/{trigger_id}")
def update_trigger_direct(trigger_id: int, body: dict):
    """
    Direct SQLite update of triggers.db — fallback when Seven's main
    backend (port 7777) is not running. Supports updating enabled state
    and other trigger fields.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        raise HTTPException(status_code=500, detail="Triggers database not found")

    # Validate trigger_id exists
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Build update query dynamically based on provided fields
    updates = []
    params = []

    if 'name' in body and body['name'] is not None:
        if not body['name'].strip():
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        updates.append("name = ?")
        params.append(body['name'].strip())

    if 'action_type' in body and body['action_type'] is not None:
        # Validate action_type
        valid_action_types = {
            'open_app', 'open_url', 'open_file', 'open_folder',
            'open_workspace', 'run_command', 'seven_action'
        }
        if body['action_type'] not in valid_action_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action_type. Must be one of: {', '.join(valid_action_types)}"
            )
        updates.append("action_type = ?")
        params.append(body['action_type'])

    if 'action_data' in body and body['action_data'] is not None:
        updates.append("action_data = ?")
        params.append(json.dumps(body['action_data']))

    if 'hotkey' in body:
        updates.append("hotkey = ?")
        params.append(body['hotkey'] if body['hotkey'] else None)

    if 'voice_phrase' in body:
        updates.append("voice_phrase = ?")
        params.append(body['voice_phrase'].lower().strip() if body['voice_phrase'] else None)

    if 'audio_pattern' in body:
        updates.append("audio_pattern = ?")
        params.append(body['audio_pattern'] if body['audio_pattern'] else None)

    if 'enabled' in body and body['enabled'] is not None:
        updates.append("enabled = ?")
        params.append(1 if body['enabled'] else 0)

    if 'silent' in body and body['silent'] is not None:
        updates.append("silent = ?")
        params.append(1 if body['silent'] else 0)

    if 'icon' in body and body['icon'] is not None:
        updates.append("icon = ?")
        params.append(body['icon'])

    if not updates:
        # No fields to update
        return {"success": True}

    updates.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(trigger_id)

    # Create a fresh connection for the update operation
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            f"UPDATE triggers SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        conn.close()

        # Signal daemon to reload triggers (if daemon is running)
        try:
            with open(RELOAD_SIGNAL, "w") as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            print(f"[PANEL] Failed to write reload signal: {e}")

        return {"success": True}
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/panel/triggers/{trigger_id}")
def delete_trigger_direct(trigger_id: int):
    """
    Direct SQLite delete of triggers.db — fallback when Seven's main
    backend (port 7777) is not running.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        raise HTTPException(status_code=500, detail="Triggers database not found")

    # Validate trigger_id exists
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Create a fresh connection for the delete operation
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
        conn.commit()
        conn.close()

        # Signal daemon to reload triggers (if daemon is running)
        try:
            with open(RELOAD_SIGNAL, "w") as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            print(f"[PANEL] Failed to write reload signal: {e}")

        return {"success": True}
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/panel/triggers/{trigger_id}/fire")
def fire_trigger_direct(trigger_id: int):
    """
    Direct SQLite fire of trigger — fallback when Seven's main
    backend (port 7777) is not running. Executes the trigger's action
    directly using trigger_modules.executor.
    """
    triggers_db = os.path.join(SEVEN_DATA_DIR, "triggers.db")

    if not os.path.exists(triggers_db):
        raise HTTPException(status_code=500, detail="Triggers database not found")

    # Get the trigger
    try:
        conn = sqlite3.connect(triggers_db, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

        trigger = dict(row)
        trigger["enabled"] = bool(trigger.get("enabled", 1))
        trigger["silent"] = bool(trigger.get("silent", 0))
        try:
            trigger["action_data"] = json.loads(trigger.get("action_data") or "{}")
        except Exception:
            trigger["action_data"] = {}
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not trigger.get("enabled", False):
        return {"success": False, "error": "Trigger is disabled"}

    try:
        from trigger_modules.executor import execute_trigger
        import threading
        
        # execute_trigger in trigger_modules handles intelligent background threading, 
        # on-screen overlay animations, status notifications, and stats logging autonomously.
        threading.Thread(target=execute_trigger, args=(trigger,), daemon=True).start()
        return {"success": True, "message": "Trigger execution initiated via daemon executor"}
    except Exception as e:
        print(f"[PANEL SERVER] executor load error: {e}. Running quick python subprocess fallback.")
        try:
            action_type = trigger.get('action_type')
            action_data = trigger.get('action_data', {})
            if action_type == 'open_app':
                app_path = action_data.get('path') or action_data.get('app')
                if app_path:
                    subprocess.Popen(app_path, shell=True)
                    return {"success": True, "message": f"Launched {app_path}"}
            elif action_type == 'open_url':
                url = action_data.get('url')
                if url:
                    webbrowser.open(url)
                    return {"success": True, "message": f"Opened {url}"}
            return {"success": False, "error": f"Unsupported offline action type: {action_type}"}
        except Exception as fe:
            raise HTTPException(status_code=500, detail=f"Failed to execute fallback: {str(fe)}")


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


@app.put("/panel/tasks/{task_id}")
def update_task_direct(task_id: int, body: dict):
    """
    Direct SQLite update of tasks.db — fallback when Seven's main
    backend (port 7777) is not running.
    """
    if not os.path.exists(TASKS_DB):
        raise HTTPException(status_code=500, detail="Tasks database not found")

    updates = []
    params = []

    if 'text' in body and body['text'] is not None:
        if not body['text'].strip():
            raise HTTPException(status_code=400, detail="Task text cannot be empty")
        updates.append("text = ?")
        params.append(body['text'].strip())

    if 'due_date' in body:
        updates.append("due_date = ?")
        params.append(body['due_date'] or None)

    if 'due_time' in body:
        updates.append("due_time = ?")
        params.append(body['due_time'] or None)

    if 'priority' in body and body['priority'] is not None:
        if body['priority'] not in ("low", "medium", "high"):
            raise HTTPException(status_code=400, detail="Invalid priority")
        updates.append("priority = ?")
        params.append(body['priority'])

    if 'tags' in body:
        updates.append("tags = ?")
        params.append(body['tags'] or None)

    if 'description' in body:
        updates.append("description = ?")
        params.append(body['description'] or None)

    if 'subtasks' in body:
        updates.append("subtasks = ?")
        params.append(json.dumps(body['subtasks']) if body['subtasks'] else "[]")

    if 'completed' in body and body['completed'] is not None:
        updates.append("completed = ?")
        params.append(1 if body['completed'] else 0)
        updates.append("completed_at = ?")
        params.append(datetime.now().isoformat() if body['completed'] else None)

    if not updates:
        return {"success": True}

    params.append(task_id)

    try:
        with _conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.delete("/panel/tasks/{task_id}")
def delete_task_direct(task_id: int):
    """
    Direct SQLite delete of task — fallback when Seven's main
    backend (port 7777) is not running.
    """
    if not os.path.exists(TASKS_DB):
        raise HTTPException(status_code=500, detail="Tasks database not found")

    try:
        with _conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


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


@app.delete("/panel/schedules/{sched_id}")
def cancel_schedule_direct(sched_id: int):
    """Cancel a schedule directly from schedules.json when Seven is offline."""
    try:
        sched_file = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "SEVEN", "schedules.json"
        )
        if not os.path.exists(sched_file):
            raise HTTPException(status_code=404, detail="Schedules file not found")

        with open(sched_file, "r") as f:
            scheds = json.load(f)

        updated = False
        for s in scheds:
            if s.get("id") == sched_id:
                s["status"] = "cancelled"
                s["updated_at"] = datetime.now().isoformat()
                updated = True
                break

        if updated:
            with open(sched_file, "w") as f:
                json.dump(scheds, f, indent=2)

            # Emit a reload trigger so schedule daemon updates lists
            try:
                signal_file = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")),
                    "SEVEN", "schedule_reload.signal"
                )
                with open(signal_file, "w") as f:
                    f.write(datetime.now().isoformat())
            except Exception:
                pass

            return {"success": True}

        raise HTTPException(status_code=404, detail="Schedule not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    print(f"[PANEL SERVER] Starting on port 7778")
    print(f"[PANEL SERVER] Tasks DB: {TASKS_DB}")
    uvicorn.run(app, host="127.0.0.1", port=7778, log_level="warning")