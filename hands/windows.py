"""
=============================================================================
PROJECT SEVEN - hands/windows.py (Window Mastery)
Version: 1.6

CAPABILITIES:
    - Focus/switch to windows
    - Minimize, maximize, restore windows
    - Snap windows (left/right/top-left/top-right/bottom-left/bottom-right)
    - Split-screen layouts (side-by-side, stack, quad)
    - Minimize all / show desktop
    - Move windows between monitors
    - Resize windows to custom dimensions

USES: pywin32 (win32gui, win32con) for real window handle manipulation

TAG FORMAT:
    ###WINDOW: action=focus target=chrome
    ###WINDOW: action=minimize target=chrome
    ###WINDOW: action=maximize target=chrome
    ###WINDOW: action=restore target=chrome
    ###WINDOW: action=snap target=chrome position=left
    ###WINDOW: action=layout mode=split targets=chrome,code
    ###WINDOW: action=minimize_all
    ###WINDOW: action=show_desktop
=============================================================================
"""

import ctypes
import time
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine

try:
    import win32gui
    import win32con
    import win32api
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print(Fore.RED + "[WINDOWS] pywin32 not installed. Run: pip install pywin32")

# =========================================================================
# WINDOW NAME ALIASES — fuzzy matching for voice commands
# =========================================================================
WINDOW_ALIASES = {
    "chrome": ["google chrome", "chrome"],
    "firefox": ["mozilla firefox", "firefox"],
    "edge": ["microsoft edge", "edge"],
    "brave": ["brave", "brave browser"],
    "code": ["visual studio code", "vs code", "vscode"],
    "vs code": ["visual studio code", "vs code", "vscode"],
    "vscode": ["visual studio code", "vs code", "vscode"],
    "visual studio code": ["visual studio code", "vs code", "vscode"],
    "notepad": ["notepad", "untitled - notepad"],
    "explorer": ["file explorer", "explorer"],
    "files": ["file explorer", "explorer"],
    "terminal": ["command prompt", "cmd", "windows powershell", "powershell", "terminal"],
    "cmd": ["command prompt", "cmd"],
    "powershell": ["windows powershell", "powershell"],
    "spotify": ["spotify"],
    "discord": ["discord"],
    "steam": ["steam"],
    "word": ["word", "microsoft word", "document"],
    "excel": ["excel", "microsoft excel"],
    "task manager": ["task manager"],
    "settings": ["settings"],
    "calculator": ["calculator"],
    "paint": ["paint", "mspaint"],
    "obs": ["obs", "obs studio"],
    "vlc": ["vlc", "vlc media player"],
    "telegram": ["telegram"],
    "whatsapp": ["whatsapp"],
}


def _get_all_windows():
    """
    Enumerate all visible, titled windows.
    Returns list of (hwnd, title) tuples.
    """
    if not WIN32_AVAILABLE:
        return []

    windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and title.strip():
                windows.append((hwnd, title))
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def _find_window(target):
    """
    Find window handle by target name.
    Uses alias expansion + fuzzy title matching.
    Returns (hwnd, title) or (None, None).
    """
    if not WIN32_AVAILABLE:
        return None, None

    target_lower = target.lower().strip()

    # Expand aliases
    search_terms = [target_lower]
    if target_lower in WINDOW_ALIASES:
        search_terms = WINDOW_ALIASES[target_lower] + [target_lower]

    windows = _get_all_windows()

    # Pass 1: Exact title match (case-insensitive)
    for hwnd, title in windows:
        title_lower = title.lower()
        for term in search_terms:
            if term == title_lower:
                return hwnd, title

    # Pass 2: Title contains search term
    for hwnd, title in windows:
        title_lower = title.lower()
        for term in search_terms:
            if term in title_lower:
                return hwnd, title

    # Pass 3: Search term contains part of title
    for hwnd, title in windows:
        title_lower = title.lower()
        for term in search_terms:
            if title_lower in term:
                return hwnd, title

    return None, None


def _find_all_windows(target):
    """
    Find ALL window handles matching target name.
    Returns list of (hwnd, title) tuples.
    """
    if not WIN32_AVAILABLE:
        return []

    target_lower = target.lower().strip()
    search_terms = [target_lower]
    if target_lower in WINDOW_ALIASES:
        search_terms = WINDOW_ALIASES[target_lower] + [target_lower]

    windows = _get_all_windows()
    matches = []

    for hwnd, title in windows:
        title_lower = title.lower()
        for term in search_terms:
            if term in title_lower or title_lower in term:
                matches.append((hwnd, title))
                break

    return matches


def _get_monitor_info():
    """
    Get monitor work areas (excludes taskbar).
    Returns list of (x, y, width, height) tuples.
    """
    if not WIN32_AVAILABLE:
        return [(0, 0, 1920, 1080)]

    monitors = []
    try:
        monitor_handles = win32api.EnumDisplayMonitors()
        for handle, _, _ in monitor_handles:
            info = win32api.GetMonitorInfo(handle)
            work = info['Work']  # (left, top, right, bottom) — excludes taskbar
            x, y, r, b = work
            monitors.append((x, y, r - x, b - y))
    except Exception as e:
        print(Fore.YELLOW + f"[WINDOWS] Monitor enum failed: {e}. Using default.")
        monitors = [(0, 0, 1920, 1080)]

    return monitors


def _restore_if_minimized(hwnd):
    """Restore window if it's minimized, so we can move/resize it."""
    if not WIN32_AVAILABLE:
        return
    try:
        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] == win32con.SW_SHOWMINIMIZED:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
    except:
        pass


def _set_window_pos(hwnd, x, y, w, h):
    """Move and resize a window."""
    if not WIN32_AVAILABLE:
        return
    try:
        _restore_if_minimized(hwnd)
        # Remove maximized state before repositioning
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        if style & win32con.WS_MAXIMIZE:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOP,
            int(x), int(y), int(w), int(h),
            win32con.SWP_SHOWWINDOW
        )
    except Exception as e:
        print(Fore.RED + f"[WINDOWS] SetWindowPos failed: {e}")


def _safe_foreground(hwnd):
    """
    Safely bring window to foreground.
    Uses thread attachment trick to bypass Windows security.
    Never throws — fails silently.
    """
    try:
        foreground_hwnd = win32gui.GetForegroundWindow()
        if foreground_hwnd == hwnd:
            return  # Already foreground
        
        foreground_thread = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
        current_thread = win32api.GetCurrentThreadId()
        
        attached = False
        try:
            if foreground_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, True)
                attached = True
            if target_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, True)
            
            win32gui.BringWindowToTop(hwnd)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, False)
            if target_thread != current_thread:
                ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)
    except:
        # Last resort — just try without attachment
        try:
            win32gui.BringWindowToTop(hwnd)
        except:
            pass


# =========================================================================
# PUBLIC API
# =========================================================================

def get_window_list():
    """Return list of all visible window titles. Used by dev console."""
    windows = _get_all_windows()
    return [(hwnd, title) for hwnd, title in windows
            if title not in ("Program Manager", "Microsoft Text Input Application")]


def manage_window(params):
    """
    Main entry point. Receives parsed params dict from tag:
        {"action": "focus", "target": "chrome", "position": "left", ...}
    Returns (success: bool, message: str)
    """
    if not WIN32_AVAILABLE:
        return False, "Window control unavailable. Install pywin32."

    action = params.get("action", "").lower()
    target = params.get("target", "").lower()

    print(Fore.CYAN + f"🪟 WINDOWS: action={action} target={target} params={params}")

    # --- ACTIONS THAT DON'T NEED A TARGET ---
    if action == "minimize_all":
        return _minimize_all()

    if action == "show_desktop":
        return _show_desktop()

    if action == "layout":
        return _layout(params)

    # --- ACTIONS THAT NEED A TARGET ---
    if not target:
        return False, "No target window specified."

    hwnd, title = _find_window(target)
    if not hwnd:
        return False, f"Can't find window: {target}"

    if action == "focus":
        return _focus(hwnd, title)
    elif action == "minimize":
        return _minimize(hwnd, title)
    elif action == "maximize":
        return _maximize(hwnd, title)
    elif action == "restore":
        return _restore(hwnd, title)
    elif action == "snap":
        position = params.get("position", "left")
        monitor_idx = int(params.get("monitor", "0"))
        return _snap(hwnd, title, position, monitor_idx)
    elif action == "move_monitor":
        monitor_idx = int(params.get("monitor", "1"))
        return _move_to_monitor(hwnd, title, monitor_idx)
    elif action == "resize":
        width = int(params.get("width", "800"))
        height = int(params.get("height", "600"))
        return _resize(hwnd, title, width, height)
    elif action == "center":
        return _center(hwnd, title)
    else:
        return False, f"Unknown window action: {action}"


# =========================================================================
# ACTION IMPLEMENTATIONS
# =========================================================================

def _focus(hwnd, title):
    """Bring window to foreground."""
    try:
        _restore_if_minimized(hwnd)
        _safe_foreground(hwnd)
        print(Fore.GREEN + f"   -> Focused: {title}")
        command_log.log_command("WINDOW", f"focus {title}", True, "Foreground")
        mood_engine.on_command_result(True)
        return True, f"Switched to {title}"
    except Exception as e:
        print(Fore.RED + f"   -> Focus failed: {e}")
        command_log.log_command("WINDOW", f"focus {title}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't focus {title}"


def _minimize(hwnd, title):
    """Minimize window."""
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        print(Fore.GREEN + f"   -> Minimized: {title}")
        command_log.log_command("WINDOW", f"minimize {title}", True, "Minimized")
        mood_engine.on_command_result(True)
        return True, f"Minimized {title}"
    except Exception as e:
        print(Fore.RED + f"   -> Minimize failed: {e}")
        command_log.log_command("WINDOW", f"minimize {title}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't minimize {title}"


def _maximize(hwnd, title):
    """Maximize window."""
    try:
        _restore_if_minimized(hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
        _safe_foreground(hwnd)
        print(Fore.GREEN + f"   -> Maximized: {title}")
        command_log.log_command("WINDOW", f"maximize {title}", True, "Maximized")
        mood_engine.on_command_result(True)
        return True, f"Maximized {title}"
    except Exception as e:
        print(Fore.RED + f"   -> Maximize failed: {e}")
        command_log.log_command("WINDOW", f"maximize {title}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't maximize {title}"


def _restore(hwnd, title):
    """Restore window from minimized/maximized state."""
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        _safe_foreground(hwnd)
        print(Fore.GREEN + f"   -> Restored: {title}")
        command_log.log_command("WINDOW", f"restore {title}", True, "Restored")
        mood_engine.on_command_result(True)
        return True, f"Restored {title}"
    except Exception as e:
        print(Fore.RED + f"   -> Restore failed: {e}")
        command_log.log_command("WINDOW", f"restore {title}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't restore {title}"


def _snap(hwnd, title, position, monitor_idx=0):
    """
    Snap window to a screen region.
    Positions: left, right, top-left, top-right, bottom-left, bottom-right,
               top, bottom
    """
    monitors = _get_monitor_info()
    if monitor_idx >= len(monitors):
        monitor_idx = 0

    mx, my, mw, mh = monitors[monitor_idx]
    half_w = mw // 2
    half_h = mh // 2

    positions = {
        "left":         (mx, my, half_w, mh),
        "right":        (mx + half_w, my, half_w, mh),
        "top":          (mx, my, mw, half_h),
        "bottom":       (mx, my + half_h, mw, half_h),
        "top-left":     (mx, my, half_w, half_h),
        "top-right":    (mx + half_w, my, half_w, half_h),
        "bottom-left":  (mx, my + half_h, half_w, half_h),
        "bottom-right": (mx + half_w, my + half_h, half_w, half_h),
        "full":         (mx, my, mw, mh),
    }

    if position not in positions:
        return False, f"Unknown snap position: {position}. Use: {', '.join(positions.keys())}"

    x, y, w, h = positions[position]
    _set_window_pos(hwnd, x, y, w, h)
    _safe_foreground(hwnd)

    print(Fore.GREEN + f"   -> Snapped {title} to {position}")
    command_log.log_command("WINDOW", f"snap {title} {position}", True, f"Monitor {monitor_idx}")
    mood_engine.on_command_result(True)
    return True, f"Snapped {title} to {position}"


def _minimize_all():
    """Minimize all windows (show desktop)."""
    try:
        # Use the Shell COM object — same as Win+D behavior
        import subprocess
        subprocess.Popen(
            'powershell -command "(New-Object -ComObject Shell.Application).MinimizeAll()"',
            shell=True
        )
        print(Fore.GREEN + "   -> Minimized all windows")
        command_log.log_command("WINDOW", "minimize_all", True, "Shell.MinimizeAll")
        mood_engine.on_command_result(True)
        return True, "All windows minimized"
    except Exception as e:
        print(Fore.RED + f"   -> Minimize all failed: {e}")
        command_log.log_command("WINDOW", "minimize_all", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't minimize all windows"


def _show_desktop():
    """Toggle show desktop (Win+D)."""
    try:
        import subprocess
        subprocess.Popen(
            'powershell -command "(New-Object -ComObject Shell.Application).ToggleDesktop()"',
            shell=True
        )
        print(Fore.GREEN + "   -> Toggled desktop")
        command_log.log_command("WINDOW", "show_desktop", True, "Shell.ToggleDesktop")
        mood_engine.on_command_result(True)
        return True, "Desktop toggled"
    except Exception as e:
        print(Fore.RED + f"   -> Show desktop failed: {e}")
        command_log.log_command("WINDOW", "show_desktop", False, str(e))
        mood_engine.on_command_result(False)
        return False, "Couldn't show desktop"


def _layout(params):
    """
    Arrange multiple windows in a layout.
    Modes: split (side-by-side), stack (top-bottom), quad (4 corners)
    """
    mode = params.get("mode", "split").lower()
    targets_str = params.get("targets", "")

    if not targets_str:
        return False, "No targets for layout. Specify apps."

    targets = [t.strip() for t in targets_str.split(",") if t.strip()]

    if len(targets) < 2:
        return False, "Layout needs at least 2 windows."

    # Find all window handles
    found = []
    missing = []
    for t in targets:
        hwnd, title = _find_window(t)
        if hwnd:
            found.append((hwnd, title, t))
        else:
            missing.append(t)

    if missing:
        return False, f"Can't find: {', '.join(missing)}"

    monitors = _get_monitor_info()
    mx, my, mw, mh = monitors[0]  # Primary monitor

    if mode == "split":
        # Side by side — divide width equally
        count = len(found)
        slice_w = mw // count
        # Position ALL windows first, THEN focus in reverse order
        # so the first window ends up on top
        for i, (hwnd, title, _) in enumerate(found):
            _set_window_pos(hwnd, mx + (i * slice_w), my, slice_w, mh)
        # Focus in reverse so first window is frontmost
        for hwnd, title, _ in reversed(found):
            _focus_silent(hwnd)
            time.sleep(0.15)
        layout_desc = " | ".join([t for _, _, t in found])
        print(Fore.GREEN + f"   -> Split layout: {layout_desc}")
        command_log.log_command("WINDOW", f"layout split {layout_desc}", True, f"{count} windows")
        mood_engine.on_command_result(True)
        return True, f"Split: {layout_desc}"

    elif mode == "stack":
        # Top and bottom — divide height equally
        count = len(found)
        slice_h = mh // count
        for i, (hwnd, title, _) in enumerate(found):
            _set_window_pos(hwnd, mx, my + (i * slice_h), mw, slice_h)
        for hwnd, title, _ in reversed(found):
            _focus_silent(hwnd)
            time.sleep(0.15)
        layout_desc = " / ".join([t for _, _, t in found])
        print(Fore.GREEN + f"   -> Stack layout: {layout_desc}")
        command_log.log_command("WINDOW", f"layout stack {layout_desc}", True, f"{count} windows")
        mood_engine.on_command_result(True)
        return True, f"Stacked: {layout_desc}"

    elif mode == "quad":
        # 4 corners (max 4 windows)
        positions = [
            (mx, my, mw // 2, mh // 2),                    # top-left
            (mx + mw // 2, my, mw // 2, mh // 2),          # top-right
            (mx, my + mh // 2, mw // 2, mh // 2),          # bottom-left
            (mx + mw // 2, my + mh // 2, mw // 2, mh // 2) # bottom-right
        ]
        for i, (hwnd, title, _) in enumerate(found[:4]):
            x, y, w, h = positions[i]
            _set_window_pos(hwnd, x, y, w, h)
        for hwnd, title, _ in reversed(found[:4]):
            _focus_silent(hwnd)
            time.sleep(0.15)
        layout_desc = " | ".join([t for _, _, t in found[:4]])
        print(Fore.GREEN + f"   -> Quad layout: {layout_desc}")
        command_log.log_command("WINDOW", f"layout quad {layout_desc}", True, f"{min(len(found), 4)} windows")
        mood_engine.on_command_result(True)
        return True, f"Quad layout: {layout_desc}"

    else:
        return False, f"Unknown layout mode: {mode}. Use: split, stack, quad"


def _move_to_monitor(hwnd, title, monitor_idx):
    """Move window to a different monitor."""
    monitors = _get_monitor_info()

    if monitor_idx < 0 or monitor_idx >= len(monitors):
        return False, f"Monitor {monitor_idx} doesn't exist. You have {len(monitors)} monitor(s)."

    mx, my, mw, mh = monitors[monitor_idx]

    # Get current window size
    try:
        rect = win32gui.GetWindowRect(hwnd)
        curr_w = rect[2] - rect[0]
        curr_h = rect[3] - rect[1]
        # Center on target monitor
        new_x = mx + (mw - curr_w) // 2
        new_y = my + (mh - curr_h) // 2
        _set_window_pos(hwnd, new_x, new_y, curr_w, curr_h)
        _safe_foreground(hwnd)
        print(Fore.GREEN + f"   -> Moved {title} to monitor {monitor_idx}")
        command_log.log_command("WINDOW", f"move {title} monitor {monitor_idx}", True, "Moved")
        mood_engine.on_command_result(True)
        return True, f"Moved {title} to monitor {monitor_idx}"
    except Exception as e:
        print(Fore.RED + f"   -> Move failed: {e}")
        command_log.log_command("WINDOW", f"move {title} monitor {monitor_idx}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't move {title}"


def _resize(hwnd, title, width, height):
    """Resize window to specific dimensions."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        x = rect[0]
        y = rect[1]
        _set_window_pos(hwnd, x, y, width, height)
        print(Fore.GREEN + f"   -> Resized {title} to {width}x{height}")
        command_log.log_command("WINDOW", f"resize {title} {width}x{height}", True, "Resized")
        mood_engine.on_command_result(True)
        return True, f"Resized {title} to {width}x{height}"
    except Exception as e:
        print(Fore.RED + f"   -> Resize failed: {e}")
        command_log.log_command("WINDOW", f"resize {title} {width}x{height}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't resize {title}"


def _center(hwnd, title):
    """Center window on primary monitor."""
    monitors = _get_monitor_info()
    mx, my, mw, mh = monitors[0]

    try:
        rect = win32gui.GetWindowRect(hwnd)
        curr_w = rect[2] - rect[0]
        curr_h = rect[3] - rect[1]
        new_x = mx + (mw - curr_w) // 2
        new_y = my + (mh - curr_h) // 2
        _set_window_pos(hwnd, new_x, new_y, curr_w, curr_h)
        print(Fore.GREEN + f"   -> Centered {title}")
        command_log.log_command("WINDOW", f"center {title}", True, "Centered")
        mood_engine.on_command_result(True)
        return True, f"Centered {title}"
    except Exception as e:
        print(Fore.RED + f"   -> Center failed: {e}")
        command_log.log_command("WINDOW", f"center {title}", False, str(e))
        mood_engine.on_command_result(False)
        return False, f"Couldn't center {title}"


def _focus_silent(hwnd):
    """Focus without logging (used in layouts to avoid log spam)."""
    try:
        _restore_if_minimized(hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        _safe_foreground(hwnd)
    except:
        pass