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
    """
    Professional silent update flow.
    
    Creates a detached launcher script that:
      1. Waits for Electron and Python to fully exit
      2. Kills any remaining processes (safety net)
      3. Runs the NSIS installer silently (/S flag, no UI)
      4. Relaunches the updated app automatically
      5. Cleans up the installer and itself
    
    The user sees: click -> app closes instantly -> new version opens.
    No install wizard, no progress bars, no file-lock errors.
    """
    try:
        import subprocess
        import tempfile

        updater = _get_updater()
        state   = updater.get_state()
        installer_path = state.get("download_path")

        if not installer_path:
            raise HTTPException(status_code=400, detail="No download in progress")
        if not os.path.exists(installer_path):
            raise HTTPException(status_code=400, detail="Downloaded file not found. Please download again.")

        # ── Build the silent update launcher script ──
        # This .bat runs completely independently after the app exits.
        bat_lines = [
            "@echo off",
            "title Seven Update",
            "",
            ":: Wait for Electron and Python to fully exit",
            "timeout /t 2 /nobreak >nul",
            "",
            ":: Safety net: kill any remaining Seven processes",
            "taskkill /f /im SEVEN.exe 2>nul",
            "",
            ":: Wait for file handles to release (prevents 'Failed to uninstall' error)",
            "timeout /t 2 /nobreak >nul",
            "",
            ":: Run installer silently. /S = no UI, no wizard, no prompts.",
            ":: NSIS reads the install path from the registry automatically.",
            '"' + installer_path + '" /S',
            "",
            ":: Wait for installer to finish writing files",
            "timeout /t 3 /nobreak >nul",
            "",
            ":: Relaunch the updated app",
            'if exist "%LOCALAPPDATA%\\Programs\\SEVEN\\SEVEN.exe" (',
            '    start "" "%LOCALAPPDATA%\\Programs\\SEVEN\\SEVEN.exe"',
            ') else if exist "%PROGRAMFILES%\\SEVEN\\SEVEN.exe" (',
            '    start "" "%PROGRAMFILES%\\SEVEN\\SEVEN.exe"',
            ')',
            "",
            ":: Clean up installer and this script",
            'del /f /q "' + installer_path + '" 2>nul',
            'del /f /q "%~f0" 2>nul',
        ]

        bat_path = os.path.join(tempfile.gettempdir(), "seven_update_launcher.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(bat_lines))

        print("[UPDATER] Launcher script created: " + bat_path)

        # Launch the bat script as a fully detached process.
        # It survives after Electron and Python exit.
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS         = 0x00000008

        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            close_fds=True,
            shell=False,
            cwd=tempfile.gettempdir(),
        )
        print("[UPDATER] Silent update launcher started")

        # Clear pending state
        try:
            updater._clear_pending_download()
            updater._state["download_path"]     = None
            updater._state["download_progress"] = 0
            updater._state["update_available"]  = False
            updater._state["info"]              = None
        except Exception:
            pass

        return {"success": True, "installer_path": installer_path, "quit": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))