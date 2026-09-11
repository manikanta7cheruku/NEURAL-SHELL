"""
backend/routes/panel_extras.py
Panel-specific endpoints: close-all, restore, trigger inline edit.
"""

import os
import json
import time
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from colorama import Fore
from typing import Optional

router = APIRouter()


class CloseAllRequest(BaseModel):
    save_workspace: bool = True
    skip_media: bool = True


class InlineHotkeyEdit(BaseModel):
    trigger_id: int
    new_hotkey: str


@router.post("/panel/close-all")
def close_all_apps(body: CloseAllRequest):
    """
    Close all visible user apps, optionally saving as a recovery workspace.
    Skips: Explorer shell, SEVEN processes, playing media (if skip_media=True).
    Returns list of closed apps and workspace ID if saved.
    """
    try:
        import win32gui
        import win32con
        import win32process
        import psutil
    except ImportError:
        raise HTTPException(status_code=500, detail="pywin32 not available")

    _SKIP_PROCESSES = {
        "explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
        "textinputhost.exe", "runtimebroker.exe", "startmenuexperiencehost.exe",
        "applicationframehost.exe", "systemsettings.exe", "lockapp.exe",
        "seven.exe", "electron.exe", "python.exe", "pythonw.exe",
    }

    _MEDIA_PROCESSES = {
        "spotify.exe", "vlc.exe", "wmplayer.exe", "groove.exe",
        "itunes.exe", "musicbee.exe", "foobar2000.exe",
    }

    closed_apps = []
    skipped_apps = []
    windows_to_close = []

    def _enum_cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return
        if title.strip().lower() == "program manager":
            return

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            exe_name = proc.name().lower()
            exe_path = (proc.exe() or "").lower()
        except Exception:
            return

        if exe_name in _SKIP_PROCESSES:
            return
        if "seven" in exe_path or "mk-projects" in exe_path:
            return

        if body.skip_media and exe_name in _MEDIA_PROCESSES:
            skipped_apps.append({"name": title, "reason": "media_playing"})
            return

        windows_to_close.append({
            "hwnd": hwnd,
            "title": title,
            "exe_name": exe_name,
            "exe_path": exe_path,
            "pid": pid,
        })

    win32gui.EnumWindows(_enum_cb, None)

    # Save workspace before closing (if requested)
    workspace_id = None
    if body.save_workspace and windows_to_close:
        try:
            from hands.workspace import scan_current
            apps = scan_current()
            if apps:
                now_str = datetime.now().strftime("%b %d %Y %I:%M%p")
                ws_name = f"Recovery {now_str}"

                from backend.routes.workspaces import _get_conn
                import json as _json
                conn = _get_conn()
                cursor = conn.execute(
                    "INSERT INTO workspaces (name, description, apps, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (ws_name, f"Auto-saved before Close All ({len(apps)} apps)",
                     _json.dumps([{k: v for k, v in a.items() if k != "pid"} for a in apps]),
                     datetime.now().isoformat(), datetime.now().isoformat())
                )
                conn.commit()
                workspace_id = cursor.lastrowid
                conn.close()
                print(Fore.GREEN + f"[PANEL] Recovery workspace saved: #{workspace_id} '{ws_name}'")
        except Exception as e:
            print(Fore.YELLOW + f"[PANEL] Recovery save failed: {e}")

    # Close windows
    for win in windows_to_close:
        try:
            win32gui.PostMessage(win["hwnd"], win32con.WM_CLOSE, 0, 0)
            closed_apps.append(win["title"])
        except Exception:
            pass

    return {
        "success": True,
        "closed_count": len(closed_apps),
        "closed_apps": closed_apps,
        "skipped": skipped_apps,
        "workspace_id": workspace_id,
    }


@router.post("/panel/restore-last")
def restore_last_workspace():
    """Restore the most recent recovery workspace."""
    try:
        from backend.routes.workspaces import _get_conn, _row_to_dict
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM workspaces WHERE name LIKE 'Recovery%' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()

        if not row:
            return {"success": False, "message": "No recovery workspace found"}

        workspace = _row_to_dict(row)

        from hands.workspace import smart_restore
        threading.Thread(
            target=smart_restore,
            args=(workspace["apps"],),
            daemon=True
        ).start()

        return {
            "success": True,
            "workspace": workspace["name"],
            "app_count": len(workspace["apps"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/panel/triggers-compact")
def get_triggers_compact():
    """Get all triggers in compact format for panel display."""
    try:
        from backend.routes.triggers import _get_conn, _row_to_dict
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM triggers ORDER BY "
                "CASE WHEN hotkey IS NOT NULL THEN 0 "
                "WHEN voice_phrase IS NOT NULL THEN 1 "
                "WHEN audio_pattern IS NOT NULL THEN 2 "
                "ELSE 3 END, name ASC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        return []


@router.put("/panel/triggers/{trigger_id}/hotkey")
def inline_edit_hotkey(trigger_id: int, body: InlineHotkeyEdit):
    """Edit a trigger's hotkey inline from the panel."""
    try:
        from backend.routes.triggers import (
            _get_conn, _row_to_dict, _normalize_hotkey,
            _check_hotkey_conflict, _signal_daemon_reload
        )

        if not body.new_hotkey or not body.new_hotkey.strip():
            raise HTTPException(status_code=400, detail="Hotkey cannot be empty")

        normalized = _normalize_hotkey(body.new_hotkey)

        conflict = _check_hotkey_conflict(normalized, exclude_id=trigger_id)
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Already used by '{conflict['name']}'"
            )

        with _get_conn() as conn:
            conn.execute(
                "UPDATE triggers SET hotkey = ?, updated_at = ? WHERE id = ?",
                (normalized, datetime.now().isoformat(), trigger_id)
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM triggers WHERE id = ?", (trigger_id,)
            ).fetchone()

        _signal_daemon_reload()
        return {"success": True, "trigger": _row_to_dict(row)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))