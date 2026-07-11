"""
hands/workspace.py
Workspace scanner and restorer — FINAL version.

KEY FIX: Tracks windows by HWND (window handle), not PID.
This captures multiple Chrome profile windows that share one PID.

Captures:
  - ALL visible user app windows (any app with a window)
  - Chrome tabs via Seven Tab Sync extension (all profiles)
  - VS Code workspace path via state.vscdb
  - File Explorer folder paths via Shell COM
  - File paths from window titles (Notepad, Excel, PDF)
  - PowerShell/Terminal working directory
  - UWP apps (WhatsApp, Settings, Calculator, Photos)
  - Window positions and sizes

Skips:
  - Seven itself (Electron)
  - System UI (ClickToDo, TextInputHost, NVIDIA Overlay)
  - Desktop shell (Program Manager)
  - Background services
"""

import os
import sys
import json
import time
import re
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


# ── Skip lists ───────────────────────────────────────────────────────────

_SKIP_EXE_NAMES = {
    # System processes
    "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "widgetservice.exe", "applicationframehost.exe",
    "runtimebroker.exe", "lockapp.exe",
    "dllhost.exe", "ctfmon.exe", "sihost.exe",
    "taskhostw.exe", "backgroundtaskhost.exe",
    "shellhost.exe", "smartscreen.exe",
    # HP/OEM
    "clicktodo.exe",
    # GPU overlays
    "nvidia overlay.exe",
    # WebView (captured via parent app)
    "msedgewebview2.exe",
}

_SKIP_TITLE_EXACT = {
    "", "program manager", "windows input experience",
    "microsoft text input application",
    "nvidia geforce overlay", "nvidia geforce overlay dt",
    "click to do",
}

# ── App classification ───────────────────────────────────────────────────

_BROWSERS = {
    "chrome.exe": "chrome", "msedge.exe": "edge",
    "firefox.exe": "firefox", "brave.exe": "brave",
}

_EDITORS = {
    "code.exe": "vscode", "notepad.exe": "notepad",
    "notepad++.exe": "notepad++", "sublime_text.exe": "sublime",
}

_OFFICE = {
    "excel.exe": "excel", "winword.exe": "word",
    "powerpnt.exe": "powerpoint",
}

_TERMINALS = {
    "powershell.exe": "powershell", "pwsh.exe": "powershell",
    "cmd.exe": "cmd", "windowsterminal.exe": "terminal",
    "wt.exe": "terminal",
}

_UWP_APPS = {
    "whatsapp.root.exe": {"type": "uwp", "launch": "whatsapp:"},
    "systemsettings.exe": {"type": "uwp", "launch": "ms-settings:"},
    "calculatorapp.exe": {"type": "uwp", "launch": "calculator:"},
    "calculator.exe": {"type": "uwp", "launch": "calculator:"},
    "photos.exe": {"type": "uwp", "launch": "ms-photos:"},
    "mspaint.exe": {"type": "uwp", "launch": "mspaint:"},
}

# System apps that should be capturable
_SYSTEM_TOOLS = {
    "taskmgr.exe": {"type": "system_tool", "launch": "taskmgr"},
    "rundll32.exe": {"type": "system_tool"},
}


# ── SCAN ─────────────────────────────────────────────────────────────────

def scan_current():
    """
    Scan ALL visible windows. Uses window handles (hwnd) not PIDs
    to capture multiple windows from the same process (Chrome profiles).
    """
    print(Fore.CYAN + "[WORKSPACE] Scanning desktop...")
    start = time.time()

    apps = []
    seen_titles = set()  # prevent exact duplicate titles

    def enum_cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            if not title:
                return

            title_lower = title.lower().strip()

            # Skip exact title matches
            if title_lower in _SKIP_TITLE_EXACT:
                return

            # Skip duplicate titles (same window listed twice)
            if title in seen_titles:
                return

            # Get process info
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                exe_name = proc.name().lower()
                exe_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return

            # Skip by exe name
            if exe_name in _SKIP_EXE_NAMES:
                return

            # Skip Seven itself
            if exe_name == "electron.exe" and "seven" in (exe_path or "").lower():
                return

            seen_titles.add(title)

            # Get window rect
            try:
                rect = win32gui.GetWindowRect(hwnd)
                win_info = {
                    "title": title,
                    "x": rect[0], "y": rect[1],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                }
            except Exception:
                win_info = {"title": title}

            # Classify
            app_cfg = _classify(exe_name, exe_path, title, win_info, pid, proc)
            if app_cfg:
                apps.append(app_cfg)

        except Exception:
            pass

    win32gui.EnumWindows(enum_cb, None)

    # Enrich with extra data
    _enrich_browser_tabs(apps)
    _enrich_vscode(apps)
    _scan_explorer_folders(apps)

    elapsed = int((time.time() - start) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Scanned {len(apps)} apps in {elapsed}ms")
    return apps


def _classify(exe_name, exe_path, title, win_info, pid, proc):
    """Classify a window into an app config dict."""

    # Browser (each window = potentially different profile)
    if exe_name in _BROWSERS:
        return {
            "type": _BROWSERS[exe_name],
            "name": _clean_app_name(title, exe_name),
            "exe_path": exe_path,
            "tabs": [],
            "window": win_info,
        }

    # Editor
    if exe_name in _EDITORS:
        return {
            "type": _EDITORS[exe_name],
            "name": title,
            "exe_path": exe_path,
            "file_path": _extract_file_path(title),
            "workspace_path": "",
            "window": win_info,
        }

    # Office
    if exe_name in _OFFICE:
        return {
            "type": _OFFICE[exe_name],
            "name": title,
            "exe_path": exe_path,
            "file_path": _extract_file_path(title),
            "window": win_info,
        }

    # Terminal
    if exe_name in _TERMINALS:
        cwd = ""
        try:
            cwd = proc.cwd()
        except Exception:
            pass
        return {
            "type": _TERMINALS[exe_name],
            "name": title,
            "exe_path": exe_path,
            "working_dir": cwd,
            "window": win_info,
        }

    # UWP apps
    if exe_name in _UWP_APPS:
        info = _UWP_APPS[exe_name]
        return {
            "type": "uwp",
            "name": title or exe_name.replace(".exe", "").title(),
            "protocol": info.get("launch", ""),
            "window": win_info,
        }

    # UWP by path (WindowsApps or SystemApps)
    if exe_path and ("WindowsApps" in exe_path or "SystemApps" in exe_path):
        # Try known UWP names
        for known_exe, info in _UWP_APPS.items():
            if known_exe in exe_name:
                return {
                    "type": "uwp",
                    "name": title,
                    "protocol": info.get("launch", ""),
                    "window": win_info,
                }
        # Unknown UWP — skip if it looks like system junk
        if any(skip in exe_name for skip in ["background", "host", "broker", "service"]):
            return None
        # Keep other UWP apps
        return {
            "type": "uwp",
            "name": title,
            "exe_path": exe_path,
            "protocol": "",
            "window": win_info,
        }

    # System tools
    if exe_name in _SYSTEM_TOOLS:
        info = _SYSTEM_TOOLS[exe_name]
        return {
            "type": info.get("type", "app"),
            "name": title,
            "exe_path": exe_path,
            "launch_cmd": info.get("launch", ""),
            "window": win_info,
        }

    # Explorer windows (not desktop shell)
    if exe_name == "explorer.exe":
        return {
            "type": "explorer",
            "name": title,
            "folder_path": "",
            "window": win_info,
        }

    # Skip overlays
    if "overlay" in exe_name or "overlay" in title.lower():
        return None

    # Generic app (Premiere Pro, Photoshop, Spotify, anything)
    return {
        "type": "app",
        "name": _clean_app_name(title, exe_name),
        "exe_path": exe_path,
        "file_path": _extract_file_path(title),
        "window": win_info,
    }


def _clean_app_name(title, exe_name):
    """Extract clean app name from window title."""
    # "filename.py - AppName" → "AppName"
    if " - " in title:
        parts = title.split(" - ")
        return parts[-1].strip()
    return exe_name.replace(".exe", "").title()


def _extract_file_path(title):
    """Try to extract file path from window title."""
    if not title:
        return ""

    # Remove leading asterisk (unsaved indicator)
    clean = title.lstrip("*").strip()

    parts = clean.split(" - ")
    if len(parts) >= 2:
        candidate = parts[0].strip().lstrip("*").strip()

        # Direct path
        if os.path.exists(candidate):
            return os.path.abspath(candidate)

        # Check common drives
        for drive in ["C:\\", "D:\\", "E:\\", "M:\\", "F:\\"]:
            full = os.path.join(drive, candidate)
            if os.path.exists(full):
                return full

        # Check user folders
        home = os.path.expanduser("~")
        for sub in ["Desktop", "Documents", "Downloads"]:
            full = os.path.join(home, sub, candidate)
            if os.path.exists(full):
                return full

    # Look for full paths in title
    match = re.search(r'[A-Za-z]:\\[^\*\?"<>|]+\.\w+', clean)
    if match:
        path = match.group(0).strip()
        if os.path.exists(path):
            return path

    return ""


# ── Browser tabs ─────────────────────────────────────────────────────────

def _enrich_browser_tabs(apps):
    """Read Chrome tabs via Seven Tab Sync extension."""
    browsers = [a for a in apps if a.get("type") in ("chrome", "edge", "brave")]
    if not browsers:
        return

    try:
        from backend.routes.chrome import get_tabs_by_profile
        profile_tabs = get_tabs_by_profile()

        if profile_tabs:
            total = sum(len(t) for t in profile_tabs.values())
            print(Fore.GREEN + f"[WORKSPACE] Chrome tabs: {total} across {len(profile_tabs)} profiles")

            for browser in browsers:
                all_tabs = []
                for prof, tabs in profile_tabs.items():
                    for tab in tabs:
                        all_tabs.append({
                            "url": tab["url"],
                            "title": tab["title"],
                            "profile": prof,
                            "pinned": tab.get("pinned", False),
                        })
                browser["tabs"] = all_tabs
                browser["profiles"] = list(profile_tabs.keys())
            return
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Extension tab read: {e}")

    # Fallback: window title only
    for b in browsers:
        title = b.get("window", {}).get("title", "")
        for suffix in [" - Google Chrome", " - Microsoft Edge", " - Brave"]:
            if title.endswith(suffix):
                title = title[:-len(suffix)]
        b["tabs"] = [{"url": "", "title": title}]
    print(Fore.YELLOW + "[WORKSPACE] Chrome tabs: title only (extension not installed)")


# ── VS Code ──────────────────────────────────────────────────────────────

def _enrich_vscode(apps):
    """Read VS Code workspace from state.vscdb."""
    vscode = [a for a in apps if a.get("type") == "vscode"]
    if not vscode:
        return

    appdata = os.environ.get("APPDATA", "")
    db = os.path.join(appdata, "Code", "User", "globalStorage", "state.vscdb")
    if not os.path.exists(db):
        return

    try:
        import sqlite3
        from urllib.parse import unquote
        conn = sqlite3.connect(db, timeout=2)
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'"
        ).fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            entries = data.get("entries", [])
            if entries:
                ws = entries[0].get("folderUri", "").replace("file:///", "").replace("/", "\\")
                ws = unquote(ws)
                if len(ws) >= 2 and ws[1] == ":":
                    ws = ws[0].upper() + ws[1:]
                for v in vscode:
                    v["workspace_path"] = ws
                print(Fore.CYAN + f"[WORKSPACE] VS Code: {ws}")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] VS Code state: {e}")


# ── Explorer folders ─────────────────────────────────────────────────────

def _scan_explorer_folders(apps):
    """Get Explorer window folder paths via Shell COM."""
    explorers = [a for a in apps if a.get("type") == "explorer"]
    if not explorers:
        return

    try:
        import win32com.client
        from urllib.parse import unquote

        shell = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()

        folders = []
        for i in range(windows.Count):
            try:
                w = windows.Item(i)
                if w and w.LocationURL:
                    path = unquote(w.LocationURL.replace("file:///", "").replace("/", "\\"))
                    folders.append({"path": path, "name": w.LocationName or ""})
            except Exception:
                continue

        for i, exp in enumerate(explorers):
            if i < len(folders):
                exp["folder_path"] = folders[i]["path"]
                if folders[i]["name"]:
                    exp["name"] = folders[i]["name"]
                print(Fore.CYAN + f"[WORKSPACE] Explorer: {folders[i]['path']}")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Explorer scan: {e}")


# ── RESTORE ──────────────────────────────────────────────────────────────

def restore(apps_config):
    """Restore workspace — all apps launch in parallel."""
    if not apps_config:
        return

    print(Fore.CYAN + f"[WORKSPACE] Restoring {len(apps_config)} apps...")
    start = time.time()

    threads = []
    for cfg in apps_config:
        t = threading.Thread(target=_restore_one, args=(cfg,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=20)

    elapsed = int((time.time() - start) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Restored in {elapsed}ms")


def _restore_one(cfg):
    """Restore a single app."""
    app_type = cfg.get("type", "app")
    name = cfg.get("name", "unknown")

    try:
        if app_type in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(cfg)
        elif app_type == "vscode":
            _restore_vscode(cfg)
        elif app_type == "explorer":
            _restore_explorer(cfg)
        elif app_type in ("notepad", "notepad++", "sublime"):
            _restore_editor(cfg)
        elif app_type in ("excel", "word", "powerpoint"):
            _restore_office(cfg)
        elif app_type == "uwp":
            _restore_uwp(cfg)
        elif app_type in ("powershell", "cmd", "terminal"):
            _restore_terminal(cfg)
        elif app_type == "system_tool":
            _restore_system_tool(cfg)
        elif app_type == "document":
            _restore_file(cfg)
        else:
            _restore_generic(cfg)
        print(Fore.GREEN + f"  [+] {name}")
    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")


def _restore_browser(cfg):
    """Restore browser with tabs from all profiles."""
    tabs = cfg.get("tabs", [])
    urls = [t["url"] for t in tabs if t.get("url", "").startswith("http")]

    browser_type = cfg.get("type", "chrome")
    browser_cmd = {
        "chrome": "chrome", "edge": "msedge",
        "firefox": "firefox", "brave": "brave",
    }.get(browser_type, "chrome")

    if not urls:
        subprocess.Popen(f'start {browser_cmd}', shell=True)
        return

    # Open in batches of 5
    for i in range(0, len(urls), 5):
        batch = urls[i:i+5]
        url_args = " ".join(f'"{u}"' for u in batch)
        subprocess.Popen(f'start {browser_cmd} {url_args}', shell=True)
        if i + 5 < len(urls):
            time.sleep(1)

    print(f"[WORKSPACE] {browser_type}: {len(urls)} tabs opened")


def _restore_vscode(cfg):
    ws = cfg.get("workspace_path", "")
    fp = cfg.get("file_path", "")
    if ws and os.path.exists(ws):
        subprocess.Popen(['code', ws])
    elif fp and os.path.exists(fp):
        subprocess.Popen(['code', fp])
    else:
        subprocess.Popen(['code'])


def _restore_explorer(cfg):
    folder = cfg.get("folder_path", "")
    if folder and os.path.exists(folder):
        subprocess.Popen(['explorer', folder])
    else:
        subprocess.Popen(['explorer'])


def _restore_editor(cfg):
    fp = cfg.get("file_path", "")
    exe = cfg.get("exe_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    elif exe and os.path.exists(exe):
        subprocess.Popen([exe])
    else:
        _restore_generic(cfg)


def _restore_office(cfg):
    fp = cfg.get("file_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    else:
        _restore_generic(cfg)


def _restore_uwp(cfg):
    protocol = cfg.get("protocol", "")
    if protocol:
        try:
            os.startfile(protocol)
        except Exception:
            _restore_generic(cfg)
    else:
        _restore_generic(cfg)


def _restore_terminal(cfg):
    cwd = cfg.get("working_dir", "")
    app_type = cfg.get("type", "powershell")
    exe = "powershell" if app_type in ("powershell", "terminal") else "cmd"

    if cwd and os.path.exists(cwd):
        subprocess.Popen([exe], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([exe], creationflags=subprocess.CREATE_NEW_CONSOLE)


def _restore_system_tool(cfg):
    launch = cfg.get("launch_cmd", "")
    if launch:
        subprocess.Popen(launch, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        _restore_generic(cfg)


def _restore_file(cfg):
    fp = cfg.get("file_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    else:
        _restore_generic(cfg)


def _restore_generic(cfg):
    exe = cfg.get("exe_path", "")
    name = cfg.get("name", "")

    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe])
            return
        except Exception:
            pass

    clean = name.split(" - ")[-1].strip() if " - " in name else name
    try:
        from hands.core import open_app
        open_app(clean)
    except Exception:
        try:
            import AppOpener
            AppOpener.open(clean)
        except Exception:
            pass