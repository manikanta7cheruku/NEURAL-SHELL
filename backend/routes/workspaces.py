"""
=============================================================================
backend/routes/workspaces.py

Workspaces CRUD API + database schema.

WORKSPACE = a saved snapshot of open apps + browser tabs + file paths.
User can restore a workspace to instantly reopen everything.

APPS STRUCTURE (stored as JSON in apps field):
  [
    {
      "type": "chrome",
      "tabs": [
        {"url": "https://github.com", "title": "GitHub"},
        {"url": "https://gmail.com",  "title": "Gmail"}
      ]
    },
    {
      "type": "vscode",
      "workspace_path": "C:/Projects/Seven",
      "files": ["main.py", "brain.py"]
    },
    {
      "type": "explorer",
      "folder_path": "C:/Users/me/Documents"
    },
    {
      "type": "app",
      "name": "Spotify",
      "exe_path": null
    },
    {
      "type": "pdf",
      "file_path": "C:/Books/book.pdf",
      "page": 42
    }
  ]

NOTE: Chrome incognito tabs SKIPPED in v1.5 (comes in v1.6)
=============================================================================
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from colorama import Fore


# Reuse triggers DB (workspaces table lives in same DB)
try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception:
    _SEVEN_DATA = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "seven_data"
    )

TRIGGERS_DB = os.path.join(_SEVEN_DATA, "triggers.db")

print(Fore.GREEN + f"[WORKSPACES] Sharing DB: {TRIGGERS_DB}")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    name:        str
    description: Optional[str] = None
    apps:        list                # array of app configs (JSON)
    icon:        Optional[str] = None


class WorkspaceUpdate(BaseModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    apps:        Optional[list] = None
    icon:        Optional[str]  = None


# ─────────────────────────────────────────────────────────────────────────
# DATABASE CONNECTION (reuses triggers.db)
# ─────────────────────────────────────────────────────────────────────────

def _get_conn():
    conn = sqlite3.connect(TRIGGERS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _row_to_dict(row):
    d = dict(row)
    try:
        d["apps"] = json.loads(d.get("apps") or "[]")
    except Exception:
        d["apps"] = []
    return d


# ─────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────

@router.get("/api/workspaces")
def list_workspaces():
    """List all saved workspaces."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM workspaces ORDER BY last_used DESC NULLS LAST, created_at DESC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.RED + f"[WORKSPACES] list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/workspaces")
def create_workspace(body: WorkspaceCreate):
    """Create/save a new workspace."""
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Workspace name cannot be empty")

    if not body.apps:
        raise HTTPException(status_code=400, detail="Workspace must have at least one app")

    now_iso = datetime.now().isoformat()

    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO workspaces
                    (name, description, apps, icon, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    body.name.strip(),
                    body.description,
                    json.dumps(body.apps),
                    body.icon,
                    now_iso,
                    now_iso,
                )
            )
            conn.commit()
            new_id = cursor.lastrowid

            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (new_id,)
            ).fetchone()

        print(Fore.GREEN + f"[WORKSPACES] Created #{new_id}: {body.name} ({len(body.apps)} apps)")
        return {"success": True, "workspace": _row_to_dict(row)}

    except Exception as e:
        print(Fore.RED + f"[WORKSPACES] create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/workspaces/{workspace_id}")
def update_workspace(workspace_id: int, body: WorkspaceUpdate):
    """Update workspace fields."""
    try:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

            updates = []
            params = []

            if body.name is not None:
                if not body.name.strip():
                    raise HTTPException(status_code=400, detail="Name cannot be empty")
                updates.append("name = ?")
                params.append(body.name.strip())

            if body.description is not None:
                updates.append("description = ?")
                params.append(body.description)

            if body.apps is not None:
                updates.append("apps = ?")
                params.append(json.dumps(body.apps))

            if body.icon is not None:
                updates.append("icon = ?")
                params.append(body.icon)

            if not updates:
                return {"success": True, "workspace": _row_to_dict(existing)}

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            params.append(workspace_id)
            conn.execute(
                f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

            updated = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()

        print(Fore.GREEN + f"[WORKSPACES] Updated #{workspace_id}")
        return {"success": True, "workspace": _row_to_dict(updated)}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[WORKSPACES] update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int):
    """Delete a workspace."""
    try:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT id, name FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

            conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            conn.commit()

        print(Fore.GREEN + f"[WORKSPACES] Deleted #{workspace_id}: {existing['name']}")
        return {"success": True, "deleted_id": workspace_id}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[WORKSPACES] delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/workspaces/scan")
def scan_current_workspace():
    """
    Scan currently open windows and return workspace snapshot (not saved).
    User previews it then decides to save with a name.

    STUB IN PHASE 1: Returns example structure.
    REAL IMPLEMENTATION: Phase 4 (hands/workspace.py)
    """
    try:
        # In Phase 4 this will call hands.workspace.scan_current()
        # For now return stub so UI can be developed against real API shape
        try:
            from hands.workspace import scan_current
            apps = scan_current()
        except ImportError:
            # Stub for Phase 1
            apps = [
                {"type": "app", "name": "Chrome", "note": "stub — Phase 4 will scan real data"},
                {"type": "app", "name": "VS Code", "note": "stub"},
            ]

        return {
            "success":     True,
            "app_count":   len(apps),
            "apps":        apps,
            "scanned_at":  datetime.now().isoformat(),
        }

    except Exception as e:
        print(Fore.RED + f"[WORKSPACES] scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/workspaces/{workspace_id}/restore")
def restore_workspace(workspace_id: int):
    """
    Restore a saved workspace — launches all apps in parallel.

    STUB IN PHASE 1: Just increments use count.
    REAL IMPLEMENTATION: Phase 4 (hands/workspace.py)
    """
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

            workspace = _row_to_dict(row)

            # Update use stats
            conn.execute(
                "UPDATE workspaces SET use_count = use_count + 1, last_used = ? WHERE id = ?",
                (datetime.now().isoformat(), workspace_id)
            )
            conn.commit()

        # In Phase 4 this will call hands.workspace.restore(workspace["apps"])
        try:
            from hands.workspace import restore
            restore(workspace["apps"])
        except ImportError:
            print(Fore.YELLOW + f"[WORKSPACES] restore stub — Phase 4 will implement")

        return {
            "success":    True,
            "workspace":  workspace["name"],
            "app_count":  len(workspace["apps"]),
            "message":    f"Restoring {workspace['name']} ({len(workspace['apps'])} apps)",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[WORKSPACES] restore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# DIRECT DB ACCESS
# ─────────────────────────────────────────────────────────────────────────

def db_get_workspace_by_id(workspace_id):
    """Get workspace by ID. Used by trigger execution."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None
    except Exception:
        return None


def db_get_workspace_by_name(name):
    """Get workspace by name (case insensitive). Used by voice commands."""
    if not name:
        return None
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE LOWER(name) = ?",
                (name.lower().strip(),)
            ).fetchone()
        return _row_to_dict(row) if row else None
    except Exception:
        return None