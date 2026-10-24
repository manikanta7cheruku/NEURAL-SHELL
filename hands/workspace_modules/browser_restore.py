"""
hands/workspace_modules/browser_restore.py

Reopens one saved browser window: the right browser (Chrome, Edge or Brave), the right profile, only the tabs that
are not already open, and never on top of the browser's own session restore.

WHY TABS USED TO DUPLICATE
    With "Continue where you left off", launching chrome.exe with URLs reopens the last session AND the URLs.
    Now, when the browser is closed and set to continue, Seven starts it without URLs, waits for its own restore
    to finish, then compares and opens only what is missing.

WHAT "ALREADY OPEN" MEANS
    A saved tab is open when its normalised URL is open in that profile (Seven extension, or the active tab's
    address) or a tab with the same title is open in that profile (UI Automation, works without the extension).
"""

import subprocess
import threading
import time
from typing import Dict, List

from colorama import Fore

from hands.workspace_modules import browser_sessions
from hands.workspace_modules.browser_tabs import window_tabs
from hands.workspace_modules.url_matching import normalize_url

_lock = threading.Lock()


def _browser_windows(browser: str) -> List[int]:
    import psutil
    import win32gui
    import win32process
    exe = browser_sessions.BROWSERS[browser]["exe_name"]
    found = []

    def _cb(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if psutil.Process(pid).name().lower() == exe and not win32gui.GetWindow(hwnd, 4):   # GW_OWNER
                    found.append(hwnd)
        except Exception:
            pass
        return True
    win32gui.EnumWindows(_cb, None)
    return found


def open_state(browser: str, profile_dir: str) -> Dict[str, set]:
    """{"urls", "titles"} open right now in one profile of one browser."""
    from hands.workspace_modules.browser_capture import _extension_pool, _profile_from_buttons, _profile_from_title
    import win32gui
    urls, titles = set(), set()
    for hwnd in _browser_windows(browser):
        info = window_tabs(hwnd)
        if "Incognito" in info.get("buttons", []):
            continue
        prof = (_profile_from_buttons(browser, info.get("buttons", []))
                or _profile_from_title(browser, win32gui.GetWindowText(hwnd)) or "Default")
        if prof != profile_dir:
            continue
        titles.update(t.strip() for t in info["titles"])
        if info["active_url"]:
            urls.add(normalize_url(info["active_url"]))
    for tab in _extension_pool():
        if tab["profile_dir"] == profile_dir and tab["title"] in titles:
            urls.add(normalize_url(tab["url"]))
    return {"urls": urls, "titles": titles}


def _wait_for_window(browser: str, before: int, timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if len(_browser_windows(browser)) > before:
            return True
        time.sleep(0.25)
    return False


_BLANK = {"new tab", "new tab page"}


def _close_blank_tabs(browser: str) -> None:
    """Close the empty "New tab" a plain browser start leaves behind, once real tabs are open beside it."""
    try:
        from hands.workspace_modules.browser_tabs import _uia
        uia, U = _uia()
        for hwnd in _browser_windows(browser):
            root = uia.ElementFromHandle(hwnd)
            tabs = root.FindAll(4, uia.CreatePropertyCondition(30003, 50019))
            if tabs.Length < 2:
                continue
            for i in range(tabs.Length - 1, -1, -1):
                tab = tabs.GetElement(i)
                if (tab.CurrentName or "").strip().lower() in _BLANK:
                    close = tab.FindFirst(4, uia.CreatePropertyCondition(30003, 50000))
                    if close:
                        close.GetCurrentPattern(10000).QueryInterface(U.IUIAutomationInvokePattern).Invoke()
    except Exception as exc:
        print(Fore.YELLOW + f"[WORKSPACE] Blank tab left open: {exc}")


def restore_browser(cfg: Dict) -> Dict:
    """Open what is missing from one saved window. Returns {"opened", "already_open", "unrestorable"}."""
    browser = (cfg.get("type") or "chrome").lower()
    if browser not in browser_sessions.BROWSERS:
        browser = "chrome"
    exe = browser_sessions.find_exe(browser) or cfg.get("exe_path")
    profile = cfg.get("profile_dir") or "Default"
    saved = cfg.get("tabs") or []
    reopenable = [t for t in saved if (t.get("url") or "").startswith(("http://", "https://", "file:///"))]
    result = {"opened": 0, "already_open": 0, "unrestorable": len(saved) - len(reopenable)}
    if not exe or not reopenable:
        return result

    with _lock:
        started_here = False
        if not _browser_windows(browser):
            # No window open. The browser may bring back its last session by itself ("Continue where you left
            # off", or Edge reopening its last window after running in the background), and it does not say
            # which in any setting Seven can trust. So start it plainly, let it finish, then fill in the gaps.
            print(Fore.CYAN + f"[WORKSPACE] Starting {browser} first so its own restore can't duplicate tabs")
            subprocess.Popen([exe, f"--profile-directory={profile}"])
            _wait_for_window(browser, 0)
            time.sleep(2.5)
            started_here = True
        running = True

        state = open_state(browser, profile) if running else {"urls": set(), "titles": set()}
        missing = [t for t in reopenable
                   if normalize_url(t["url"]) not in state["urls"] and (t.get("title") or "").strip() not in state["titles"]]
        result["already_open"] = len(reopenable) - len(missing)
        if not missing:
            print(Fore.CYAN + f"[WORKSPACE] {cfg.get('name', browser)}: all {len(reopenable)} tabs already open")
            return result

        # A window none of whose tabs are open comes back as its own window, keeping the saved layout. Right after
        # starting the browser, its first window is used instead.
        own_window = not started_here and len(missing) == len(reopenable)
        before = len(_browser_windows(browser))
        cmd = [exe, f"--profile-directory={profile}"] + (["--new-window"] if own_window else [])
        subprocess.Popen(cmd + [t["url"] for t in missing])
        if own_window:
            _wait_for_window(browser, before, timeout=8.0)
        else:
            time.sleep(1.0)
        if started_here:
            _close_blank_tabs(browser)
        result["opened"] = len(missing)
        print(Fore.GREEN + f"[WORKSPACE] {cfg.get('name', browser)}: opened {len(missing)}, "
                           f"{result['already_open']} already open, {result['unrestorable']} without an address")
        return result
