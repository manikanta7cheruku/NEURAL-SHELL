"""
hands/workspace_modules/browser_tabs.py

What is open in each browser window, read through Windows UI Automation: the same accessibility tree screen
readers use. It needs no extension and works for Chrome, Edge and Brave.

    tab titles     every TabItem in the window's tab strip, in order
    active URL     the value of the address bar (the selected tab only)

URLs of the other tabs are not exposed to UI Automation. They come from the Seven extension when it is installed
(backend/routes/chrome.py), matched to these titles. Chromium's own session file holds them too, but the browser
keeps it locked while it runs.
"""

import re
import threading
from typing import Dict

_TAB_ITEM, _EDIT, _BUTTON, _VALUE_PATTERN = 50019, 50004, 50000, 10002
# Browsers append state to a tab's accessible name: "Notes - Memory usage - 120 MB", "Song - Audio playing".
_STATE_SUFFIX = re.compile(r"\s+-\s+(?:Memory usage\b.*|Audio playing|Muted|Pinned|Network error|Crashed|"
                           r"Recording|Sharing your screen|Camera in use|Microphone in use|Paused)$", re.I)
_local = threading.local()


def _uia():
    """One UI Automation client per thread (COM objects are apartment-bound)."""
    client = getattr(_local, "client", None)
    if client is None:
        import comtypes.client
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U
        client = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
        _local.client, _local.U = client, U
    return client, _local.U


def normalize_address(value: str) -> str:
    """The address bar hides the scheme ("google.com/search?q=x", "M:/notes.pdf"). Put it back."""
    value = (value or "").strip()
    if not value or "://" in value or value.startswith(("about:", "data:")):
        return value
    if len(value) > 2 and value[1] == ":" and value[2] in "/\\":
        return "file:///" + value.replace("\\", "/")
    return "https://" + value


def window_tabs(hwnd: int) -> Dict:
    """{"titles", "active_url", "buttons"} for one browser window, or empty values if it cannot be read.
    buttons are the toolbar button names: Chrome's profile button carries the profile name ("Incognito" too)."""
    try:
        uia, U = _uia()
        root = uia.ElementFromHandle(hwnd)
        found = root.FindAll(4, uia.CreatePropertyCondition(30003, _TAB_ITEM))
        titles = [_STATE_SUFFIX.sub("", found.GetElement(i).CurrentName or "").strip() for i in range(found.Length)]
        bfound = root.FindAll(4, uia.CreatePropertyCondition(30003, _BUTTON))
        buttons = [n for n in (bfound.GetElement(i).CurrentName for i in range(bfound.Length)) if n and len(n) < 60]
        active = ""
        edit = root.FindFirst(4, uia.CreatePropertyCondition(30003, _EDIT))
        if edit:
            try:
                pattern = edit.GetCurrentPattern(_VALUE_PATTERN).QueryInterface(U.IUIAutomationValuePattern)
                active = normalize_address(pattern.CurrentValue)
            except Exception:
                pass
        return {"titles": [t for t in titles if t], "active_url": active, "buttons": buttons}
    except Exception:
        return {"titles": [], "active_url": "", "buttons": []}
