"""
hands/window_layout.py
Window arrangement engine for trigger workspace restore.

Arranges restored workspace windows into layouts:
  maximize — all windows maximized (works 100% of the time)
  split    — 2 windows side by side (left/right)
  grid     — up to 4 windows in 2x2 grid
  stack    — 2 windows top/bottom

Uses win32gui.SetWindowPos for precise placement.
Uses SW_MAXIMIZE for maximize (most reliable method).

NOTE: UWP apps (WhatsApp, Calculator) resist SetWindowPos.
      They are silently skipped — other windows still arrange.
"""

import time
import threading
from colorama import Fore

try:
    import win32gui
    import win32con
    import win32api
    import win32process
    import psutil
    WIN32_OK = True
except ImportError:
    WIN32_OK = False
    print(Fore.YELLOW + "[LAYOUT] pywin32 not available")


# ── Skip list — system windows that should never be arranged ──────────────

_SKIP_TITLES = {
    "", "program manager",
    "microsoft text input application",
    "windows input experience",
    "nvidia geforce overlay",
    "click to do",
}

_SKIP_EXE = {
    "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "runtimebroker.exe", "applicationframehost.exe",
    "msedgewebview2.exe", "nvidia overlay.exe",
}


# ── Public entry point ────────────────────────────────────────────────────

def arrange_windows(layout: str, app_names: list) -> tuple:
    """
    Arrange workspace windows into the chosen layout.

    Args:
        layout:    'maximize' | 'split' | 'grid' | 'stack'
        app_names: list of app name strings from the workspace
                   (used to find the right windows)

    Returns:
        (success: bool, message: str)
    """
    if not WIN32_OK:
        return False, "pywin32 not available"

    if not app_names:
        return False, "No app names provided"

    layout = layout.lower().strip()
    if layout not in ("maximize", "split", "grid", "stack"):
        return False, f"Unknown layout: {layout}"

    print(Fore.CYAN + f"[LAYOUT] Arranging {len(app_names)} apps as '{layout}'")

    # Give windows time to finish opening if called right after restore
    time.sleep(0.5)

    # Find window handles for each app name
    handles = _find_handles(app_names)

    if not handles:
        return False, "No matching windows found"

    print(Fore.CYAN + f"[LAYOUT] Found {len(handles)} windows to arrange")

    # Get primary monitor work area (excludes taskbar)
    mx, my, mw, mh = _work_area()

    if layout == "maximize":
        return _do_maximize(handles)
    elif layout == "split":
        return _do_split(handles, mx, my, mw, mh)
    elif layout == "grid":
        return _do_grid(handles, mx, my, mw, mh)
    elif layout == "stack":
        return _do_stack(handles, mx, my, mw, mh)

    return False, "Unknown layout"


# ── Layout implementations ────────────────────────────────────────────────

def _do_maximize(handles):
    """
    Maximize all windows.
    Most reliable layout — uses SW_SHOWMAXIMIZED.
    """
    count = 0
    for hwnd, name in handles:
        try:
            _restore_first(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
            count += 1
            time.sleep(0.05)
        except Exception as e:
            print(Fore.YELLOW + f"[LAYOUT] Maximize skip '{name}': {e}")

    if count == 0:
        return False, "No windows could be maximized"

    print(Fore.GREEN + f"[LAYOUT] Maximized {count} windows")
    return True, f"Maximized {count} windows"


def _do_split(handles, mx, my, mw, mh):
    """
    Split first 2 windows side by side.
    If more than 2 windows — maximize the rest behind them.
    """
    if len(handles) == 1:
        # Only one window — just maximize it
        return _do_maximize(handles)

    half = mw // 2

    # First two windows — side by side
    _place(handles[0], mx,        my, half, mh)
    _place(handles[1], mx + half, my, half, mh)

    # Remaining windows — maximize behind
    for hwnd, name in handles[2:]:
        try:
            _restore_first(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
        except Exception:
            pass

    print(Fore.GREEN + f"[LAYOUT] Split: {handles[0][1]} | {handles[1][1]}")
    return True, f"Split: {handles[0][1]} and {handles[1][1]}"


def _do_grid(handles, mx, my, mw, mh):
    """
    Arrange up to 4 windows in 2x2 grid.
    If fewer than 4 — fills available slots.
    If more than 4 — maximize the rest behind.
    """
    half_w = mw // 2
    half_h = mh // 2

    positions = [
        (mx,          my,          half_w, half_h),  # top-left
        (mx + half_w, my,          half_w, half_h),  # top-right
        (mx,          my + half_h, half_w, half_h),  # bottom-left
        (mx + half_w, my + half_h, half_w, half_h),  # bottom-right
    ]

    placed = min(len(handles), 4)

    for i in range(placed):
        x, y, w, h = positions[i]
        _place(handles[i], x, y, w, h)

    # Extra windows — maximize behind grid
    for hwnd, name in handles[4:]:
        try:
            _restore_first(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
        except Exception:
            pass

    print(Fore.GREEN + f"[LAYOUT] Grid: {placed} windows arranged")
    return True, f"Grid layout: {placed} windows"


def _do_stack(handles, mx, my, mw, mh):
    """
    Stack first 2 windows top and bottom.
    If more than 2 — maximize the rest behind.
    """
    if len(handles) == 1:
        return _do_maximize(handles)

    half_h = mh // 2

    _place(handles[0], mx, my,          mw, half_h)
    _place(handles[1], mx, my + half_h, mw, half_h)

    # Remaining windows — maximize behind
    for hwnd, name in handles[2:]:
        try:
            _restore_first(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
        except Exception:
            pass

    print(Fore.GREEN + f"[LAYOUT] Stack: {handles[0][1]} / {handles[1][1]}")
    return True, f"Stack: {handles[0][1]} and {handles[1][1]}"


# ── Window finding ────────────────────────────────────────────────────────

def _find_handles(app_names: list) -> list:
    """
    Find window handles matching the app names from workspace.
    Returns list of (hwnd, display_name) tuples.
    Ordered to match app_names order as closely as possible.
    """
    # Get all visible windows
    all_windows = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title or title.lower().strip() in _SKIP_TITLES:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            exe = proc.name().lower()
            if exe in _SKIP_EXE:
                return
            # Skip Seven itself
            if exe == "electron.exe" and "seven" in (proc.exe() or "").lower():
                return
        except Exception:
            return
        all_windows.append((hwnd, title))

    try:
        win32process = __import__('win32process')
        win32gui.EnumWindows(_cb, None)
    except Exception as e:
        print(Fore.YELLOW + f"[LAYOUT] EnumWindows error: {e}")
        return []

    if not all_windows:
        return []

    # Match app_names to windows
    # Strategy: for each app name, find the best matching window
    matched = []
    used_hwnds = set()

    for app_name in app_names:
        name_lower = app_name.lower()

        best_hwnd  = None
        best_title = None
        best_score = 0

        for hwnd, title in all_windows:
            if hwnd in used_hwnds:
                continue

            title_lower = title.lower()
            score = 0

            # Exact app name in title
            if name_lower in title_lower:
                score = 3
            # Title in app name
            elif any(word in name_lower for word in title_lower.split()
                     if len(word) > 3):
                score = 2
            # Partial match
            elif any(c in title_lower for c in name_lower.split()):
                score = 1

            if score > best_score:
                best_score = score
                best_hwnd  = hwnd
                best_title = title

        if best_hwnd and best_score > 0:
            matched.append((best_hwnd, best_title))
            used_hwnds.add(best_hwnd)

    # If we found fewer than 2 by name matching,
    # fall back to all visible windows (excluding system)
    if len(matched) < 2:
        print(Fore.YELLOW + "[LAYOUT] Name matching found <2 windows, "
              "falling back to all visible windows")
        matched = [
            (hwnd, title) for hwnd, title in all_windows
            if hwnd not in used_hwnds or True  # include all
        ]
        # De-duplicate
        seen = set()
        deduped = []
        for hwnd, title in matched:
            if hwnd not in seen:
                seen.add(hwnd)
                deduped.append((hwnd, title))
        matched = deduped

    return matched


# ── Helpers ───────────────────────────────────────────────────────────────

def _work_area() -> tuple:
    """Get primary monitor work area (excludes taskbar)."""
    try:
        monitors = win32api.EnumDisplayMonitors()
        for handle, _, _ in monitors:
            info = win32api.GetMonitorInfo(handle)
            work = info['Work']  # (left, top, right, bottom)
            x, y, r, b = work
            return x, y, r - x, b - y
    except Exception:
        pass
    return 0, 0, 1920, 1080


def _restore_first(hwnd):
    """Restore window from minimized state before repositioning."""
    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.08)
        # Remove maximized state
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if style & win32con.WS_MAXIMIZE:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.08)
    except Exception:
        pass


def _place(handle_tuple, x, y, w, h):
    """Place a window at exact coordinates."""
    hwnd, name = handle_tuple
    try:
        _restore_first(hwnd)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            int(x), int(y), int(w), int(h),
            win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
        )
        print(Fore.GREEN + f"  [LAYOUT] Placed '{name}' at "
              f"({x},{y}) {w}×{h}")
    except Exception as e:
        print(Fore.YELLOW + f"  [LAYOUT] Could not place '{name}': {e}")