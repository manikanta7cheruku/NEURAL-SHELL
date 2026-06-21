"""
backend/routes/updates.py
Handles: /api/update/*
"""

from fastapi import APIRouter, HTTPException
import os
import sys

router = APIRouter()


def _get_updater():
    """Import updater module — handles both packaged and dev paths."""
    try:
        from backend import updater
        return updater
    except ModuleNotFoundError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import updater
        return updater


@router.get("/api/update/status")
def get_update_status():
    """Current update state — polled by React every 3 seconds."""
    try:
        updater = _get_updater()
        state   = updater.get_state()
        return {**state, "current_version": updater._read_current_version()}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "update_available":  False,
            "checking":          False,
            "downloading":       False,
            "download_progress": 0,
            "download_path":     None,
            "error":             str(e),
            "info":              None,
            "current_version":   "1.1.4"
        }


@router.post("/api/update/check")
def trigger_update_check():
    """Force an immediate update check."""
    try:
        updater = _get_updater()
        updater.check_for_updates(force=True)
        return {"success": True, "message": "Check started"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/update/download")
def trigger_download():
    """Start downloading the update in background."""
    try:
        updater = _get_updater()
        state   = updater.get_state()

        if not state["update_available"]:
            raise HTTPException(status_code=400, detail="No update available")
        if state["downloading"]:
            raise HTTPException(status_code=400, detail="Download already in progress")

        updater.start_download_thread()
        return {"success": True, "message": "Download started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/update/install")
def trigger_install():
    """Signal Electron to run the downloaded installer and quit."""
    try:
        updater = _get_updater()
        state   = updater.get_state()
        path    = state.get("download_path")

        if not path:
            raise HTTPException(status_code=400, detail="No download in progress")
        if not os.path.exists(path):
            raise HTTPException(status_code=400, detail="Downloaded file not found. Please download again.")

        try:
            updater._clear_pending_download()
            updater._state["download_path"]     = None
            updater._state["download_progress"] = 0
            updater._state["update_available"]  = False
            updater._state["info"]              = None
        except Exception:
            pass

        return {"success": True, "installer_path": path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))