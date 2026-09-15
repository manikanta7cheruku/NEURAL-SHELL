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
        import win32process
        import ctypes
        import psutil

        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return False

        if title.strip().lower() == "program manager":
            return False

        if not win32gui.IsWindowVisible(hwnd):
            return False

        # Strictly block typical Windows 10/11 phantom background apps
        title_lower = title.strip().lower()
        ignore_titles = {
            "microsoft store", "xbox", "settings", "calculator",
            "movies & tv", "task view", "program manager", "photos", "camera",
            "xbox game bar", "game bar", "windows security",
            "cortana", "search", "action center", "notification center",
        }
        if title_lower in ignore_titles:
            return False

        # Block phantom UWP windows by exe name + small size heuristic.
        # UWP apps like Microsoft Store and Xbox create invisible warm-up
        # windows that pass DWM cloak checks on Windows 11.
        try:
            _, _pid = win32process.GetWindowThreadProcessId(hwnd)
            _proc = psutil.Process(_pid)
            _exe = _proc.name().lower()
            _phantom_uwp = {
                "winstore.app.exe", "xboxapp.exe", "xboxpcapp.exe",
                "xboxgameoverlay.exe", "xboxgamingoverlay.exe",
                "microsoft.photos.exe", "windowscamera.exe",
                "skypeapp.exe", "microsoft.todos.exe",
                "microsoft.windowsmaps.exe",
                "microsoft.zunemusic.exe", "microsoft.zunevideo.exe",
                "microsoft.windowscommunicationsapps.exe",
                "microsoft.people.exe", "microsoft.stickynotes.exe",
                "microsoft.msn.weather.exe",
                "microsoft.windows.soundrecorder.exe",
                "microsoft.windowsalarms.exe",
            }
            if _exe in _phantom_uwp:
                rect = win32gui.GetWindowRect(hwnd)
                w, h = rect[2] - rect[0], rect[3] - rect[1]
                if w < 400 or h < 300:
                    return False
                # Check if process is suspended (UWP background state)
                try:
                    if _proc.status() == psutil.STATUS_STOPPED:
                        return False
                except Exception:
                    pass
        except Exception:
            pass

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