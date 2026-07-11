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


class TabSyncPayload(BaseModel):
    timestamp: str
    browser:   str = "chrome"
    profile:   str = "default"
    windows:   list = []


@router.post("/api/chrome/tabs")
def receive_tabs(payload: TabSyncPayload):
    """
    Receive tab data from Chrome extension.
    Called every 3 seconds per Chrome profile.
    """
    global _last_update

    profile = payload.profile or "default"
    
    _tab_snapshots[profile] = {
        "timestamp": payload.timestamp,
        "browser":   payload.browser,
        "profile":   profile,
        "windows":   payload.windows,
        "received":  datetime.now().isoformat(),
    }
    
    _last_update = time.time()

    # Count total tabs across all windows
    total_tabs = sum(
        len(w.get("tabs", [])) for w in payload.windows
    )

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
    """Check if Chrome extension is connected and sending data."""
    age = time.time() - _last_update if _last_update > 0 else -1

    return {
        "connected":     age >= 0 and age < 10,
        "last_update":   _last_update,
        "age_seconds":   round(age, 1) if age >= 0 else -1,
        "profiles":      list(_tab_snapshots.keys()),
        "profile_count": len(_tab_snapshots),
    }


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