"""
hands/workspace_modules/filters.py
Window filtering — matches Task Manager's "Apps" section exactly.
Only skips Seven's own processes. Nothing else.
"""


def is_seven_process(exe_name: str, exe_path: str) -> bool:
    """Only skip Seven's own processes. Nothing else."""
    name_lower = exe_name.lower()
    path_lower = exe_path.lower()

    if name_lower not in ("electron.exe", "pythonw.exe",
                          "python.exe", "seven.exe"):
        return False

    _seven_markers = (
        "mk-projects\\seven",
        "\\seven\\electron",
        "\\seven\\python",
        "program files\\seven",
        "appdata\\local\\seven",
    )
    return any(marker in path_lower for marker in _seven_markers)


def has_taskbar_presence(hwnd: int) -> bool:
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
        import win32gui
        import win32con
        import ctypes

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

        # DWM cloaked check
        try:
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