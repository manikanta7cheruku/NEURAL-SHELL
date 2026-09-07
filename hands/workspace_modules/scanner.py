"""
hands/workspace_modules/scanner.py
Desktop scanner — enumerates all visible user-opened windows.
Classifies each into an app config dict.
"""
import time
from colorama import Fore

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    pass

from hands.workspace_modules.filters import is_seven_process, has_taskbar_presence


# ── App type maps ────────────────────────────────────────────────────────

BROWSERS = {
    "chrome.exe": "chrome",
    "msedge.exe": "edge",
    "firefox.exe": "firefox",
    "brave.exe":   "brave",
}

EDITORS = {
    "code.exe":         "vscode",
    "notepad.exe":      "notepad",
    "notepad++.exe":    "notepad++",
    "sublime_text.exe": "sublime",
}

OFFICE = {
    "excel.exe":    "excel",
    "winword.exe":  "word",
    "powerpnt.exe": "powerpoint",
}

TERMINALS = {
    "powershell.exe":      "powershell",
    "pwsh.exe":            "powershell",
    "cmd.exe":             "cmd",
    "windowsterminal.exe": "terminal",
    "wt.exe":              "terminal",
}


# ── Public API ───────────────────────────────────────────────────────────

def scan_current():
    """
    Scan all visible user-opened windows and return app configs.
    Filters out system utilities, Seven's own processes, GPU overlays.
    """
    print(Fore.CYAN + "[WORKSPACE] Scanning desktop...")
    t0 = time.time()

    apps         = []
    seen_windows = set()

    def _cb(hwnd, _):
        try:
            if not has_taskbar_presence(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            try:
                proc     = psutil.Process(pid)
                exe_name = proc.name().lower()
                exe_path = proc.exe()
            except Exception:
                return

            if is_seven_process(exe_name, exe_path):
                return

            window_key = (pid, title.strip().lower())
            if window_key in seen_windows:
                return
            seen_windows.add(window_key)

            try:
                rect     = win32gui.GetWindowRect(hwnd)
                win_info = {
                    "title":  title,
                    "x":      rect[0],
                    "y":      rect[1],
                    "width":  rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                }
            except Exception:
                win_info = {"title": title}

            cfg = _classify(exe_name, exe_path, title, win_info, proc)
            if cfg:
                apps.append(cfg)

        except Exception:
            pass

    win32gui.EnumWindows(_cb, None)

    from hands.workspace_modules.enrichment import (
        enrich_chrome, enrich_vscode, enrich_explorer
    )
    enrich_chrome(apps)
    enrich_vscode(apps)

    try:
        import pythoncom
        pythoncom.CoInitialize()
        enrich_explorer(apps)
        pythoncom.CoUninitialize()
    except Exception:
        enrich_explorer(apps)

    elapsed = int((time.time() - t0) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Scanned {len(apps)} apps in {elapsed}ms")
    return apps


# ── Classification ───────────────────────────────────────────────────────

def _classify(exe_name, exe_path, title, win_info, proc):
    """Classify a window into an app config."""

    if exe_name in BROWSERS:
        return {
            "type": BROWSERS[exe_name],
            "name": app_name(title, exe_name),
            "exe_path": exe_path,
            "tabs": [],
            "profile_name": "",
            "window": win_info,
            "_is_browser": True,
        }

    if exe_name in EDITORS:
        return {
            "type": EDITORS[exe_name],
            "name": title,
            "exe_path": exe_path,
            "workspace_path": "",
            "window": win_info,
        }

    if exe_name in OFFICE:
        return {
            "type": OFFICE[exe_name],
            "name": title,
            "exe_path": exe_path,
            "window": win_info,
        }

    if exe_name in TERMINALS:
        cwd = ""
        try:
            cwd = proc.cwd()
        except Exception:
            pass
        return {
            "type": TERMINALS[exe_name],
            "name": title,
            "exe_path": exe_path,
            "working_dir": cwd,
            "window": win_info,
        }

    if exe_path and ("WindowsApps" in exe_path or "SystemApps" in exe_path):
        return {
            "type": "uwp",
            "name": title or exe_name.replace(".exe", "").replace(".", " ").title(),
            "exe_path": exe_path,
            "window": win_info,
        }

    if exe_name == "explorer.exe":
        return {
            "type": "explorer",
            "name": f"File Explorer: {title}" if title else "File Explorer",
            "folder_path": "",
            "window": win_info,
        }

    return {
        "type": "app",
        "name": app_name(title, exe_name),
        "exe_path": exe_path,
        "window": win_info,
    }


def app_name(title, exe_name):
    """Extract clean app name from window title."""
    if exe_name == "explorer.exe":
        if title and title.strip():
            return f"File Explorer: {title.strip()}"
        return "File Explorer"

    if " - " in title:
        parts = title.split(" - ")
        app_part = parts[-1].strip()
        if app_part:
            return app_part
        if len(parts) >= 2:
            return parts[-2].strip()

    if title and title.strip():
        return title.strip()

    return exe_name.replace(".exe", "").replace(".", " ").title()