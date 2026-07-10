"""
=============================================================================
hands/workspace.py

Workspace scanner and restorer.
Scans all open windows on the system and captures their state.
Restores everything in parallel for speed.

SCAN CAPTURES:
  - All visible windows (title, process name, exe path)
  - Chrome/Edge tabs (URLs + titles via DevTools Protocol)
  - VS Code workspaces (via SQLite state.vscdb)
  - File Explorer open folders (via Shell COM interface)
  - PDF/document file paths
  - Window positions and sizes

RESTORE:
  - Launches all apps in parallel threads
  - Chrome opens with all saved tab URLs
  - VS Code opens saved workspace
  - Explorer opens saved folders
  - Other apps launch by exe path or name

PERFORMANCE:
  Scan:    200-500ms for typical desktop (10-20 windows)
  Restore: 2-5 seconds parallel launch (depends on app count)

DEPENDENCIES:
  pywin32 (already installed — win32gui, win32process, win32com)
  psutil  (already installed)
=============================================================================
"""

import os
import sys
import json
import time
import subprocess
import threading
from colorama import Fore

try:
    import win32gui
    import win32process
    import win32con
    import psutil
except ImportError:
    print(Fore.YELLOW + "[WORKSPACE] pywin32 or psutil not available")


# ─────────────────────────────────────────────────────────────────────────
# KNOWN APP CLASSIFICATIONS
# Maps process names to friendly app types for UI
# ─────────────────────────────────────────────────────────────────────────

_BROWSER_PROCESSES = {
    "chrome.exe":    "chrome",
    "msedge.exe":    "edge",
    "firefox.exe":   "firefox",
    "brave.exe":     "brave",
    "opera.exe":     "opera",
    "vivaldi.exe":   "vivaldi",
}

_EDITOR_PROCESSES = {
    "code.exe":           "vscode",
    "code - insiders.exe": "vscode",
    "notepad.exe":        "notepad",
    "notepad++.exe":      "notepad++",
    "sublime_text.exe":   "sublime",
    "devenv.exe":         "visual_studio",
    "idea64.exe":         "intellij",
    "pycharm64.exe":      "pycharm",
    "webstorm64.exe":     "webstorm",
}

_MEDIA_PROCESSES = {
    "spotify.exe":      "spotify",
    "vlc.exe":          "vlc",
    "wmplayer.exe":     "media_player",
}

_SKIP_PROCESSES = {
    "explorer.exe",        # Desktop shell (not file explorer windows)
    "searchhost.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "systemsettings.exe",
    "textinputhost.exe",
    "widgetservice.exe",
    "applicationframehost.exe",
    "taskmgr.exe",
    "runtimebroker.exe",
    "searchui.exe",
    "lockapp.exe",
}

_SKIP_TITLES = {
    "", "program manager", "windows input experience",
    "microsoft text input application",
    "settings", "search",
}


# ─────────────────────────────────────────────────────────────────────────
# SCAN CURRENT WORKSPACE
# ─────────────────────────────────────────────────────────────────────────

def scan_current():
    """
    Scan all visible windows and return workspace config list.

    Returns:
        list of app configs, each is a dict like:
        {
            "type": "chrome",
            "name": "Google Chrome",
            "exe_path": "C:\\...\\chrome.exe",
            "tabs": [...],            # for browsers
            "workspace_path": "...",  # for VS Code
            "folder_path": "...",     # for Explorer
            "file_path": "...",       # for documents
            "window": {
                "title": "...",
                "x": 0, "y": 0,
                "width": 1920, "height": 1080
            }
        }
    """
    print(Fore.CYAN + "[WORKSPACE] Scanning current desktop...")
    start_time = time.time()

    apps = []
    seen_pids = set()
    seen_exe_paths = set()

    def enum_callback(hwnd, _):
        """Callback for EnumWindows — processes each visible window."""
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            if not title or title.lower() in _SKIP_TITLES:
                return

            # Get process info
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid in seen_pids:
                return

            try:
                proc = psutil.Process(pid)
                exe_name = proc.name().lower()
                exe_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return

            if exe_name in _SKIP_PROCESSES:
                return

            # Skip if we already captured this exe (avoid duplicates)
            exe_key = exe_path.lower() if exe_path else exe_name
            if exe_key in seen_exe_paths:
                return

            seen_pids.add(pid)
            seen_exe_paths.add(exe_key)

            # Get window position
            try:
                rect = win32gui.GetWindowRect(hwnd)
                window_info = {
                    "title": title,
                    "x": rect[0],
                    "y": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                }
            except Exception:
                window_info = {"title": title}

            # Classify the window
            app_config = _classify_window(exe_name, exe_path, title, window_info, pid)
            if app_config:
                apps.append(app_config)

        except Exception:
            pass

    win32gui.EnumWindows(enum_callback, None)

    # Scan Chrome tabs separately (requires DevTools)
    _enrich_browser_tabs(apps)

    # Scan VS Code state separately
    _enrich_vscode_state(apps)

    # Scan Explorer folders separately
    _scan_explorer_folders(apps)

    elapsed = int((time.time() - start_time) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Scanned {len(apps)} apps in {elapsed}ms")

    return apps


def _classify_window(exe_name, exe_path, title, window_info, pid):
    """Classify a window into an app config dict."""

    # Browser
    if exe_name in _BROWSER_PROCESSES:
        browser_type = _BROWSER_PROCESSES[exe_name]
        return {
            "type": browser_type,
            "name": title.split(" - ")[-1] if " - " in title else browser_type.title(),
            "exe_path": exe_path,
            "tabs": [],  # filled by _enrich_browser_tabs
            "window": window_info,
            "pid": pid,
        }

    # Editor
    if exe_name in _EDITOR_PROCESSES:
        editor_type = _EDITOR_PROCESSES[exe_name]
        return {
            "type": editor_type,
            "name": title,
            "exe_path": exe_path,
            "workspace_path": "",  # filled by _enrich_vscode_state
            "files": [],
            "window": window_info,
            "pid": pid,
        }

    # Media
    if exe_name in _MEDIA_PROCESSES:
        media_type = _MEDIA_PROCESSES[exe_name]
        return {
            "type": media_type,
            "name": title,
            "exe_path": exe_path,
            "window": window_info,
            "pid": pid,
        }

    # File Explorer (special — handled by _scan_explorer_folders)
    if exe_name == "explorer.exe" and title and title.lower() != "program manager":
        return {
            "type": "explorer",
            "name": title,
            "folder_path": "",  # filled by _scan_explorer_folders
            "window": window_info,
            "pid": pid,
        }

    # PDF / Document viewers
    _doc_exts = [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md"]
    for ext in _doc_exts:
        if ext in title.lower():
            return {
                "type": "document",
                "name": title,
                "exe_path": exe_path,
                "file_path": _extract_file_path_from_title(title),
                "window": window_info,
                "pid": pid,
            }

    # Generic app
    return {
        "type": "app",
        "name": title.split(" - ")[-1] if " - " in title else exe_name.replace(".exe", "").title(),
        "exe_path": exe_path,
        "window": window_info,
        "pid": pid,
    }


def _extract_file_path_from_title(title):
    """Try to extract file path from window title (many apps show it)."""
    # Many apps show "filename.ext - AppName" or "path\\file - AppName"
    parts = title.split(" - ")
    if len(parts) >= 2:
        potential_path = parts[0].strip()
        if os.path.exists(potential_path):
            return potential_path
        # Try common locations
        for base in [os.path.expanduser("~"), "C:\\", "D:\\"]:
            full = os.path.join(base, potential_path)
            if os.path.exists(full):
                return full
    return ""


# ─────────────────────────────────────────────────────────────────────────
# CHROME TAB SCANNING
# ─────────────────────────────────────────────────────────────────────────

def _enrich_browser_tabs(apps):
    """
    Read Chrome/Edge tab URLs via DevTools Protocol.
    Requires Chrome to be running with --remote-debugging-port=9222.
    Falls back to title-only if DevTools not available.
    """
    browser_apps = [a for a in apps if a.get("type") in ("chrome", "edge", "brave")]
    if not browser_apps:
        return

    for browser_app in browser_apps:
        browser_type = browser_app["type"]
        port = 9222  # default DevTools port

        try:
            import requests
            r = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2)
            if r.status_code == 200:
                pages = r.json()
                tabs = []
                for page in pages:
                    if page.get("type") == "page":
                        tabs.append({
                            "url": page.get("url", ""),
                            "title": page.get("title", ""),
                        })
                browser_app["tabs"] = tabs
                print(Fore.CYAN + f"[WORKSPACE] {browser_type}: {len(tabs)} tabs captured via DevTools")
                return
        except Exception:
            pass

        # Fallback: just capture the window title (no URLs)
        title = browser_app.get("window", {}).get("title", "")
        if title:
            browser_app["tabs"] = [{"url": "", "title": title}]
            print(Fore.YELLOW + f"[WORKSPACE] {browser_type}: DevTools not available, title only")


# ─────────────────────────────────────────────────────────────────────────
# VS CODE STATE SCANNING
# ─────────────────────────────────────────────────────────────────────────

def _enrich_vscode_state(apps):
    """
    Read VS Code recently opened workspace from its SQLite state database.
    Location: %APPDATA%/Code/User/globalStorage/state.vscdb
    """
    vscode_apps = [a for a in apps if a.get("type") == "vscode"]
    if not vscode_apps:
        return

    appdata = os.environ.get("APPDATA", "")
    state_db = os.path.join(appdata, "Code", "User", "globalStorage", "state.vscdb")

    if not os.path.exists(state_db):
        print(Fore.YELLOW + "[WORKSPACE] VS Code state.vscdb not found")
        return

    try:
        import sqlite3
        conn = sqlite3.connect(state_db, timeout=2)
        cursor = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            entries = data.get("entries", [])
            if entries:
                # Most recent workspace
                recent = entries[0]
                workspace_path = recent.get("folderUri", "").replace("file:///", "").replace("/", "\\")

                for vs_app in vscode_apps:
                    vs_app["workspace_path"] = workspace_path
                    print(Fore.CYAN + f"[WORKSPACE] VS Code workspace: {workspace_path}")

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] VS Code state read error: {e}")


# ─────────────────────────────────────────────────────────────────────────
# FILE EXPLORER FOLDER SCANNING
# ─────────────────────────────────────────────────────────────────────────

def _scan_explorer_folders(apps):
    """
    Read open File Explorer windows and get their current folder paths.
    Uses Windows Shell COM interface (IShellWindows).
    """
    explorer_apps = [a for a in apps if a.get("type") == "explorer"]
    if not explorer_apps:
        return

    try:
        import win32com.client
        shell = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()

        explorer_folders = []
        for i in range(windows.Count):
            try:
                window = windows.Item(i)
                if window is None:
                    continue

                location_url = window.LocationURL
                location_name = window.LocationName

                if location_url:
                    # Convert file:///C:/Users/... to C:\Users\...
                    folder_path = location_url.replace("file:///", "").replace("/", "\\")
                    # URL decode
                    from urllib.parse import unquote
                    folder_path = unquote(folder_path)

                    explorer_folders.append({
                        "path": folder_path,
                        "name": location_name,
                    })
            except Exception:
                continue

        # Match folders to our explorer app entries
        for i, exp_app in enumerate(explorer_apps):
            if i < len(explorer_folders):
                exp_app["folder_path"] = explorer_folders[i]["path"]
                exp_app["name"] = explorer_folders[i]["name"]
                print(Fore.CYAN + f"[WORKSPACE] Explorer folder: {explorer_folders[i]['path']}")

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Explorer scan error: {e}")


# ─────────────────────────────────────────────────────────────────────────
# WORKSPACE RESTORE
# ─────────────────────────────────────────────────────────────────────────

def restore(apps_config):
    """
    Restore a workspace by launching all apps in parallel.

    Args:
        apps_config: list of app config dicts from workspace JSON

    Each app launches in its own thread for speed.
    Total restore time: 2-5 seconds for typical workspace.
    """
    if not apps_config:
        print(Fore.YELLOW + "[WORKSPACE] Nothing to restore")
        return

    print(Fore.CYAN + f"[WORKSPACE] Restoring {len(apps_config)} apps...")
    start_time = time.time()

    threads = []
    for app_cfg in apps_config:
        t = threading.Thread(
            target=_restore_single_app,
            args=(app_cfg,),
            daemon=True
        )
        t.start()
        threads.append(t)

    # Wait for all (max 20 seconds)
    for t in threads:
        t.join(timeout=20)

    elapsed = int((time.time() - start_time) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Restored {len(apps_config)} apps in {elapsed}ms")


def _restore_single_app(app_cfg):
    """Restore a single app from its config."""
    app_type = app_cfg.get("type", "app")
    name     = app_cfg.get("name", "unknown")

    try:
        if app_type in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(app_cfg)

        elif app_type == "vscode":
            _restore_vscode(app_cfg)

        elif app_type == "explorer":
            _restore_explorer(app_cfg)

        elif app_type == "document":
            _restore_document(app_cfg)

        elif app_type == "app":
            _restore_generic_app(app_cfg)

        elif app_type in ("spotify", "vlc", "media_player"):
            _restore_generic_app(app_cfg)

        else:
            _restore_generic_app(app_cfg)

        print(Fore.GREEN + f"  [+] {name}")

    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")


def _restore_browser(cfg):
    """Restore browser with all saved tabs."""
    tabs = cfg.get("tabs", [])
    urls = [t.get("url", "") for t in tabs if t.get("url") and t["url"].startswith("http")]

    browser_type = cfg.get("type", "chrome")
    browser_cmd = {
        "chrome":  "chrome",
        "edge":    "msedge",
        "brave":   "brave",
        "firefox": "firefox",
    }.get(browser_type, "chrome")

    if urls:
        # Open browser with all tab URLs at once
        cmd = f'start {browser_cmd} {" ".join(urls)}'
        subprocess.Popen(cmd, shell=True)
    else:
        subprocess.Popen(f'start {browser_cmd}', shell=True)


def _restore_vscode(cfg):
    """Restore VS Code with workspace path."""
    workspace = cfg.get("workspace_path", "")
    if workspace and os.path.exists(workspace):
        subprocess.Popen(['code', workspace])
    else:
        subprocess.Popen(['code'])


def _restore_explorer(cfg):
    """Restore Explorer with folder path."""
    folder = cfg.get("folder_path", "")
    if folder and os.path.exists(folder):
        subprocess.Popen(['explorer', folder])
    else:
        subprocess.Popen(['explorer'])


def _restore_document(cfg):
    """Restore document file."""
    path = cfg.get("file_path", "")
    if path and os.path.exists(path):
        os.startfile(path)


def _restore_generic_app(cfg):
    """Restore any app by exe path or name."""
    exe_path = cfg.get("exe_path", "")
    name     = cfg.get("name", "")

    if exe_path and os.path.exists(exe_path):
        subprocess.Popen([exe_path])
        return

    # Try via hands.core
    try:
        from hands.core import open_app
        app_name = name.split(" - ")[-1] if " - " in name else name
        open_app(app_name)
        return
    except Exception:
        pass

    # Try AppOpener
    try:
        import AppOpener
        AppOpener.open(name)
    except Exception:
        pass