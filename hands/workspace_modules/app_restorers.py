"""
hands/workspace_modules/app_restorers.py
Individual app-type restore functions.
Handles browsers (with Chrome profile pinning + tab deduplication),
editors, office, explorer, terminals, and generic/custom apps.
"""

import os
import subprocess
import time
from colorama import Fore

from hands.workspace_modules.helpers import (
    find_chrome_exe,
    find_chrome_profile_dir,
)


def restore_one(cfg):
    """Dispatch to the correct restorer based on app type."""
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

        # Reopen saved document files for non-generic apps if captured
        open_files = cfg.get("open_files", [])
        if open_files and t not in ("chrome", "edge", "brave", "firefox", "app"):
            time.sleep(1.2)
            try:
                from hands.workspace_modules.document_capture import restore_open_files
                _opened = restore_open_files(open_files)
                if _opened > 0:
                    print(Fore.GREEN + f"  [+] {name} (+ {_opened} files)")
            except Exception as _fe:
                print(Fore.YELLOW + f"  [~] {name} file restore: {_fe}")

        # ── Restore saved window geometry (position + size) ──
        _restore_window_geometry(cfg, name)

        print(Fore.GREEN + f"  [+] {name}")
    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")


def _restore_window_geometry(cfg, app_name):
    """
    Move the app's window to its saved x/y/width/height position.
    Runs in a background thread so it doesn't block other restores.
    Waits up to 8 seconds for the window to appear.
    """
    win_info = cfg.get("window") or {}
    x = win_info.get("x")
    y = win_info.get("y")
    w = win_info.get("width")
    h = win_info.get("height")

    # No geometry saved — nothing to do
    if x is None or y is None or w is None or h is None:
        return

    # Skip if geometry is invalid or default (windows we never captured)
    if w < 100 or h < 100:
        return

    import threading as _th
    _th.Thread(
        target=_wait_and_position_window,
        args=(cfg, app_name, int(x), int(y), int(w), int(h)),
        daemon=True
    ).start()


def _wait_and_position_window(cfg, app_name, x, y, w, h):
    """
    Wait for the app's window to appear (up to 8s),
    then move it to the saved position using SetWindowPos.
    """
    import time as _t
    try:
        import win32gui
        import win32con
        import win32process
        import psutil
    except ImportError:
        return

    exe_path = (cfg.get("exe_path") or "").lower()
    exe_name = os.path.basename(exe_path).lower() if exe_path else ""
    saved_title = (cfg.get("window", {}).get("title") or "").lower().strip()
    app_type = (cfg.get("type") or "").lower()

    # Poll for the window every 400ms for up to 8 seconds
    end_time = _t.time() + 8.0
    target_hwnd = None

    while _t.time() < end_time and target_hwnd is None:
        _t.sleep(0.4)

        candidates = []

        def _enum_cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            try:
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc = psutil.Process(pid)
                    proc_exe = (proc.exe() or "").lower()
                    proc_name = proc.name().lower()
                except Exception:
                    return
                # Skip Seven's own windows
                if any(m in proc_exe for m in ["mk-projects\\seven", "\\seven\\"]):
                    return

                # Match by exe path (strongest)
                match_score = 0
                if exe_path and proc_exe == exe_path:
                    match_score = 10
                elif exe_name and proc_name == exe_name:
                    match_score = 8
                elif saved_title:
                    title_lower = title.lower()
                    if title_lower == saved_title:
                        match_score = 6
                    elif saved_title in title_lower or title_lower in saved_title:
                        match_score = 4

                if match_score > 0:
                    candidates.append((match_score, hwnd, title))
            except Exception:
                pass

        try:
            win32gui.EnumWindows(_enum_cb, None)
        except Exception:
            pass

        if candidates:
            # Pick highest score
            candidates.sort(reverse=True)
            _, target_hwnd, matched_title = candidates[0]
            print(Fore.CYAN + f"  [POS] Found '{app_name}' → '{matched_title}' "
                  f"(hwnd={target_hwnd})")
            break

    if target_hwnd is None:
        print(Fore.YELLOW + f"  [POS] Could not find window for '{app_name}' "
              f"within 8s — skipping position restore")
        return

    # Restore window if minimized/maximized so SetWindowPos works
    try:
        placement = win32gui.GetWindowPlacement(target_hwnd)
        if placement[1] in (win32con.SW_SHOWMINIMIZED, win32con.SW_MINIMIZE):
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            _t.sleep(0.15)
    except Exception:
        pass

    # Apply the saved geometry
    try:
        win32gui.SetWindowPos(
            target_hwnd,
            win32con.HWND_TOP,
            x, y, w, h,
            win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
        )
        print(Fore.GREEN + f"  [POS] Positioned '{app_name}' at "
              f"({x}, {y}) {w}×{h}")
    except Exception as e:
        print(Fore.YELLOW + f"  [POS] Position failed for '{app_name}': {e}")


def _restore_browser(cfg):
    """
    Restore browser tabs with profile-pinning and URL deduplication.
    Never launches tabs that are already active in that profile.
    """
    tabs         = cfg.get("tabs", [])
    urls         = [t["url"] for t in tabs if t.get("url", "").startswith("http")]
    profile_name = cfg.get("profile_name", "")
    chrome_exe   = find_chrome_exe()

    if not urls:
        return

    if not chrome_exe:
        for url in urls:
            subprocess.Popen(f'start chrome "{url}"', shell=True)
            time.sleep(0.2)
        return

    chrome_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    profile_dir = find_chrome_profile_dir(chrome_base, profile_name) or "Default"

    # Query currently active tabs for this profile to prevent duplication
    from hands.workspace_modules.url_matching import normalize_url
    from backend.routes.chrome import get_tabs_by_profile

    open_urls_in_profile = set()
    try:
        current_profile_tabs = get_tabs_by_profile()
        for prof_key, tab_list in current_profile_tabs.items():
            if prof_key.lower() == profile_name.lower() or prof_key.lower() == profile_dir.lower():
                for t in tab_list:
                    u = t.get("url", "")
                    if u:
                        open_urls_in_profile.add(normalize_url(u))
    except Exception:
        pass

    # Filter out tabs already open
    missing_urls = [u for u in urls if normalize_url(u) not in open_urls_in_profile] if open_urls_in_profile else list(urls)

    if not missing_urls:
        print(Fore.CYAN + f"[WORKSPACE] Chrome ({profile_name}): All {len(urls)} tabs already open — skipping launch.")
        return

    print(Fore.GREEN + f"[WORKSPACE] Chrome ({profile_name}): Opening {len(missing_urls)} missing tab(s) in profile '{profile_dir}'")
    for u in missing_urls:
        subprocess.Popen([chrome_exe, f"--profile-directory={profile_dir}", u])
        time.sleep(0.12)


def _restore_vscode(cfg):
    ws  = cfg.get("workspace_path", "")
    exe = cfg.get("exe_path", "")

    if ws and os.path.exists(ws):
        try:
            subprocess.Popen(["code", ws])
            return
        except Exception:
            pass

    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe])
            return
        except Exception:
            pass

    try:
        subprocess.Popen("code", shell=True)
    except Exception:
        pass


def _restore_explorer(cfg):
    folder = cfg.get("folder_path", "")
    name   = cfg.get("name", "")

    if folder and os.path.exists(folder):
        subprocess.Popen(["explorer", folder])
        return

    if name:
        clean = name
        for prefix in ("File Explorer: ", "File Explorer — ", "File Explorer - "):
            if name.startswith(prefix):
                clean = name[len(prefix):]
                break
        if " - File Explorer" in clean:
            clean = clean.replace(" - File Explorer", "").strip()
        if os.path.exists(clean):
            subprocess.Popen(["explorer", clean])
            return

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
    exe        = cfg.get("exe_path", "")
    name       = cfg.get("name", "")
    open_files = cfg.get("open_files", [])
    work_dir   = cfg.get("working_dir", "")

    # If document files exist, opening the document automatically opens the associated app
    if open_files:
        try:
            from hands.workspace_modules.document_capture import restore_open_files
            if restore_open_files(open_files) > 0:
                return
        except Exception:
            pass

    # Direct launch with working directory
    if exe and os.path.exists(exe):
        try:
            cwd_arg = work_dir if work_dir and os.path.isdir(work_dir) else None
            subprocess.Popen([exe], cwd=cwd_arg)
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