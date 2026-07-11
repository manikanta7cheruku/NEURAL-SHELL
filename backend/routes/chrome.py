"""
backend/routes/chrome.py

Receives and serves Chrome tab data from the Seven Tab Sync extension.

ARCHITECTURE:
  Chrome Extension → POST /api/chrome/tabs → stored in memory
  Workspace Scanner → GET /api/chrome/tabs → reads latest snapshot
  
  Data is stored IN MEMORY only (not database).
  It's real-time ephemeral data that refreshes every 3 seconds.
  No persistence needed — tabs are a live snapshot.

MULTI-PROFILE SUPPORT:
  Each Chrome profile runs its own copy of the extension.
  Each sends its own tab data with a profile identifier.
  Seven merges all profiles into one unified snapshot.
"""

import os
import sys
import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from colorama import Fore

router = APIRouter()

# ── In-memory tab storage ────────────────────────────────────────────────
# Key: profile name (string)
# Value: dict with timestamp + windows/tabs data

_tab_snapshots = {}
_last_update = 0

def get_extension_install_dir():
    try:
        from hands.chrome_setup import get_extension_install_dir as _get_dir
        return _get_dir()
    except Exception:
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "SEVEN", "chrome_extension")


class TabSyncPayload(BaseModel):
    timestamp: str
    browser:   str = "chrome"
    profile:   str = "default"
    windows:   list = []


@router.post("/api/chrome/tabs")
def receive_tabs(payload: TabSyncPayload):
    """
    Receive tab data from Chrome extension.
    Called periodically per Chrome profile.
    Keeps data from ALL profiles, not just the latest.
    """
    global _last_update

    profile = payload.profile or "default"

    total_tabs = sum(
        len(w.get("tabs", [])) for w in payload.windows
    )

    _tab_snapshots[profile] = {
        "timestamp":    payload.timestamp,
        "browser":      payload.browser,
        "profile":      profile,
        "windows":      payload.windows,
        "received":     datetime.now().isoformat(),
        "_received_ts": time.time(),
        "tab_count":    total_tabs,
    }

    _last_update = time.time()

    return {
        "success": True,
        "profile": profile,
        "windows": len(payload.windows),
        "tabs":    total_tabs,
    }


@router.get("/api/chrome/tabs")
def get_tabs(profile: Optional[str] = None):
    """
    Get latest Chrome tab snapshot.
    Used by workspace scanner to capture all open tabs.
    
    If profile specified: return only that profile's tabs.
    If no profile: return ALL profiles' tabs merged.
    """
    if not _tab_snapshots:
        return {
            "available": False,
            "message":   "No tab data received. Install the Seven Tab Sync Chrome extension.",
            "profiles":  [],
            "tabs":      [],
        }

    if profile and profile in _tab_snapshots:
        snap = _tab_snapshots[profile]
        all_tabs = []
        for win in snap.get("windows", []):
            for tab in win.get("tabs", []):
                tab["profile"] = profile
                tab["incognito"] = win.get("incognito", False)
                all_tabs.append(tab)
        return {
            "available": True,
            "profiles":  [profile],
            "tabs":      all_tabs,
            "timestamp": snap.get("timestamp"),
        }

    # Return ALL profiles
    all_tabs = []
    profiles = []
    for prof_name, snap in _tab_snapshots.items():
        profiles.append(prof_name)
        for win in snap.get("windows", []):
            for tab in win.get("tabs", []):
                tab["profile"]  = prof_name
                tab["incognito"] = win.get("incognito", False)
                all_tabs.append(tab)

    return {
        "available": True,
        "profiles":  profiles,
        "tabs":      all_tabs,
        "total":     len(all_tabs),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/chrome/tabs/status")
def get_status():
    """
    Check Chrome extension status across ALL profiles.
    Profile data is kept even when profile goes inactive.
    A profile is 'active' if synced in last 60 seconds.
    Connection is True if ANY profile synced in last 60 seconds.
    """
    now = time.time()

    total_tabs = 0
    active_profiles = 0
    profile_details = []

    for prof_name, snap in _tab_snapshots.items():
        tab_count = snap.get("tab_count", 0)
        total_tabs += tab_count

        received = snap.get("received", "")
        last_sync_time = snap.get("_received_ts", 0)
        age = now - last_sync_time if last_sync_time > 0 else -1
        is_active = age >= 0 and age < 60  # 60 second window

        if is_active:
            active_profiles += 1

        profile_details.append({
            "name":       prof_name,
            "tabs":       tab_count,
            "windows":    len(snap.get("windows", [])),
            "last_sync":  received,
            "active":     is_active,
            "age_seconds": round(age, 1) if age >= 0 else -1,
        })

    # Sort: active profiles first, then by tab count
    profile_details.sort(key=lambda p: (not p["active"], -p["tabs"]))

    connected = active_profiles > 0 or len(_tab_snapshots) > 0

    return {
        "connected":        connected,
        "total_tabs":       total_tabs,
        "profile_count":    len(_tab_snapshots),
        "active_profiles":  active_profiles,
        "profile_details":  profile_details,
        "extension_path":   get_extension_install_dir(),
    }

@router.get("/api/chrome/setup/status")
def get_setup_status():
    """Check Chrome extension status."""
    try:
        from hands.chrome_setup import check_extension_status
        return check_extension_status()
    except Exception as e:
        return {"installed": False, "connected": False, "error": str(e)}


@router.post("/api/chrome/setup/prepare")
def prepare_extension():
    """Copy extension files and get the path for user to load."""
    try:
        from hands.chrome_setup import prepare_extension, copy_path_to_clipboard

        success, path, message = prepare_extension()
        if not success:
            return {"success": False, "message": message}

        # Copy path to clipboard for easy paste
        copy_path_to_clipboard(path)

        return {
            "success": True,
            "path":    path,
            "message": "Extension ready. Path copied to clipboard.",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/chrome/setup/open")
def open_extensions_page():
    """Open Chrome extensions page."""
    try:
        from hands.chrome_setup import open_chrome_extensions_page
        success, message = open_chrome_extensions_page()
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/chrome/setup/uninstall")
def uninstall_extension():
    """Remove extension files."""
    try:
        from hands.chrome_setup import uninstall_extension
        success, message = uninstall_extension()
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/api/chrome/tabs/clear")
def clear_tabs():
    """Clear all stored tab data. Called when user disables Tab Sync."""
    global _tab_snapshots, _last_update
    _tab_snapshots = {}
    _last_update = 0
    return {"success": True, "message": "Tab data cleared"}

# ── Direct access for workspace scanner ──────────────────────────────────

def get_all_tabs():
    """
    Direct function call for workspace scanner.
    Returns list of tab dicts with url, title, profile, incognito.
    No HTTP overhead.
    """
    all_tabs = []
    for prof_name, snap in _tab_snapshots.items():
        for win in snap.get("windows", []):
            for tab in win.get("tabs", []):
                all_tabs.append({
                    "url":       tab.get("url", ""),
                    "title":     tab.get("title", ""),
                    "profile":   prof_name,
                    "incognito": win.get("incognito", False),
                    "pinned":    tab.get("pinned", False),
                    "active":    tab.get("active", False),
                })
    return all_tabs


def get_tabs_by_profile():
    """
    Returns tabs grouped by profile.
    Used by workspace restore to open correct profile's tabs.
    """
    result = {}
    for prof_name, snap in _tab_snapshots.items():
        tabs = []
        for win in snap.get("windows", []):
            for tab in win.get("tabs", []):
                url = tab.get("url", "")
                # Skip chrome internal pages
                if url.startswith("chrome://") or url.startswith("edge://"):
                    continue
                if url.startswith("chrome-extension://"):
                    continue
                tabs.append({
                    "url":    url,
                    "title":  tab.get("title", ""),
                    "pinned": tab.get("pinned", False),
                })
        if tabs:
            result[prof_name] = tabs
    return result