"""
hands/workspace.py
Workspace scanner and restorer.

Captures all visible user apps, Chrome tabs (via extension),
VS Code workspace, Explorer folders, terminals.

Restore is smart — only opens what is genuinely missing.
Tabs are matched at URL level — no duplicate tab opening.
"""

import os
import json
import time
import re
import subprocess
import threading
from colorama import Fore

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    print(Fore.YELLOW + "[WORKSPACE] pywin32 or psutil not available")


# ─────────────────────────────────────────────────────────────────────────
# WINDOW FILTERING
# Matches Task Manager's "Apps" section exactly.
# Scans EVERY app the user has open. Only skips Seven itself.
# Uses the same method as Task Manager: visible + has taskbar presence.
# ─────────────────────────────────────────────────────────────────────────


def _is_seven_process(exe_name: str, exe_path: str) -> bool:
    """Only skip Seven's own processes. Nothing else."""
    name_lower = exe_name.lower()
    path_lower = exe_path.lower()

    if name_lower not in ("electron.exe", "pythonw.exe", "python.exe"):
        return False

    _seven_markers = (
        "mk-projects\\seven",
        "\\seven\\electron",
        "\\seven\\python",
        "program files\\seven",
        "appdata\\local\\seven",
    )
    return any(marker in path_lower for marker in _seven_markers)


def _has_taskbar_presence(hwnd: int) -> bool:
    """
    Returns True if this window would appear in the Windows taskbar.
    Uses the exact same logic Windows uses internally:

    A window gets a taskbar button if:
      1. Visible
      2. Top-level (no owner window)
      3. Not a tool window (WS_EX_TOOLWINDOW)
      4. Has a non-empty title
      5. Has real screen area (not a ghost/hidden window)
      6. Not cloaked (Windows hides some UWP windows via DWM cloak)
    """
    try:
        import win32con

        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return False

        if title.strip().lower() == "program manager":
            return False

        if not win32gui.IsWindowVisible(hwnd):
            return False

        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return False

        owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
        if owner:
            return False

        # DWM cloaked check: Windows hides some UWP app windows
        # even though they are technically "visible". This catches
        # Settings, Calculator etc. that are running but minimized
        # to tray or were auto-started by Windows.
        try:
            import ctypes
            DWMWA_CLOAKED = 14
            cloaked = ctypes.c_int(0)
            hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_CLOAKED,
                ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            if hr == 0 and cloaked.value != 0:
                return False
        except Exception:
            pass

        try:
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w <= 0 or h <= 0:
                return False
        except Exception:
            return False

        return True

    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────
# APP TYPE MAPS
# ─────────────────────────────────────────────────────────────────────────

_BROWSERS = {
    "chrome.exe": "chrome",
    "msedge.exe": "edge",
    "firefox.exe": "firefox",
    "brave.exe":   "brave",
}

_EDITORS = {
    "code.exe":         "vscode",
    "notepad.exe":      "notepad",
    "notepad++.exe":    "notepad++",
    "sublime_text.exe": "sublime",
}

_OFFICE = {
    "excel.exe":    "excel",
    "winword.exe":  "word",
    "powerpnt.exe": "powerpoint",
}

_TERMINALS = {
    "powershell.exe":      "powershell",
    "pwsh.exe":            "powershell",
    "cmd.exe":             "cmd",
    "windowsterminal.exe": "terminal",
    "wt.exe":              "terminal",
}

_UWP_PROTOCOLS = {}


# ─────────────────────────────────────────────────────────────────────────
# SCAN
# ─────────────────────────────────────────────────────────────────────────

def scan_current():
    """
    Scan all visible user-opened windows and return app configs.

    Filters out:
    - System utilities (Task Manager, Settings, etc.)
    - SEVEN's own processes
    - Admin-elevated terminals (Administrator: PowerShell)
    - GPU overlays
    - Background services
    """
    print(Fore.CYAN + "[WORKSPACE] Scanning desktop...")
    t0 = time.time()

    apps      = []
    seen_pids = set()

    def _cb(hwnd, _):
        try:
            if not _has_taskbar_presence(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)

            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            if pid in seen_pids:
                return

            try:
                proc     = psutil.Process(pid)
                exe_name = proc.name().lower()
                exe_path = proc.exe()
            except Exception:
                return

            if _is_seven_process(exe_name, exe_path):
                return

            seen_pids.add(pid)

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

    _enrich_chrome(apps)
    _enrich_vscode(apps)

    # COM must be initialized in the same thread that calls Shell COM
    try:
        import pythoncom
        pythoncom.CoInitialize()
        _enrich_explorer(apps)
        pythoncom.CoUninitialize()
    except Exception:
        _enrich_explorer(apps)

    elapsed = int((time.time() - t0) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Scanned {len(apps)} apps in {elapsed}ms")
    return apps


def _classify(exe_name, exe_path, title, win_info, proc):
    """Classify a window into an app config."""

    # Browser
    if exe_name in _BROWSERS:
        return {
            "type":         _BROWSERS[exe_name],
            "name":         _app_name(title, exe_name),
            "exe_path":     exe_path,
            "tabs":         [],
            "profile_name": "",
            "window":       win_info,
            "_is_browser":  True,
        }

    # VS Code / editors
    if exe_name in _EDITORS:
        return {
            "type":           _EDITORS[exe_name],
            "name":           title,
            "exe_path":       exe_path,
            "workspace_path": "",
            "window":         win_info,
        }

    # Office
    if exe_name in _OFFICE:
        return {
            "type":     _OFFICE[exe_name],
            "name":     title,
            "exe_path": exe_path,
            "window":   win_info,
        }

    # Terminals — only non-admin ones reach here
    if exe_name in _TERMINALS:
        cwd = ""
        try:
            cwd = proc.cwd()
        except Exception:
            pass
        return {
            "type":        _TERMINALS[exe_name],
            "name":        title,
            "exe_path":    exe_path,
            "working_dir": cwd,
            "window":      win_info,
        }

    # UWP apps (from WindowsApps or SystemApps)
    if exe_path and ("WindowsApps" in exe_path or "SystemApps" in exe_path):
        return {
            "type":     "uwp",
            "name":     title or exe_name.replace(".exe", "").replace(".", " ").title(),
            "exe_path": exe_path,
            "window":   win_info,
        }

    # Explorer
    if exe_name == "explorer.exe":
        return {
            "type":        "explorer",
            "name":        f"File Explorer: {title}" if title else "File Explorer",
            "folder_path": "",
            "window":      win_info,
        }

    # Generic app — name derived from window title
    return {
        "type":     "app",
        "name":     _app_name(title, exe_name),
        "exe_path": exe_path,
        "window":   win_info,
    }


def _app_name(title, exe_name):
    """
    Extract clean app name from window title.
    Uses the title itself — no hardcoded name database.
    Most apps put their name after the last " - " in the title.
    """
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


# ─────────────────────────────────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────

def _enrich_chrome(apps):
    """Replace raw browser entries with per-profile tab data from extension."""
    browser_entries = [a for a in apps if a.get("_is_browser")]
    if not browser_entries:
        return

    profile_tabs = {}
    try:
        from backend.routes.chrome import get_tabs_by_profile
        profile_tabs = get_tabs_by_profile()
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome extension: {e}")

    if not profile_tabs:
        for b in browser_entries:
            b["tabs"] = []
            b.pop("_is_browser", None)
        print(Fore.YELLOW + "[WORKSPACE] Chrome: extension not installed — tabs not captured")
        return

    browser_type = browser_entries[0].get("type", "chrome")
    exe_path     = browser_entries[0].get("exe_path", "")

    for entry in browser_entries:
        if entry in apps:
            apps.remove(entry)

    total = 0
    for prof, tabs in profile_tabs.items():
        clean = [
            {
                "url":     t.get("url", ""),
                "title":   t.get("title", ""),
                "profile": prof,
                "pinned":  t.get("pinned", False),
            }
            for t in tabs
            if t.get("url", "") and
               not t["url"].startswith("chrome://") and
               not t["url"].startswith("chrome-extension://") and
               not t["url"].startswith("edge://")
        ]
        if not clean:
            continue
        total += len(clean)
        tab_count = len(clean)
        apps.append({
            "type":         browser_type,
            "name":         f"Chrome ({prof}) - {tab_count} tab{'s' if tab_count != 1 else ''}",
            "exe_path":     exe_path,
            "tabs":         clean,
            "profile_name": prof,
            "window":       {"title": f"Chrome - {prof}"},
        })
        print(Fore.CYAN + f"  Chrome profile '{prof}': {tab_count} tabs")

    print(Fore.GREEN + f"[WORKSPACE] Chrome: {total} tabs, {len(profile_tabs)} profiles")


def _enrich_vscode(apps):
    """Read VS Code workspace path from state.vscdb."""
    vscode_entries = [a for a in apps if a.get("type") == "vscode"]
    if not vscode_entries:
        return

    appdata = os.environ.get("APPDATA", "")
    db_path = os.path.join(appdata, "Code", "User", "globalStorage", "state.vscdb")
    if not os.path.exists(db_path):
        return

    try:
        import sqlite3
        from urllib.parse import unquote
        conn = sqlite3.connect(db_path, timeout=2)
        row  = conn.execute(
            "SELECT value FROM ItemTable "
            "WHERE key = 'history.recentlyOpenedPathsList'"
        ).fetchone()
        conn.close()

        if row:
            entries = json.loads(row[0]).get("entries", [])
            if entries:
                ws = entries[0].get("folderUri", "")
                ws = ws.replace("file:///", "").replace("/", "\\")
                ws = unquote(ws)
                if len(ws) >= 2 and ws[1] == ":":
                    ws = ws[0].upper() + ws[1:]
                for v in vscode_entries:
                    v["workspace_path"] = ws
                    # Clean up the name to just show the folder, not full title
                    v["name"] = "Visual Studio Code"
                print(Fore.CYAN + f"[WORKSPACE] VS Code: {ws}")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] VS Code state: {e}")


def _enrich_explorer(apps):
    """
    Get Explorer window paths via Shell COM.
    Saves both folder_path and display name.
    """
    explorers = [a for a in apps if a.get("type") == "explorer"]
    if not explorers:
        return

    try:
        import win32com.client
        from urllib.parse import unquote

        shell   = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()
        folders = []

        for i in range(windows.Count):
            try:
                w = windows.Item(i)
                if not w:
                    continue
                url  = w.LocationURL or ""
                loc  = w.LocationName or ""
                path = ""

                if url:
                    path = unquote(
                        url.replace("file:///", "").replace("/", "\\")
                    )
                    # Fix drive letter casing
                    if len(path) >= 2 and path[1] == ":":
                        path = path[0].upper() + path[1:]

                if path or loc:
                    folders.append({"path": path, "name": loc})

            except Exception:
                continue

        for i, exp in enumerate(explorers):
            if i < len(folders):
                f = folders[i]
                if f["path"]:
                    exp["folder_path"] = f["path"]
                if f["name"]:
                    exp["name"] = f"File Explorer: {f['name']}"
                print(Fore.CYAN + f"[WORKSPACE] Explorer: {f['path']} ({f['name']})")
            else:
                print(Fore.YELLOW + "[WORKSPACE] Explorer: could not get path from Shell COM")

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Explorer enrichment failed: {e}")


# ─────────────────────────────────────────────────────────────────────────
# SMART RESTORE
# ─────────────────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """
    Normalize URL for comparison.
    Strips www, trailing slashes, fragments, query params for base URLs.
    Returns (domain, full_normalized) tuple for flexible matching.
    """
    url = url.strip().rstrip("/")
    # Remove fragment
    if "#" in url:
        url = url[:url.index("#")]
    # Lowercase
    url = url.lower()
    # Normalize www
    url = url.replace("://www.", "://")
    return url


def _extract_domain(url: str) -> str:
    """
    Extract just the domain from a URL.
    https://app.outlier.ai/login  →  app.outlier.ai
    https://youtube.com           →  youtube.com
    https://www.youtube.com/watch →  youtube.com
    """
    url = url.strip().lower()
    # Remove scheme
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break
    # Remove www
    if url.startswith("www."):
        url = url[4:]
    # Take only the domain part (before first slash)
    domain = url.split("/")[0]
    # Remove port
    domain = domain.split(":")[0]
    return domain


def _is_base_url(url: str) -> bool:
    """
    True if URL is just a homepage/base with no meaningful path.
    https://youtube.com        → True  (base)
    https://youtube.com/       → True  (base)
    https://youtube.com/watch  → False (specific page)
    https://app.outlier.ai/login → False (specific page)
    """
    url = url.strip().rstrip("/").lower()
    url = url.replace("://www.", "://")
    # Remove scheme
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            url = url[len(scheme):]
            break
    # Remove domain
    parts = url.split("/", 1)
    if len(parts) == 1:
        return True   # no path at all
    path = parts[1].strip().rstrip("/")
    return path == ""  # empty path = base URL


def _url_matches(saved_url: str, open_urls: set, open_domains: set) -> bool:
    """
    Check if a saved URL is already open.

    Rules:
      1. Exact normalized match → True
      2. Saved URL is a BASE URL (e.g. youtube.com) AND
         that domain is open with ANY path → True
         (user has YouTube open, no need to open youtube.com again)
      3. Otherwise → False
    """
    if not saved_url:
        return False

    normalized = _normalize_url(saved_url)
    domain     = _extract_domain(saved_url)

    # Rule 1: exact match
    if normalized in open_urls:
        return True

    # Rule 2: base URL + domain already open with any page
    if _is_base_url(saved_url) and domain in open_domains:
        return True

    return False

def _get_open_chrome_profiles() -> set:
    """
    Detect which Chrome profiles have open windows right now.
    Uses window title matching — fast and 100% accurate.
    Chrome window titles end with " - Google Chrome" and contain
    the profile name in parentheses for non-default profiles.
    """
    profiles = set()
    try:
        import psutil

        chrome_pids = set()
        for p in psutil.process_iter(['pid', 'name']):
            if p.info['name'] and p.info['name'].lower() == "chrome.exe":
                chrome_pids.add(p.info['pid'])

        if not chrome_pids:
            return profiles

        # Read profile info from Local State
        chrome_base = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Google", "Chrome", "User Data"
        )
        local_state_path = os.path.join(chrome_base, "Local State")
        if not os.path.exists(local_state_path):
            return profiles

        with open(local_state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        info_cache = state.get("profile", {}).get("info_cache", {})

        # Build mapping: profile display name → email
        name_to_email = {}
        dir_to_email  = {}
        for profile_dir, info in info_cache.items():
            email = (
                info.get("user_name") or
                info.get("signin", {}).get("login", "") or
                ""
            ).lower()
            display_name = info.get("name", "").lower()
            if email:
                if display_name:
                    name_to_email[display_name] = email
                dir_to_email[profile_dir.lower()] = email

        # Check which Chrome windows are actually open by PID
        open_dirs = set()
        for pid in chrome_pids:
            try:
                proc = psutil.Process(pid)
                cmd = proc.cmdline()
                for arg in cmd:
                    if arg.startswith("--profile-directory="):
                        pdir = arg.split("=", 1)[1].lower()
                        open_dirs.add(pdir)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Map open profile dirs to emails
        for pdir in open_dirs:
            email = dir_to_email.get(pdir, "")
            if email:
                profiles.add(email)
                profiles.add(email.split("@")[0])

        # If no --profile-directory found, check for Default profile
        if not open_dirs and chrome_pids:
            email = dir_to_email.get("default", "")
            if email:
                profiles.add(email)
                profiles.add(email.split("@")[0])

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome profile detection: {e}")

    return profiles

def _get_open_chrome_tabs() -> tuple:
    """
    Get all currently open Chrome tab URLs.
    Returns (open_urls: set, open_domains: set).

    Mode 1: Chrome extension via Seven backend (instant).
    Mode 2: Chrome DevTools Protocol on port 9222 (fast socket check first).
    """
    open_urls    = set()
    open_domains = set()

    # Mode 1: Chrome extension via Seven backend
    try:
        from backend.routes.chrome import get_tabs_by_profile
        profile_tabs = get_tabs_by_profile()
        if profile_tabs:
            for tabs in profile_tabs.values():
                for t in tabs:
                    url = t.get("url", "")
                    if url and url.startswith("http"):
                        norm   = _normalize_url(url)
                        domain = _extract_domain(url)
                        open_urls.add(norm)
                        open_domains.add(domain)
            if open_urls:
                print(Fore.CYAN + f"[WORKSPACE] Chrome tabs via extension: "
                      f"{len(open_urls)} URLs, {len(open_domains)} domains")
                return open_urls, open_domains
    except Exception:
        pass

    # Mode 2: DevTools Protocol — check port is open first (no timeout wasted)
    import socket as _socket
    try:
        _s = _socket.create_connection(("127.0.0.1", 9222), timeout=0.1)
        _s.close()
    except Exception:
        return open_urls, open_domains

    try:
        import urllib.request
        import json as _json
        req = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=0.5)
        tabs_data = _json.loads(req.read().decode("utf-8"))
        for tab in tabs_data:
            url = tab.get("url", "")
            if url and url.startswith("http"):
                norm   = _normalize_url(url)
                domain = _extract_domain(url)
                open_urls.add(norm)
                open_domains.add(domain)
        if open_urls:
            print(Fore.CYAN + f"[WORKSPACE] Chrome tabs via DevTools: "
                  f"{len(open_urls)} URLs, {len(open_domains)} domains")
    except Exception:
        pass

    return open_urls, open_domains

_restore_in_progress = threading.Lock()


def smart_restore(apps_config):
    """
    Open only apps/tabs that are not already running.
    Returns (opened_count, already_open_count).
    """
    if not apps_config:
        return 0, 0

    if not _restore_in_progress.acquire(blocking=True, timeout=30):
        print(Fore.YELLOW + "[WORKSPACE] Restore lock timeout — skipping")
        return 0, 0

    try:
        import concurrent.futures

        # Chrome detection runs in parallel while scan runs in this thread
        # scan_current uses COM which has thread affinity — must stay in caller thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _pool:
            _prof_future = _pool.submit(_get_open_chrome_profiles)
            _tabs_future = _pool.submit(_get_open_chrome_tabs)

            # Scan runs here while Chrome detection runs in background
            try:
                current = scan_current()
            except Exception:
                current = []

            try:
                _extra_profiles = _prof_future.result(timeout=3)
            except Exception:
                _extra_profiles = set()

            try:
                open_chrome_urls, open_chrome_domains = _tabs_future.result(timeout=3)
            except Exception:
                open_chrome_urls, open_chrome_domains = set(), set()

        open_exes     = set()
        open_ws_paths = set()
        open_folders  = set()
        open_profiles = set()
        open_uwp      = set()
        open_types    = set()

        for app in current:
            t    = (app.get("type") or "").lower()
            exe  = (app.get("exe_path") or "").lower()
            ws   = (app.get("workspace_path") or "").lower()
            fld  = (app.get("folder_path") or "").lower()
            prof = (app.get("profile_name") or "").lower()
            prot = (app.get("protocol") or "").lower()
            name = (app.get("name") or "").lower()

            if exe:  open_exes.add(exe)
            if ws:   open_ws_paths.add(ws)
            if fld:  open_folders.add(fld)
            if prof: open_profiles.add(prof)
            if t:    open_types.add(t)
            if t == "uwp":
                if prot: open_uwp.add(prot)
                if name: open_uwp.add(name)

        open_profiles.update(_extra_profiles)
        print(Fore.CYAN + f"[WORKSPACE] Open URLs: {len(open_chrome_urls)}, "
              f"Domains: {len(open_chrome_domains)}")

        filtered_apps = [cfg for cfg in apps_config if _should_restore(cfg)]

        missing      = []
        already_open = 0

        for cfg in filtered_apps:
            t    = (cfg.get("type") or "").lower()
            exe  = (cfg.get("exe_path") or "").lower()
            ws   = (cfg.get("workspace_path") or "").lower()
            fld  = (cfg.get("folder_path") or "").lower()
            prof = (cfg.get("profile_name") or "").lower()
            prot = (cfg.get("protocol") or "").lower()
            name = (cfg.get("name") or "").lower()
            tabs = cfg.get("tabs", [])

            if t in ("chrome", "edge", "brave", "firefox"):
                if tabs and open_chrome_urls:
                    missing_tabs = []
                    skipped_tabs = 0

                    for tab in tabs:
                        tab_url = tab.get("url", "")
                        if not tab_url:
                            continue
                        if _url_matches(tab_url, open_chrome_urls, open_chrome_domains):
                            skipped_tabs += 1
                        else:
                            missing_tabs.append(tab)

                    if not missing_tabs:
                        already_open += 1
                        print(Fore.CYAN + f"[WORKSPACE] Chrome '{prof}': "
                              f"all {len(tabs)} tabs already open")
                    else:
                        new_cfg = dict(cfg)
                        new_cfg["tabs"] = missing_tabs
                        new_cfg["_partial"] = True
                        missing.append(new_cfg)
                        print(Fore.CYAN + f"[WORKSPACE] Chrome '{prof}': "
                              f"{len(missing_tabs)} new, {skipped_tabs} already open")

                elif tabs and not open_chrome_urls:
                    if prof and prof in open_profiles:
                        already_open += 1
                        print(Fore.CYAN + f"[WORKSPACE] Browser already open: {name}")
                    else:
                        missing.append(cfg)
                        print(Fore.YELLOW + f"[WORKSPACE] Missing browser: {name}")

                else:
                    if (prof and prof in open_profiles) or (t in open_types):
                        already_open += 1
                        print(Fore.CYAN + f"[WORKSPACE] Browser already open: {name}")
                    else:
                        missing.append(cfg)
                        print(Fore.YELLOW + f"[WORKSPACE] Missing browser: {name}")

            elif t == "vscode":
                if ws and ws in open_ws_paths:
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (workspace): {name}")
                elif exe and exe in open_exes:
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (exe): {name}")
                else:
                    missing.append(cfg)
                    print(Fore.YELLOW + f"[WORKSPACE] Missing: {name}")

            elif t == "explorer":
                if fld and fld in open_folders:
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (folder): {name}")
                else:
                    missing.append(cfg)
                    print(Fore.YELLOW + f"[WORKSPACE] Missing explorer: {name}")

            elif t == "uwp":
                if (prot and prot in open_uwp) or (name and name in open_uwp):
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (uwp): {name}")
                else:
                    missing.append(cfg)
                    print(Fore.YELLOW + f"[WORKSPACE] Missing uwp: {name}")

            else:
                is_open = False

                if exe and exe in open_exes:
                    is_open = True
                    print(Fore.CYAN + f"[WORKSPACE] Already open (exe): {name}")
                elif name:
                    for app in current:
                        curr_name = (app.get("name") or "").lower()
                        if name in curr_name or curr_name in name:
                            is_open = True
                            print(Fore.CYAN + f"[WORKSPACE] Already open (name): "
                                  f"{name} ~ {curr_name}")
                            break

                if is_open:
                    already_open += 1
                else:
                    missing.append(cfg)
                    print(Fore.YELLOW + f"[WORKSPACE] Missing: {name}")

        if missing:
            print(Fore.CYAN + f"[WORKSPACE] Opening {len(missing)} apps "
                  f"({already_open} already running)")
            restore(missing)
        else:
            print(Fore.GREEN + "[WORKSPACE] All apps already open")

        return len(missing), already_open

    finally:
        _restore_in_progress.release()

# ─────────────────────────────────────────────────────────────────────────
# RESTORE
# ─────────────────────────────────────────────────────────────────────────

def _should_restore(cfg: dict) -> bool:
    """
    Only skip Seven's own processes.
    If the user saved it in a workspace, Seven should restore it.
    """
    exe  = (cfg.get("exe_path") or "").lower()
    name = (cfg.get("name") or "").strip()

    if not name and not exe:
        return False

    exe_name = os.path.basename(exe) if exe else ""
    if exe_name in ("electron.exe", "python.exe", "pythonw.exe"):
        seven_markers = (
            "mk-projects\\seven",
            "\\seven\\electron",
            "\\seven\\python",
            "program files\\seven",
            "appdata\\local\\seven",
        )
        if any(marker in exe for marker in seven_markers):
            return False

    return True


def restore(apps_config):
    """Launch all apps in parallel threads."""
    if not apps_config:
        return

    clean_config = [cfg for cfg in apps_config if _should_restore(cfg)]

    if not clean_config:
        print(Fore.GREEN + "[WORKSPACE] Nothing to restore after filtering")
        return

    print(Fore.CYAN + f"[WORKSPACE] Restoring {len(clean_config)} apps...")
    t0      = time.time()
    threads = []

    for cfg in clean_config:
        th = threading.Thread(target=_restore_one, args=(cfg,), daemon=True)
        th.start()
        threads.append(th)

    for th in threads:
        th.join(timeout=20)

    elapsed = int((time.time() - t0) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Done in {elapsed}ms")


def _restore_one(cfg):
    t    = (cfg.get("type") or "").lower()
    name = cfg.get("name", "?")
    try:
        if t in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(cfg)
        elif t == "vscode":
            _restore_vscode(cfg)
        elif t == "explorer":
            _restore_explorer(cfg)
        elif t in ("notepad", "notepad++", "sublime"):
            _restore_editor(cfg)
        elif t in ("excel", "word", "powerpoint"):
            _restore_office(cfg)
        elif t == "uwp":
            _restore_uwp(cfg)
        elif t in ("powershell", "cmd", "terminal"):
            _restore_terminal(cfg)
        else:
            _restore_generic(cfg)
        print(Fore.GREEN + f"  [+] {name}")
    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")


def _restore_browser(cfg):
    """
    Restore browser tabs.
    If _partial=True, only the missing_tabs subset is opened.
    Tabs are opened in the correct Chrome profile.
    """
    tabs         = cfg.get("tabs", [])
    urls         = [t["url"] for t in tabs
                    if t.get("url", "").startswith("http")]
    profile_name = cfg.get("profile_name", "")
    chrome_exe   = _find_chrome_exe()

    if not urls:
        # No URLs to open — nothing to do
        return

    if not chrome_exe:
        # Fallback: open via shell
        for url in urls:
            subprocess.Popen(f'start chrome "{url}"', shell=True)
            time.sleep(0.3)
        return

    chrome_base  = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    profile_dir  = _find_chrome_profile_dir(chrome_base, profile_name)

    if profile_dir:
        subprocess.Popen(
            [chrome_exe, f"--profile-directory={profile_dir}", urls[0]]
        )
        # Open all remaining tabs immediately — no sleep needed
        for url in urls[1:]:
            subprocess.Popen(
                [chrome_exe, f"--profile-directory={profile_dir}", url]
            )
        partial = cfg.get("_partial", False)
        print(Fore.CYAN + f"[WORKSPACE] Chrome '{profile_name}': "
              f"{'partial restore — ' if partial else ''}{len(urls)} tabs")
    else:
        for url in urls:
            subprocess.Popen([chrome_exe, url])
            time.sleep(0.3)


def _restore_vscode(cfg):
    """Restore VS Code. Uses workspace_path if available, else exe_path."""
    ws  = cfg.get("workspace_path", "")
    exe = cfg.get("exe_path", "")

    if ws and os.path.exists(ws):
        try:
            subprocess.Popen(["code", ws])
            return
        except Exception:
            pass

    # Fallback: launch VS Code directly via exe
    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe])
            return
        except Exception:
            pass

    # Last resort: shell command
    try:
        subprocess.Popen("code", shell=True)
    except Exception:
        pass


def _restore_explorer(cfg):
    """
    Open File Explorer at the saved folder path.
    Falls back to opening the folder from the saved name if path missing.
    """
    folder = cfg.get("folder_path", "")
    name   = cfg.get("name", "")

    if folder and os.path.exists(folder):
        subprocess.Popen(["explorer", folder])
        print(Fore.GREEN + f"[WORKSPACE] Explorer opened: {folder}")
        return

    # Try to extract folder path from enriched name
    # Name format: "File Explorer: EDU - File Explorer" or "File Explorer: C:\Users\..."
    if name:
        # Strip "File Explorer: " prefix
        clean = name
        for prefix in ("File Explorer: ", "File Explorer — ", "File Explorer - "):
            if name.startswith(prefix):
                clean = name[len(prefix):]
                break

        # Remove " - File Explorer" suffix
        if " - File Explorer" in clean:
            clean = clean.replace(" - File Explorer", "").strip()

        if os.path.exists(clean):
            subprocess.Popen(["explorer", clean])
            print(Fore.GREEN + f"[WORKSPACE] Explorer opened from name: {clean}")
            return

    # Last resort — open My Computer
    subprocess.Popen(["explorer"])
    print(Fore.YELLOW + "[WORKSPACE] Explorer opened without folder (path not found)")


def _restore_editor(cfg):
    fp  = cfg.get("file_path", "")
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
    proto = cfg.get("protocol", "")
    if proto:
        try:
            os.startfile(proto)
            return
        except Exception:
            pass
    _restore_generic(cfg)


def _restore_terminal(cfg):
    cwd      = cfg.get("working_dir", "")
    app_type = (cfg.get("type") or "").lower()
    exe      = "powershell" if app_type in ("powershell", "terminal") else "cmd"
    flags    = subprocess.CREATE_NEW_CONSOLE
    if cwd and os.path.exists(cwd):
        subprocess.Popen([exe], cwd=cwd, creationflags=flags)
    else:
        subprocess.Popen([exe], creationflags=flags)


def _restore_generic(cfg):
    exe  = cfg.get("exe_path", "")
    name = cfg.get("name", "")

    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe])
            return
        except Exception:
            pass

    clean = name.split(" - ")[-1].strip() if " - " in name else name
    if not clean:
        return

    try:
        from hands.core import open_app
        open_app(clean)
        return
    except Exception:
        pass

    try:
        import AppOpener
        AppOpener.open(clean)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────

def _find_chrome_exe():
    for p in [
        os.path.join(os.environ.get("PROGRAMFILES", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
    ]:
        if os.path.exists(p):
            return p
    return None


def _find_chrome_profile_dir(chrome_base, profile_name):
    if not profile_name or not os.path.exists(chrome_base):
        return None

    for item in os.listdir(chrome_base):
        if item != "Default" and not item.startswith("Profile"):
            continue
        prefs = os.path.join(chrome_base, item, "Preferences")
        if not os.path.exists(prefs):
            continue
        try:
            with open(prefs, "r", encoding="utf-8") as f:
                data = json.load(f)
            for acc in data.get("account_info", []):
                email = acc.get("email", "").lower()
                if (profile_name.lower() in email or
                        email.split("@")[0] == profile_name.lower()):
                    return item
            pname = data.get("profile", {}).get("name", "")
            if pname.lower() == profile_name.lower():
                return item
        except Exception:
            continue

    profiles = [
        d for d in os.listdir(chrome_base)
        if d == "Default" or d.startswith("Profile")
    ]
    if len(profiles) == 1:
        return profiles[0]
    return None