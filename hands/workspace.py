"""
hands/workspace.py
Workspace scanner and restorer.

Captures all visible user apps, Chrome tabs (via extension),
VS Code workspace, Explorer folders, terminals.

Restore is smart — only opens what is genuinely missing.
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
# SKIP LISTS
# ─────────────────────────────────────────────────────────────────────────

_SKIP_EXE = {
    "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "widgetservice.exe", "applicationframehost.exe",
    "runtimebroker.exe", "lockapp.exe", "dllhost.exe",
    "ctfmon.exe", "sihost.exe", "taskhostw.exe",
    "backgroundtaskhost.exe", "shellhost.exe", "smartscreen.exe",
    "phoneexperiencehost.exe", "clicktodo.exe",
    "nvidia overlay.exe", "msedgewebview2.exe", "electron.exe",
}

_SKIP_TITLE = {
    "", "program manager", "windows input experience",
    "microsoft text input application",
    "nvidia geforce overlay", "nvidia geforce overlay dt",
    "click to do",
}

_SKIP_PATH_FRAGMENTS = [
    "mk-projects\\seven",
    "nvidia corporation\\nvidia app",
    "microsoftwindows.client.coreai",
]

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
    "powershell.exe":    "powershell",
    "pwsh.exe":          "powershell",
    "cmd.exe":           "cmd",
    "windowsterminal.exe": "terminal",
    "wt.exe":            "terminal",
}

_UWP_PROTOCOLS = {
    "whatsapp.root.exe":  "whatsapp:",
    "systemsettings.exe": "ms-settings:",
    "calculatorapp.exe":  "calculator:",
    "calculator.exe":     "calculator:",
    "photos.exe":         "ms-photos:",
    "mspaint.exe":        "mspaint:",
}


# ─────────────────────────────────────────────────────────────────────────
# SCAN
# ─────────────────────────────────────────────────────────────────────────

def scan_current():
    """Scan all visible user windows and return app configs."""
    print(Fore.CYAN + "[WORKSPACE] Scanning desktop...")
    t0 = time.time()

    apps        = []
    seen_titles = set()

    def _cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            if not title or title.lower().strip() in _SKIP_TITLE:
                return
            if title in seen_titles:
                return

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc     = psutil.Process(pid)
                exe_name = proc.name().lower()
                exe_path = proc.exe()
            except Exception:
                return

            if exe_name in _SKIP_EXE:
                return

            exe_lower = exe_path.lower()
            if any(f in exe_lower for f in _SKIP_PATH_FRAGMENTS):
                return

            seen_titles.add(title)

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

    # Terminals
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

    # Known UWP by exe name
    if exe_name in _UWP_PROTOCOLS:
        return {
            "type":     "uwp",
            "name":     title or exe_name.replace(".exe", "").title(),
            "protocol": _UWP_PROTOCOLS[exe_name],
            "window":   win_info,
        }

    # UWP by path
    if exe_path and ("WindowsApps" in exe_path or "SystemApps" in exe_path):
        for known, proto in _UWP_PROTOCOLS.items():
            if known.split(".")[0] in exe_name:
                return {
                    "type":     "uwp",
                    "name":     title,
                    "protocol": proto,
                    "window":   win_info,
                }
        if any(s in exe_name for s in ["background", "host", "broker", "service"]):
            return None
        return {
            "type":     "uwp",
            "name":     title,
            "exe_path": exe_path,
            "protocol": "",
            "window":   win_info,
        }

    # Explorer
    if exe_name == "explorer.exe":
        return {
            "type":        "explorer",
            "name":        title,
            "folder_path": "",
            "window":      win_info,
        }

    # Skip overlays
    if "overlay" in exe_name or "overlay" in title.lower():
        return None

    # Generic
    return {
        "type":     "app",
        "name":     _app_name(title, exe_name),
        "exe_path": exe_path,
        "window":   win_info,
    }


def _app_name(title, exe_name):
    if " - " in title:
        return title.split(" - ")[-1].strip()
    return exe_name.replace(".exe", "").title()


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
        # No extension — keep browser window with title only, no tabs
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
               not t["url"].startswith("chrome-extension://")
        ]
        if not clean:
            continue
        total += len(clean)
        apps.append({
            "type":         browser_type,
            "name":         f"Chrome ({prof})",
            "exe_path":     exe_path,
            "tabs":         clean,
            "profile_name": prof,
            "window":       {"title": f"Chrome - {prof}"},
        })
        print(Fore.CYAN + f"  Chrome profile '{prof}': {len(clean)} tabs")

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
                from urllib.parse import unquote
                ws = unquote(ws)
                if len(ws) >= 2 and ws[1] == ":":
                    ws = ws[0].upper() + ws[1:]
                for v in vscode_entries:
                    v["workspace_path"] = ws
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
                    path = unquote(
                        w.LocationURL.replace("file:///", "").replace("/", "\\")
                    )
                    folders.append({"path": path, "name": w.LocationName or ""})
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

def smart_restore(apps_config):
    """
    Open only apps that are not already running.

    Matching per type:
      chrome/browser → by profile name (from extension)
                        if no extension → always restore (tabs unknown)
      vscode         → by workspace_path
      terminal       → by exe path (same terminal type = skip)
      explorer       → by folder_path
      uwp            → by protocol/name
      everything else→ by exe_path
    """
    if not apps_config:
        return 0, 0

    # What's currently open
    try:
        current = scan_current()
    except Exception:
        current = []

    # Index current state
    open_exes      = set()
    open_ws_paths  = set()
    open_folders   = set()
    open_profiles  = set()
    open_uwp       = set()

    for app in current:
        t    = (app.get("type")          or "").lower()
        exe  = (app.get("exe_path")      or "").lower()
        ws   = (app.get("workspace_path")or "").lower()
        fld  = (app.get("folder_path")   or "").lower()
        prof = (app.get("profile_name")  or "").lower()
        prot = (app.get("protocol")      or "").lower()
        name = (app.get("name")          or "").lower()

        if exe:
            open_exes.add(exe)
        if ws:
            open_ws_paths.add(ws)
        if fld:
            open_folders.add(fld)
        if prof:
            open_profiles.add(prof)
        if t == "uwp":
            if prot:
                open_uwp.add(prot)
            if name:
                open_uwp.add(name)

    missing      = []
    already_open = 0

    for cfg in apps_config:
        t    = (cfg.get("type")          or "").lower()
        exe  = (cfg.get("exe_path")      or "").lower()
        ws   = (cfg.get("workspace_path")or "").lower()
        fld  = (cfg.get("folder_path")   or "").lower()
        prof = (cfg.get("profile_name")  or "").lower()
        prot = (cfg.get("protocol")      or "").lower()
        name = (cfg.get("name")          or "").lower()
        tabs = cfg.get("tabs", [])

        is_open = False

        if t in ("chrome", "edge", "brave", "firefox"):
            # Extension installed → we know profile → match by profile
            # Extension NOT installed → open_profiles is empty → always restore
            if prof and open_profiles and prof in open_profiles:
                is_open = True
            # If no profile saved or no extension data → restore

        elif t == "vscode":
            # Match only if same workspace folder is open
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

        else:
            # terminal, powershell, cmd, office, notepad, generic app
            if exe and exe in open_exes:
                is_open = True

        if is_open:
            already_open += 1
        else:
            missing.append(cfg)

    if missing:
        print(Fore.CYAN + f"[WORKSPACE] Opening {len(missing)} apps "
              f"({already_open} already running)")
        restore(missing)
    else:
        print(Fore.GREEN + "[WORKSPACE] All apps already open")

    return len(missing), already_open


# ─────────────────────────────────────────────────────────────────────────
# RESTORE
# ─────────────────────────────────────────────────────────────────────────

def restore(apps_config):
    """Launch all apps in parallel threads."""
    if not apps_config:
        return

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
    tabs         = cfg.get("tabs", [])
    urls         = [t["url"] for t in tabs
                    if t.get("url", "").startswith("http")]
    profile_name = cfg.get("profile_name", "")
    chrome_exe   = _find_chrome_exe()

    if not urls:
        subprocess.Popen("start chrome", shell=True)
        return

    if not chrome_exe:
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
        time.sleep(2)
        for url in urls[1:]:
            subprocess.Popen(
                [chrome_exe, f"--profile-directory={profile_dir}", url]
            )
            time.sleep(0.5)
        print(f"[WORKSPACE] Chrome '{profile_name}': {len(urls)} tabs")
    else:
        for url in urls:
            subprocess.Popen([chrome_exe, url])
            time.sleep(0.3)


def _restore_vscode(cfg):
    ws = cfg.get("workspace_path", "")
    if ws and os.path.exists(ws):
        subprocess.Popen(["code", ws])
    else:
        subprocess.Popen(["code"])


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