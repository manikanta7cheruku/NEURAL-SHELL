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
    """Get Explorer window paths via Shell COM."""
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
                if w and w.LocationURL:
                    path_str = unquote(
                        w.LocationURL.replace("file:///", "").replace("/", "\\")
                    )
                    folders.append({"path": path_str, "name": w.LocationName or ""})
            except Exception:
                continue
        for i, exp in enumerate(explorers):
            if i < len(folders):
                exp["folder_path"] = folders[i]["path"]
                if folders[i]["name"]:
                    exp["name"] = folders[i]["name"]
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Explorer: {e}")


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


def _get_open_chrome_tabs() -> tuple:
    """
    Get all currently open Chrome tab URLs.

    Returns (open_urls: set, open_domains: set)

    Works in TWO modes:
      1. Seven running  → via Chrome extension API (backend route)
      2. Seven closed   → direct Chrome DevTools Protocol on port 9222

    Both return normalized URLs + domains for matching.
    """
    open_urls    = set()
    open_domains = set()

    # ── Mode 1: Chrome extension via Seven backend ──
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

    # ── Mode 2: Direct Chrome DevTools Protocol (works when Seven closed) ──
    try:
        import urllib.request
        import json as _json

        req = urllib.request.urlopen(
            "http://127.0.0.1:9222/json",
            timeout=2
        )
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

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome tab detection failed: {e}")
        print(Fore.YELLOW + "[WORKSPACE] Launch Chrome with "
              "--remote-debugging-port=9222 for tab detection")

    return open_urls, open_domains


def smart_restore(apps_config):
    """
    Open only apps/tabs that are not already running.
    URL matching is smart:
      - Exact URL match → skip
      - Base domain saved (youtube.com) + any YouTube tab open → skip
      - Different page on same domain → open it
    """
    if not apps_config:
        return 0, 0

    try:
        current = scan_current()
    except Exception:
        current = []

    # Build lookup sets
    open_exes      = set()
    open_ws_paths  = set()
    open_folders   = set()
    open_profiles  = set()
    open_uwp       = set()
    open_types     = set()

    for app in current:
        t    = (app.get("type")           or "").lower()
        exe  = (app.get("exe_path")       or "").lower()
        ws   = (app.get("workspace_path") or "").lower()
        fld  = (app.get("folder_path")    or "").lower()
        prof = (app.get("profile_name")   or "").lower()
        prot = (app.get("protocol")       or "").lower()
        name = (app.get("name")           or "").lower()

        if exe:  open_exes.add(exe)
        if ws:   open_ws_paths.add(ws)
        if fld:  open_folders.add(fld)
        if prof: open_profiles.add(prof)
        if t:    open_types.add(t)
        if t == "uwp":
            if prot: open_uwp.add(prot)
            if name: open_uwp.add(name)

    # Get open Chrome tabs — works with or without Seven running
    open_chrome_urls, open_chrome_domains = _get_open_chrome_tabs()
    print(Fore.CYAN + f"[WORKSPACE] Open URLs: {len(open_chrome_urls)}, "
          f"Domains: {len(open_chrome_domains)}")

    missing      = []
    already_open = 0

    apps_config = [cfg for cfg in apps_config if _should_restore(cfg)]

    for cfg in apps_config:
        t    = (cfg.get("type")           or "").lower()
        exe  = (cfg.get("exe_path")       or "").lower()
        ws   = (cfg.get("workspace_path") or "").lower()
        fld  = (cfg.get("folder_path")    or "").lower()
        prof = (cfg.get("profile_name")   or "").lower()
        prot = (cfg.get("protocol")       or "").lower()
        name = (cfg.get("name")           or "").lower()
        tabs = cfg.get("tabs", [])

        is_open = False

        if t in ("chrome", "edge", "brave", "firefox"):
            if tabs and open_chrome_urls:
                # Filter tabs — skip already open ones using smart URL matching
                missing_tabs = []
                skipped_tabs = 0
                for tab in tabs:
                    tab_url = tab.get("url", "")
                    if not tab_url:
                        continue
                    if _url_matches(tab_url, open_chrome_urls, open_chrome_domains):
                        skipped_tabs += 1
                        print(Fore.CYAN + f"[WORKSPACE] Tab already open: {tab_url[:60]}")
                    else:
                        missing_tabs.append(tab)

                if not missing_tabs:
                    is_open = True
                    print(Fore.CYAN + f"[WORKSPACE] Chrome '{prof}': "
                          f"all {len(tabs)} tabs already open")
                else:
                    new_cfg = dict(cfg)
                    new_cfg["tabs"] = missing_tabs
                    new_cfg["_partial"] = True
                    print(Fore.CYAN + f"[WORKSPACE] Chrome '{prof}': "
                          f"{len(missing_tabs)} new, {skipped_tabs} already open")
                    missing.append(new_cfg)
                    continue

            elif not tabs:
                # No tabs saved — check if profile/Chrome is open
                if prof and prof in open_profiles:
                    is_open = True
                elif "chrome" in open_types or "edge" in open_types:
                    is_open = True

        elif t == "vscode":
            if ws and ws in open_ws_paths:
                is_open = True

        elif t == "explorer":
            if fld and fld in open_folders:
                is_open = True

        elif t == "uwp":
            if prot and prot in open_uwp:
                is_open = True
            elif name and name in open_uwp:
                is_open = True

        elif t in ("powershell", "cmd", "terminal"):
            if t in open_types:
                is_open = True

        else:
            if exe and exe in open_exes:
                is_open = True
            elif name:
                for app in current:
                    curr_name = (app.get("name") or "").lower()
                    if name in curr_name or curr_name in name:
                        is_open = True
                        break

        if is_open:
            already_open += 1
        else:
            missing.append(cfg)

    if missing:
        print(Fore.CYAN + f"[WORKSPACE] Opening {len(missing)} apps "
              f"({already_open} already running)")
        restore(missing)
    else:
        print(Fore.GREEN + "[WORKSPACE] All apps already open — nothing to do")

    return len(missing), already_open


# ─────────────────────────────────────────────────────────────────────────
# RESTORE
# ─────────────────────────────────────────────────────────────────────────

def _should_restore(cfg: dict) -> bool:
    """
    Return True if this app should be restored.
    Only skips Seven's own processes. Everything else restores.
    If user had it open when they saved, they want it back.
    """
    exe  = (cfg.get("exe_path") or "").lower()
    name = (cfg.get("name") or "").lower().strip()

    if not name and not exe:
        return False

    exe_name = os.path.basename(exe) if exe else ""
    if exe_name in ("electron.exe", "pythonw.exe", "python.exe"):
        _seven_markers = (
            "mk-projects\\seven", "\\seven\\electron",
            "\\seven\\python", "program files\\seven",
            "appdata\\local\\seven",
        )
        if any(marker in exe for marker in _seven_markers):
            return False

    return True


def restore(apps_config):
    """Launch all apps in parallel threads. Filters system apps first."""
    if not apps_config:
        return

    # Filter out system/internal apps before restoring
    clean_config = [cfg for cfg in apps_config if _should_restore(cfg)]

    skipped = len(apps_config) - len(clean_config)
    if skipped > 0:
        print(Fore.YELLOW + f"[WORKSPACE] Filtered {skipped} system apps from restore")

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

    print(Fore.CYAN + f"[WORKSPACE] Restoring {len(apps_config)} apps...")
    t0      = time.time()
    threads = []

    for cfg in apps_config:
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
        # Open first URL (creates/focuses window)
        subprocess.Popen(
            [chrome_exe, f"--profile-directory={profile_dir}", urls[0]]
        )
        time.sleep(1.5)
        # Open remaining URLs as new tabs
        for url in urls[1:]:
            subprocess.Popen(
                [chrome_exe, f"--profile-directory={profile_dir}", url]
            )
            time.sleep(0.4)
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
    folder = cfg.get("folder_path", "")
    if folder and os.path.exists(folder):
        subprocess.Popen(["explorer", folder])
    else:
        subprocess.Popen(["explorer"])


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