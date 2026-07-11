"""
hands/workspace.py
Workspace scanner and restorer — ENHANCED version.

Improvements over v1:
  - Captures file paths from window titles (Notepad, Excel, PDF viewers)
  - Scans Explorer folder paths via Shell COM
  - VS Code workspace detection via state.vscdb
  - Chrome tab URLs via DevTools Protocol
  - UWP app detection (Settings, Photos, Calculator)
  - Window positions and sizes for restore
  - PowerShell/Terminal working directory detection
  - Parallel restore with progress logging
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


# ── Known app classifications ────────────────────────────────────────────

_BROWSER_PROCESSES = {
    "chrome.exe": "chrome", "msedge.exe": "edge",
    "firefox.exe": "firefox", "brave.exe": "brave",
    "opera.exe": "opera", "vivaldi.exe": "vivaldi",
}

_EDITOR_PROCESSES = {
    "code.exe": "vscode", "code - insiders.exe": "vscode",
    "notepad.exe": "notepad", "notepad++.exe": "notepad++",
    "sublime_text.exe": "sublime", "devenv.exe": "visual_studio",
}

_TERMINAL_PROCESSES = {
    "powershell.exe": "powershell", "pwsh.exe": "powershell",
    "cmd.exe": "cmd", "windowsterminal.exe": "terminal",
    "wt.exe": "terminal",
}

_OFFICE_PROCESSES = {
    "excel.exe": "excel", "winword.exe": "word",
    "powerpnt.exe": "powerpoint", "onenote.exe": "onenote",
}

_UWP_PROTOCOLS = {
    "systemsettings.exe":    "ms-settings:",
    "photos.exe":            "ms-photos:",
    "calculatorapp.exe":     "calculator:",
    "calculator.exe":        "calculator:",
    "mspaint.exe":           "mspaint:",
    "windowsstore.exe":      "ms-windows-store:",
    "whatsapp.exe":          "whatsapp:",
}

# Additional apps launched by protocol or start menu name
_APP_LAUNCH_NAMES = {
    "whatsapp.root": "whatsapp",
    "calculatorapp": "calculator",
    "photos":        "ms-photos:",
}

_SKIP_PROCESSES = {
    "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "widgetservice.exe", "applicationframehost.exe",
    "runtimebroker.exe", "searchui.exe", "lockapp.exe",
    "taskmgr.exe", "rundll32.exe", "dllhost.exe",
    "sihost.exe", "ctfmon.exe", "securityhealthsystray.exe",
    "clicktodo.exe", "phoneexperiencehost.exe",
    "nvidia overlay.exe", "gamebar.exe", "gamebarftserver.exe",
    "gamingservices.exe", "gamingservicesnet.exe",
}

# Skip Seven's own window (Electron)
_SKIP_TITLES_CONTAINS = [
    "nvidia geforce overlay",
    "click to do",
]

_SKIP_TITLES = {"", "program manager", "windows input experience",
                "microsoft text input application", "search",
                "nvidia geforce overlay", "click to do"}


# ── SCAN ─────────────────────────────────────────────────────────────────

def scan_current():
    """Scan all visible windows and return workspace config list."""
    print(Fore.CYAN + "[WORKSPACE] Scanning desktop...")
    start = time.time()

    apps = []
    seen_pids = set()

    def enum_cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title or title.lower() in _SKIP_TITLES:
                return

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

            # Skip system titles
            if title.lower() in _SKIP_TITLES:
                return

            # Skip Seven's own Electron window
            if "electron" in exe_name.lower() and "seven" in (exe_path or "").lower():
                return

            # Explorer special handling: skip "Program Manager" (desktop shell)
            # but KEEP actual File Explorer windows
            if exe_name == "explorer.exe":
                if title.lower() == "program manager":
                    return
                # Don't add to seen_pids — multiple explorer windows share same process
            else:
                seen_pids.add(pid)

            # Window rect
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
    """Classify a window into an app config."""

    # Browser
    if exe_name in _BROWSER_PROCESSES:
        return {
            "type": _BROWSER_PROCESSES[exe_name],
            "name": title.split(" - ")[-1].strip() if " - " in title else exe_name.replace(".exe", "").title(),
            "exe_path": exe_path,
            "tabs": [],
            "window": win_info,
        }

    # Editor
    if exe_name in _EDITOR_PROCESSES:
        file_path = _extract_file_from_title(title)
        return {
            "type": _EDITOR_PROCESSES[exe_name],
            "name": title,
            "exe_path": exe_path,
            "file_path": file_path,
            "workspace_path": "",
            "window": win_info,
        }

    # Terminal
    if exe_name in _TERMINAL_PROCESSES:
        cwd = ""
        try:
            cwd = proc.cwd()
        except Exception:
            pass
        return {
            "type": _TERMINAL_PROCESSES[exe_name],
            "name": title,
            "exe_path": exe_path,
            "working_dir": cwd,
            "window": win_info,
        }

    # Office
    if exe_name in _OFFICE_PROCESSES:
        file_path = _extract_file_from_title(title)
        return {
            "type": _OFFICE_PROCESSES[exe_name],
            "name": title,
            "exe_path": exe_path,
            "file_path": file_path,
            "window": win_info,
        }

    # UWP apps (Store apps, modern Windows apps)
    if exe_name in _UWP_PROTOCOLS:
        return {
            "type": "uwp",
            "name": title or exe_name.replace(".exe", "").title(),
            "protocol": _UWP_PROTOCOLS[exe_name],
            "window": win_info,
        }

    # UWP apps detected by path (SystemApps or WindowsApps)
    if exe_path and ("SystemApps" in exe_path or "WindowsApps" in exe_path):
        # Try to find a protocol or launch name
        app_lower = exe_name.replace(".exe", "").lower()
        protocol = _APP_LAUNCH_NAMES.get(app_lower, "")
        if protocol:
            return {
                "type": "uwp",
                "name": title or app_lower.title(),
                "protocol": protocol,
                "window": win_info,
            }
        # Skip unknown system apps
        return None

    # Explorer windows
    if exe_name == "explorer.exe":
        return {
            "type": "explorer",
            "name": title,
            "folder_path": "",
            "window": win_info,
        }

    # PDF / document viewers
    file_path = _extract_file_from_title(title)
    if file_path:
        return {
            "type": "document",
            "name": title,
            "exe_path": exe_path,
            "file_path": file_path,
            "window": win_info,
        }

    # Skip NVIDIA overlay and other system overlays
    if "overlay" in exe_name.lower() or "overlay" in title.lower():
        return None

    # Generic app
    clean_name = title.split(" - ")[-1].strip() if " - " in title else exe_name.replace(".exe", "").title()
    return {
        "type": "app",
        "name": clean_name,
        "exe_path": exe_path,
        "window": win_info,
    }


def _extract_file_from_title(title):
    """Extract file path from window title."""
    if not title:
        return ""

    # Remove leading asterisk (unsaved file indicator)
    clean_title = title.lstrip("*").strip()

    # Pattern: "filename.ext - AppName" or "C:\path\file.ext - AppName"
    parts = clean_title.split(" - ")
    if len(parts) >= 2:
        candidate = parts[0].strip()

        # Remove leading asterisk again (some apps put it before filename)
        candidate = candidate.lstrip("*").strip()

        # Direct path check
        if os.path.exists(candidate):
            return os.path.abspath(candidate)

        # Check with common drives
        for drive in ["C:\\", "D:\\", "E:\\", "M:\\", "F:\\", "G:\\"]:
            full = os.path.join(drive, candidate)
            if os.path.exists(full):
                return full

        # Check common locations
        home = os.path.expanduser("~")
        for subdir in ["Desktop", "Documents", "Downloads", "OneDrive",
                       "OneDrive - Personal"]:
            full = os.path.join(home, subdir, candidate)
            if os.path.exists(full):
                return full

        # Check APPDATA locations
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            full = os.path.join(appdata, "SEVEN", candidate)
            if os.path.exists(full):
                return full

    # Look for file extensions anywhere in the title
    ext_pattern = r'[A-Za-z]:\\[^\*\?"<>|]+\.(?:pdf|docx?|xlsx?|pptx?|txt|md|csv|py|js|html|json|log)'
    match = re.search(ext_pattern, clean_title, re.IGNORECASE)
    if match:
        candidate = match.group(0).strip()
        if os.path.exists(candidate):
            return candidate

    # Try just the filename part with common extensions
    for ext in ['.txt', '.pdf', '.docx', '.xlsx', '.pptx', '.md', '.py', '.json', '.csv']:
        if ext in clean_title.lower():
            # Extract everything before " - " as potential filename
            fname = parts[0].strip().lstrip("*").strip() if parts else clean_title
            # Search in recent/common dirs
            for search_dir in [
                os.path.expanduser("~\\Desktop"),
                os.path.expanduser("~\\Documents"),
                os.path.expanduser("~\\Downloads"),
                os.getcwd(),
            ]:
                if os.path.exists(search_dir):
                    for f in os.listdir(search_dir):
                        if f.lower() == fname.lower():
                            return os.path.join(search_dir, f)
            break

    return ""


# ── Browser tabs ─────────────────────────────────────────────────────────

def _enrich_browser_tabs(apps):
    """Read Chrome/Edge tabs via DevTools Protocol."""
    browsers = [a for a in apps if a.get("type") in ("chrome", "edge")]
    if not browsers:
        return

    for browser in browsers:
        port = 9222
        try:
            import requests
            r = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2)
            if r.status_code == 200:
                pages = r.json()
                tabs = []
                for page in pages:
                    if page.get("type") == "page":
                        url = page.get("url", "")
                        # Skip chrome internal pages
                        if url.startswith("chrome://") or url.startswith("edge://"):
                            continue
                        tabs.append({
                            "url": url,
                            "title": page.get("title", ""),
                        })
                browser["tabs"] = tabs
                print(Fore.CYAN + f"[WORKSPACE] {browser['type']}: {len(tabs)} tabs via DevTools")
                return
        except Exception:
            pass

        # Fallback: title only
        title = browser.get("window", {}).get("title", "")
        if title:
            browser["tabs"] = [{"url": "", "title": title}]
            print(Fore.YELLOW + f"[WORKSPACE] {browser['type']}: DevTools unavailable, title only")


# ── VS Code ──────────────────────────────────────────────────────────────

def _enrich_vscode(apps):
    """Read VS Code workspace from state.vscdb."""
    vscode_apps = [a for a in apps if a.get("type") == "vscode"]
    if not vscode_apps:
        return

    appdata = os.environ.get("APPDATA", "")
    state_db = os.path.join(appdata, "Code", "User", "globalStorage", "state.vscdb")

    if not os.path.exists(state_db):
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
                recent = entries[0]
                ws = recent.get("folderUri", "").replace("file:///", "").replace("/", "\\")
                # URL-decode percent-encoded characters (m%3A → M:)
                from urllib.parse import unquote
                ws = unquote(ws)
                # Fix drive letter casing
                if len(ws) >= 2 and ws[1] == ":":
                    ws = ws[0].upper() + ws[1:]
                for vs in vscode_apps:
                    vs["workspace_path"] = ws
                    print(Fore.CYAN + f"[WORKSPACE] VS Code: {ws}")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] VS Code state error: {e}")


# ── Explorer folders ─────────────────────────────────────────────────────

def _scan_explorer_folders(apps):
    """Get open Explorer window folder paths via Shell COM."""
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
                if w is None:
                    continue
                loc = w.LocationURL
                if loc:
                    path = unquote(loc.replace("file:///", "").replace("/", "\\"))
                    folders.append({"path": path, "name": w.LocationName})
            except Exception:
                continue

        for i, exp in enumerate(explorers):
            if i < len(folders):
                exp["folder_path"] = folders[i]["path"]
                exp["name"] = folders[i]["name"] or exp["name"]
                print(Fore.CYAN + f"[WORKSPACE] Explorer: {folders[i]['path']}")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Explorer scan error: {e}")



# ── Chrome DevTools setup ────────────────────────────────────────────────

def setup_chrome_devtools():
    """
    Modify Chrome shortcut to add --remote-debugging-port=9222.
    This allows Seven to read Chrome tab URLs.
    Returns True if setup succeeded, False otherwise.
    
    Called from Triggers settings UI when user clicks "Enable tab capture".
    """
    import winreg
    import shutil

    # Find Chrome shortcut in common locations
    shortcuts = [
        os.path.join(os.environ.get("APPDATA", ""),
                     "Microsoft", "Internet Explorer", "Quick Launch",
                     "User Pinned", "TaskBar", "Google Chrome.lnk"),
        os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"),
                     "Desktop", "Google Chrome.lnk"),
        os.path.join(os.path.expanduser("~"), "Desktop", "Google Chrome.lnk"),
        os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
                     "Microsoft", "Windows", "Start Menu", "Programs",
                     "Google Chrome.lnk"),
    ]

    chrome_exe = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    if not os.path.exists(chrome_exe):
        chrome_exe = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"

    if not os.path.exists(chrome_exe):
        print(Fore.YELLOW + "[WORKSPACE] Chrome not found at standard location")
        return False

    flag = "--remote-debugging-port=9222"

    try:
        # Method 1: Create/modify registry for Chrome command line
        # This adds the flag globally when Chrome launches
        reg_path = r"Software\Google\Chrome\Application"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)

        # Read current command line flags
        try:
            current_flags, _ = winreg.QueryValueEx(key, "CommandLineFlags")
        except FileNotFoundError:
            current_flags = ""

        if flag not in current_flags:
            new_flags = f"{current_flags} {flag}".strip()
            winreg.SetValueEx(key, "CommandLineFlags", 0, winreg.REG_SZ, new_flags)
            print(Fore.GREEN + f"[WORKSPACE] Chrome DevTools flag added: {flag}")

        winreg.CloseKey(key)
        return True

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome DevTools setup failed: {e}")
        return False


def check_chrome_devtools():
    """Check if Chrome DevTools is accessible."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:9222/json/version", timeout=2)
        return r.status_code == 200
    except Exception:
        return False
    

# ── RESTORE ──────────────────────────────────────────────────────────────

def restore(apps_config):
    """Restore workspace by launching all apps in parallel."""
    if not apps_config:
        print(Fore.YELLOW + "[WORKSPACE] Nothing to restore")
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
    print(Fore.GREEN + f"[WORKSPACE] Restored {len(apps_config)} apps in {elapsed}ms")


def _restore_one(cfg):
    """Restore a single app from config."""
    app_type = cfg.get("type", "app")
    name = cfg.get("name", "unknown")

    try:
        if app_type in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(cfg)
        elif app_type == "vscode":
            _restore_vscode(cfg)
        elif app_type == "explorer":
            _restore_explorer(cfg)
        elif app_type in ("notepad", "notepad++"):
            _restore_with_file(cfg)
        elif app_type in ("excel", "word", "powerpoint"):
            _restore_with_file(cfg)
        elif app_type == "document":
            _restore_document(cfg)
        elif app_type == "uwp":
            _restore_uwp(cfg)
        elif app_type in ("powershell", "cmd", "terminal"):
            _restore_terminal(cfg)
        else:
            _restore_generic(cfg)
        print(Fore.GREEN + f"  [+] {name}")
    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")


def _restore_browser(cfg):
    """
    Restore browser. Chrome/Edge restore their own tabs automatically
    when reopened (if "Continue where you left off" is enabled in settings).
    We just need to launch the browser.
    """
    browser_type = cfg.get("type", "chrome")
    tabs = cfg.get("tabs", [])
    urls = [t["url"] for t in tabs if t.get("url") and t["url"].startswith("http")]

    browser_cmd = {
        "chrome": "chrome", "edge": "msedge", "firefox": "firefox",
        "brave": "brave", "opera": "opera", "vivaldi": "vivaldi",
    }.get(browser_type, "chrome")

    # If we have captured URLs (DevTools was available), open them
    if urls:
        # Open all URLs at once as arguments
        url_args = " ".join(f'"{u}"' for u in urls)
        subprocess.Popen(f'start {browser_cmd} {url_args}', shell=True)
        print(f"[WORKSPACE] {browser_type}: opened with {len(urls)} tabs")
    else:
        # Just launch browser — Chrome restores its own tabs
        subprocess.Popen(f'start {browser_cmd}', shell=True)
        print(f"[WORKSPACE] {browser_type}: launched (tabs restore via browser settings)")


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


def _restore_with_file(cfg):
    """Restore apps that had a specific file open (Notepad, Excel, etc.)."""
    fp = cfg.get("file_path", "")
    exe = cfg.get("exe_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    elif exe and os.path.exists(exe):
        subprocess.Popen([exe])
    else:
        name = cfg.get("name", "").split(" - ")[-1].strip()
        try:
            from hands.core import open_app
            open_app(name)
        except Exception:
            pass


def _restore_document(cfg):
    fp = cfg.get("file_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    else:
        _restore_generic(cfg)


def _restore_uwp(cfg):
    """Restore UWP apps using protocol URIs."""
    protocol = cfg.get("protocol", "")
    if protocol:
        os.startfile(protocol)


def _restore_terminal(cfg):
    """Restore PowerShell/CMD/Terminal with working directory."""
    cwd = cfg.get("working_dir", "")
    app_type = cfg.get("type", "powershell")
    title = cfg.get("name", "")

    if app_type in ("powershell", "terminal"):
        exe = "powershell"
    else:
        exe = "cmd"

    # Try to use Windows Terminal if available
    wt_path = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                           "Microsoft", "WindowsApps", "wt.exe")
    use_wt = os.path.exists(wt_path)

    if cwd and os.path.exists(cwd):
        if use_wt:
            subprocess.Popen([wt_path, "-d", cwd, exe], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([exe], cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        if use_wt:
            subprocess.Popen([wt_path, exe], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([exe], creationflags=subprocess.CREATE_NEW_CONSOLE)


def _restore_generic(cfg):
    exe = cfg.get("exe_path", "")
    name = cfg.get("name", "")

    if exe and os.path.exists(exe):
        subprocess.Popen([exe])
        return

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