"""
hands/workspace_modules/app_restorers.py
Type-agnostic restoration system.
v1.4.2 — Offline profile resolution, per-profile Chrome detection,
         terminal type fix, CPU-throttled geometry.
"""

import os
import subprocess
import time
import json as _json
import ctypes
import threading
from colorama import Fore

from hands.workspace_modules.helpers import (
    find_chrome_exe,
    find_chrome_profile_dir,
)

_browser_launch_lock = threading.Lock()


def _force_foreground(hwnd):
    try:
        import win32gui
        import win32con
        import win32process

        if not win32gui.IsWindow(hwnd):
            return

        placement = win32gui.GetWindowPlacement(hwnd)
        if placement[1] in (win32con.SW_SHOWMINIMIZED, win32con.SW_MINIMIZE):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        win32gui.BringWindowToTop(hwnd)

        fore_hwnd = win32gui.GetForegroundWindow()
        if fore_hwnd and fore_hwnd != hwnd:
            fore_thread, _ = win32process.GetWindowThreadProcessId(fore_hwnd)
            curr_thread = win32process.GetCurrentThreadId()
            if fore_thread != curr_thread:
                try:
                    win32process.AttachThreadInput(curr_thread, fore_thread, True)
                    win32gui.SetForegroundWindow(hwnd)
                    win32process.AttachThreadInput(curr_thread, fore_thread, False)
                except Exception:
                    win32gui.SetForegroundWindow(hwnd)
            else:
                win32gui.SetForegroundWindow(hwnd)
        else:
            win32gui.SetForegroundWindow(hwnd)
    except Exception:
        try:
            import win32gui
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass


def restore_one(cfg):
    """Type-agnostic app restoration based on config metadata."""
    t    = (cfg.get("type") or "").lower()
    name = cfg.get("name", "?")
    tabs = cfg.get("tabs", [])
    ws   = cfg.get("workspace_path", "")
    fld  = cfg.get("folder_path", "")
    prot = cfg.get("protocol", "")

    try:
        if tabs and t in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(cfg)
        elif ws and t == "vscode":
            _restore_vscode(cfg)
        elif t == "explorer":
            _restore_explorer(cfg)
        elif prot and t == "uwp":
            _restore_uwp(cfg)
        elif t in ("powershell", "cmd", "terminal", "pwsh"):
            _restore_terminal(cfg)
        else:
            # Check name for terminal hints before generic fallback
            name_lower = name.lower()
            if any(kw in name_lower for kw in ("powershell", "pwsh", "terminal", "cmd", "command prompt")):
                _restore_terminal(cfg)
            else:
                _restore_generic(cfg)

        open_files = cfg.get("open_files", [])
        if open_files and t not in ("chrome", "edge", "brave", "firefox"):
            if t not in ("app", ""):
                time.sleep(1.2)
                try:
                    from hands.workspace_modules.document_capture import restore_open_files
                    _opened = restore_open_files(open_files)
                    if _opened > 0:
                        print(Fore.GREEN + f"  [+] {name} (+ {_opened} files)")
                except Exception as _fe:
                    print(Fore.YELLOW + f"  [~] {name} file restore: {_fe}")

        _restore_window_geometry(cfg, name)

    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")
        import traceback
        traceback.print_exc()


# ── CHROME WINDOW & PROFILE DETECTION ────────────────────────────────────

def _get_chrome_windows_with_profiles():
    """
    Enumerate visible Chrome windows and determine profile directory
    from process command line args.
    """
    windows = []
    try:
        import win32gui
        import win32process
        import psutil

        pid_profile_map = {}
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if (proc.info.get('name') or '').lower() != 'chrome.exe':
                    continue
                cmdline = proc.info.get('cmdline') or []
                for arg in cmdline:
                    if arg.startswith('--profile-directory='):
                        pid_profile_map[proc.info['pid']] = arg.split('=', 1)[1]
                        break
            except Exception:
                continue

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title or not title.strip():
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                if proc.name().lower() != 'chrome.exe':
                    return
                rect = win32gui.GetWindowRect(hwnd)
                w, h = rect[2] - rect[0], rect[3] - rect[1]
                if w < 200 or h < 200:
                    return

                profile_dir = pid_profile_map.get(pid)
                if not profile_dir:
                    try:
                        parent = proc.parent()
                        while parent and parent.name().lower() == 'chrome.exe':
                            profile_dir = pid_profile_map.get(parent.pid)
                            if profile_dir:
                                break
                            parent = parent.parent()
                    except Exception:
                        pass

                windows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "profile_dir": profile_dir,
                })
            except Exception:
                pass

        win32gui.EnumWindows(_cb, None)
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome window scan failed: {e}")
    return windows


def _has_visible_chrome_window():
    return len(_get_chrome_windows_with_profiles()) > 0


def _is_profile_dir_open(profile_dir):
    """
    Check if a Chrome profile directory currently has a running window.
    Uses three fallback layers because Chrome's multi-process model
    hides --profile-directory from many child processes.

    Layer 1: Scan all chrome.exe processes for --profile-directory= arg
    Layer 2: Check window enumeration (visible windows tied to PIDs
             whose parent chain contains the profile directory)
    Layer 3: Check Chrome's session lock file (SingletonLock in the
             profile directory exists ONLY when profile is actively open)
    """
    if not profile_dir:
        return False

    # ── Layer 1: Process cmdline scan ────────────────────────────────
    try:
        import psutil
        target_lower = f"--profile-directory={profile_dir}".lower()
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                if (proc.info.get("name") or "").lower() != "chrome.exe":
                    continue
                cmdline = proc.info.get("cmdline") or []
                for arg in cmdline:
                    if arg and arg.lower() == target_lower:
                        return True
            except Exception:
                continue
    except Exception:
        pass

    # ── Layer 2: Window enumeration ──────────────────────────────────
    try:
        windows = _get_chrome_windows_with_profiles()
        pd_lower = profile_dir.lower()
        for w in windows:
            wpd = (w.get("profile_dir") or "").lower()
            if wpd == pd_lower:
                return True
    except Exception:
        pass

    # ── Layer 3: Session lock file check ─────────────────────────────
    # Chrome creates 'Singleton*' symlinks or lock files inside the
    # profile directory when the profile is actively open.
    # This works even when cmdline is inaccessible.
    try:
        chrome_base = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Google", "Chrome", "User Data"
        )
        pdir_path = os.path.join(chrome_base, profile_dir)
        if os.path.isdir(pdir_path):
            # Chrome creates these files ONLY while profile is running
            for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
                lock_path = os.path.join(pdir_path, lock_name)
                if os.path.exists(lock_path) or os.path.islink(lock_path):
                    return True
            # Additional check: LOCK file inside Session Storage
            # (indicates active Chrome session on this profile)
            session_lock = os.path.join(pdir_path, "Sessions")
            if os.path.isdir(session_lock):
                # Look for a Session file modified in last 5 minutes
                # (Chrome updates these while profile is active)
                import time as _time
                now = _time.time()
                for fname in os.listdir(session_lock):
                    if fname.startswith("Session_") or fname.startswith("Tabs_"):
                        fpath = os.path.join(session_lock, fname)
                        try:
                            mtime = os.path.getmtime(fpath)
                            if (now - mtime) < 300:  # 5 minutes
                                return True
                        except Exception:
                            continue
    except Exception:
        pass

    return False


# ── BULLETPROOF PROFILE RESOLUTION ───────────────────────────────────────

def _scan_chrome_profile_preferences():
    """
    Scan Chrome User Data directory and read each profile's Preferences
    file to build email → profile_dir mapping.
    This is the MOST RELIABLE method — reads ground truth from disk.
    Works 100% offline, no HTTP or Local State needed.
    """
    chrome_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    if not os.path.isdir(chrome_base):
        return {}

    mapping = {}  # key (lowercase) → profile dir name
    try:
        for entry in os.listdir(chrome_base):
            prefs_path = os.path.join(chrome_base, entry, "Preferences")
            if not os.path.isfile(prefs_path):
                continue
            try:
                with open(prefs_path, "r", encoding="utf-8") as f:
                    prefs = _json.load(f)

                # Source 1: account_info (most reliable)
                for acc in prefs.get("account_info", []):
                    email = (acc.get("email") or "").lower().strip()
                    if email:
                        mapping[email] = entry
                        mapping[email.split("@")[0]] = entry

                # Source 2: profile.name
                pname = (prefs.get("profile", {}).get("name") or "").lower().strip()
                if pname and pname not in mapping:
                    mapping[pname] = entry

                # Source 3: profile.user_name
                uname = (prefs.get("profile", {}).get("user_name") or "").lower().strip()
                if uname:
                    mapping[uname] = entry
                    mapping[uname.split("@")[0]] = entry

            except Exception:
                continue
    except Exception:
        pass
    return mapping


def _resolve_profile_dir_bulletproof(profile_name, profile_dir_saved, tabs):
    """
    Determine the correct Chrome profile directory.
    v1.4.2: Reads Preferences files directly from disk — 100% offline.
    """
    chrome_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )

    # LEVEL 1: Trust saved profile_dir if it exists on disk
    if profile_dir_saved and os.path.isdir(os.path.join(chrome_base, profile_dir_saved)):
        print(Fore.CYAN + f"  [PROFILE] '{profile_name}' → '{profile_dir_saved}' (saved)")
        return profile_dir_saved

    # LEVEL 2: Scan Preferences files from ALL profile dirs on disk
    if profile_name:
        pn = profile_name.lower().strip()
        prefs_map = _scan_chrome_profile_preferences()

        # Exact match
        if pn in prefs_map:
            resolved = prefs_map[pn]
            print(Fore.CYAN + f"  [PROFILE] Matched '{profile_name}' → "
                  f"'{resolved}' (Preferences exact match)")
            return resolved

        # Fuzzy match
        best_dir = None
        best_score = 0
        for key, dir_name in prefs_map.items():
            if pn in key or key in pn:
                score = min(len(pn), len(key))
                if score > best_score:
                    best_score = score
                    best_dir = dir_name
        if best_dir and best_score >= 3:
            print(Fore.CYAN + f"  [PROFILE] Matched '{profile_name}' → "
                  f"'{best_dir}' (Preferences fuzzy, score={best_score})")
            return best_dir

    # LEVEL 3: Local State info_cache (backup)
    if profile_name:
        pn = profile_name.lower().strip()
        try:
            local_state_path = os.path.join(chrome_base, "Local State")
            if os.path.isfile(local_state_path):
                with open(local_state_path, "r", encoding="utf-8") as f:
                    state = _json.load(f)
                info_cache = state.get("profile", {}).get("info_cache", {})
                for dir_name, info in info_cache.items():
                    if not os.path.isdir(os.path.join(chrome_base, dir_name)):
                        continue
                    candidates = [
                        (info.get("user_name") or "").lower().strip(),
                        (info.get("user_name") or "").lower().strip().split("@")[0],
                        (info.get("gaia_name") or "").lower().strip(),
                        (info.get("name") or "").lower().strip(),
                    ]
                    for c in candidates:
                        if c and c == pn:
                            print(Fore.CYAN + f"  [PROFILE] Matched '{profile_name}' → "
                                  f"'{dir_name}' (Local State exact)")
                            return dir_name
        except Exception:
            pass

    # LEVEL 4: Extension HTTP (only if Seven online)
    try:
        from hands.workspace_modules.chrome_utils import (
            _fetch_tabs_via_http, _is_seven_backend_alive,
        )
        if _is_seven_backend_alive():
            live = _fetch_tabs_via_http()
            if live and tabs:
                from hands.workspace_modules.url_matching import normalize_url
                saved_fp = {normalize_url(t["url"]) for t in tabs
                            if t.get("url", "").startswith("http")}
                best_match, best_overlap = None, 0
                for pk, tl in live.items():
                    lfp = {normalize_url(lt["url"]) for lt in tl if lt.get("url")}
                    overlap = len(saved_fp & lfp)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = pk
                if best_match and best_overlap >= 1:
                    resolved = _extension_key_to_profile_dir(best_match, chrome_base)
                    if resolved:
                        return resolved
    except Exception:
        pass

    # LEVEL 5: helpers fallback
    try:
        resolved = find_chrome_profile_dir(chrome_base, profile_name)
        if resolved and os.path.isdir(os.path.join(chrome_base, resolved)):
            return resolved
    except Exception:
        pass

    print(Fore.YELLOW + f"  [PROFILE] Could not resolve '{profile_name}' → 'Default'")
    return "Default"


def _extension_key_to_profile_dir(prof_key, chrome_base):
    try:
        local_state_path = os.path.join(chrome_base, "Local State")
        if not os.path.isfile(local_state_path):
            return None
        with open(local_state_path, "r", encoding="utf-8") as f:
            state = _json.load(f)
        info_cache = state.get("profile", {}).get("info_cache", {})
        pk_lower = prof_key.lower().strip()
        for dir_name, info in info_cache.items():
            display = (info.get("name") or "").lower().strip()
            gaia = (info.get("gaia_name") or "").lower().strip()
            user = (info.get("user_name") or "").lower().strip().split("@")[0]
            if pk_lower in (display, gaia, user) or \
               pk_lower in display or display in pk_lower or \
               pk_lower in user or user in pk_lower:
                if os.path.isdir(os.path.join(chrome_base, dir_name)):
                    return dir_name
    except Exception:
        pass
    if prof_key.lower() == "default":
        return "Default"
    return None


# ── BROWSER RESTORE ──────────────────────────────────────────────────────

def _restore_browser(cfg):
    tabs              = cfg.get("tabs", [])
    urls              = [t["url"] for t in tabs if t.get("url", "").startswith("http")]
    profile_name      = cfg.get("profile_name", "")
    profile_dir_saved = cfg.get("profile_dir", "")
    browser_closed_hint = cfg.get("_browser_closed", False)
    chrome_exe        = find_chrome_exe()

    if not urls:
        return
    if not chrome_exe:
        for url in urls:
            subprocess.Popen(f'start chrome "{url}"', shell=True)
            time.sleep(0.2)
        return

    with _browser_launch_lock:
        profile_dir = _resolve_profile_dir_bulletproof(
            profile_name, profile_dir_saved, tabs
        )
        print(Fore.CYAN + f"  [PROFILE] Resolved '{profile_name}' → dir '{profile_dir}'")

        # Validate daemon hint against reality
        any_chrome_open = _has_visible_chrome_window()
        profile_open = _is_profile_dir_open(profile_dir)
        truly_cold = browser_closed_hint and not any_chrome_open

        if truly_cold:
            print(Fore.GREEN + f"[WORKSPACE] Launching Chrome '{profile_dir}' cold "
                  f"with {len(urls)} tab(s)")
            _launch_chrome_tabs(chrome_exe, profile_dir, urls, cold_start=True)
            return

        if not profile_open:
            print(Fore.GREEN + f"[WORKSPACE] Profile '{profile_dir}' not open — "
                  f"launching with {len(urls)} tab(s)")
            _launch_chrome_tabs(chrome_exe, profile_dir, urls, cold_start=False)
            return

        # Profile IS open — dedup against THIS PROFILE ONLY.
        # Never merge URLs across accounts. A tab closed in Profile 1
        # must not be skipped just because Profile 2 has the same URL.
        from hands.workspace_modules.url_matching import normalize_url
        this_profile_urls = set()

        try:
            from hands.workspace_modules.chrome_utils import (
                _fetch_tabs_via_http, _is_seven_backend_alive,
            )
            if _is_seven_backend_alive():
                _live = _fetch_tabs_via_http()
                # _live is keyed by disk directory after re-keying
                # e.g. {"Default": [...], "Profile 1": [...]}
                _this_tabs = _live.get(profile_dir, [])
                if not _this_tabs:
                    # Case-insensitive fallback
                    _pd_lower = profile_dir.lower()
                    for _pk, _tl in _live.items():
                        if _pk.lower() == _pd_lower:
                            _this_tabs = _tl
                            break
                for _t in _this_tabs:
                    _u = _t.get("url", "")
                    if _u:
                        this_profile_urls.add(normalize_url(_u))
        except Exception:
            pass

        if not this_profile_urls:
            try:
                from hands.workspace_modules.chrome_utils import get_open_chrome_tabs
                legacy, _ = get_open_chrome_tabs()
                this_profile_urls = legacy
            except Exception:
                pass

        if not this_profile_urls:
            print(Fore.YELLOW + f"[WORKSPACE] Chrome '{profile_dir}' open but no tab "
                  f"data (Seven offline). Skipping to avoid duplicates.")
            return

        missing = [u for u in urls if normalize_url(u) not in this_profile_urls]
        if not missing:
            print(Fore.CYAN + f"[WORKSPACE] Chrome ({profile_name}/{profile_dir}): "
                  f"All {len(urls)} tabs already open")
            return

        print(Fore.GREEN + f"[WORKSPACE] Chrome ({profile_name}/{profile_dir}): "
              f"Opening {len(missing)}/{len(urls)} missing tab(s)")
        _launch_chrome_tabs(chrome_exe, profile_dir, missing)


def _launch_chrome_tabs(chrome_exe, profile_dir, urls, cold_start=False):
    if not urls:
        return
    try:
        cmd = [chrome_exe, f"--profile-directory={profile_dir}"]
        if cold_start:
            cmd += [
                "--disable-features=InfiniteSessionRestore",
                "--hide-crash-restore-bubble",
            ]
        cmd += urls
        subprocess.Popen(cmd)
        if cold_start:
            time.sleep(1.2)  # Give Chrome extra time to write lock when cold starting
        else:
            time.sleep(0.4)
    except Exception as e:
        print(Fore.RED + f"  [-] Batch launch failed: {e}")
        for url in urls:
            try:
                os.startfile(url)
                time.sleep(0.3)
            except Exception:
                pass


# ── NON-BROWSER APP RESTORERS ────────────────────────────────────────────

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


def _restore_vscode(cfg):
    """Restore VS Code with the EXACT workspace/folder that was scanned."""
    ws  = cfg.get("workspace_path", "")
    exe = cfg.get("exe_path", "")
    name = cfg.get("name", "")

    # Find VS Code executable
    if not exe or not os.path.exists(exe):
        for candidate in [
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Programs", "Microsoft VS Code", "Code.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""),
                         "Microsoft VS Code", "Code.exe"),
        ]:
            if os.path.exists(candidate):
                exe = candidate
                break
    if not exe:
        exe = "code"

    if ws and os.path.exists(ws):
        try:
            print(Fore.CYAN + f"  [VSCODE] Opening workspace: {ws}")
            subprocess.Popen([exe, ws])
            return
        except Exception as e:
            print(Fore.YELLOW + f"  [VSCODE] Failed with exe '{exe}': {e}")
        try:
            os.startfile(ws)
            return
        except Exception:
            pass

    # Fallback: just open VS Code
    try:
        subprocess.Popen([exe])
    except Exception:
        _restore_generic(cfg)


def _restore_terminal(cfg):
    """
    Restore terminal with correct executable and working directory.
    FIX: Checks both type AND name to determine the right shell.
    """
    cwd      = cfg.get("working_dir", "")
    app_type = (cfg.get("type") or "").lower()
    name     = (cfg.get("name") or "").lower()

    # Determine correct shell from type AND name
    if app_type in ("powershell", "pwsh") or "powershell" in name or "pwsh" in name:
        exe = "powershell"
    elif app_type == "terminal" or "windows terminal" in name or "wt" in name:
        exe = "wt"
    elif app_type == "cmd" or "command prompt" in name or name == "cmd":
        exe = "cmd"
    else:
        exe = "powershell"  # Safe default

    flags = subprocess.CREATE_NEW_CONSOLE
    print(Fore.CYAN + f"  [TERMINAL] Opening {exe}" +
          (f" in {cwd}" if cwd else ""))
    if cwd and os.path.exists(cwd):
        subprocess.Popen([exe], cwd=cwd, creationflags=flags)
    else:
        subprocess.Popen([exe], creationflags=flags)


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


def _restore_generic(cfg):
    exe        = cfg.get("exe_path", "")
    name       = cfg.get("name", "")
    open_files = cfg.get("open_files", [])
    work_dir   = cfg.get("working_dir", "")

    if open_files:
        try:
            from hands.workspace_modules.document_capture import restore_open_files
            if restore_open_files(open_files) > 0:
                return
        except Exception:
            pass

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


# ── WINDOW GEOMETRY (CPU-throttled) ──────────────────────────────────────

def _restore_window_geometry(cfg, app_name):
    win_info = cfg.get("window") or {}
    x = win_info.get("x")
    y = win_info.get("y")
    w = win_info.get("width")
    h = win_info.get("height")
    is_maximized = win_info.get("is_maximized", False)

    if x is None or y is None or w is None or h is None:
        return
    if w < 100 or h < 100:
        return

    import threading as _th
    _th.Thread(
        target=_wait_and_position_window,
        args=(cfg, app_name, int(x), int(y), int(w), int(h), is_maximized),
        daemon=True
    ).start()


def _wait_and_position_window(cfg, app_name, x, y, w, h, is_maximized):
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

    x, y, w, h = _clamp_to_visible_monitor(x, y, w, h)

    end_time = _t.time() + 6.0
    target_hwnd = None
    empty_scans = 0
    pid_cache = {}

    while _t.time() < end_time and target_hwnd is None:
        _t.sleep(0.8)
        candidates = []

        def _enum_cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            try:
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                cached = pid_cache.get(pid)
                if cached is None:
                    try:
                        proc = psutil.Process(pid)
                        cached = ((proc.exe() or "").lower(), proc.name().lower())
                        pid_cache[pid] = cached
                    except Exception:
                        pid_cache[pid] = ("", "")
                        return
                proc_exe, proc_name = cached
                if not proc_name:
                    return
                if any(m in proc_exe for m in ["mk-projects\\seven", "\\seven\\"]):
                    return
                match_score = 0
                if exe_path and proc_exe == exe_path:
                    match_score = 10
                elif exe_name and proc_name == exe_name:
                    match_score = 8
                elif saved_title:
                    tl = title.lower()
                    if tl == saved_title:
                        match_score = 6
                    elif saved_title in tl or tl in saved_title:
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
            candidates.sort(reverse=True)
            _, target_hwnd, _ = candidates[0]
            break
        else:
            empty_scans += 1
            if empty_scans >= 3:
                return

    if target_hwnd is None:
        return

    prev_rect = None
    stable_count = 0
    for _ in range(10):
        _t.sleep(0.15)
        try:
            rect = win32gui.GetWindowRect(target_hwnd)
        except Exception:
            break
        if prev_rect == rect:
            stable_count += 1
            if stable_count >= 3:
                break
        else:
            stable_count = 0
            prev_rect = rect

    try:
        placement = win32gui.GetWindowPlacement(target_hwnd)
        if placement[1] in (win32con.SW_SHOWMINIMIZED, win32con.SW_MINIMIZE):
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            _t.sleep(0.2)
    except Exception:
        pass

    if is_maximized:
        try:
            win32gui.ShowWindow(target_hwnd, win32con.SW_MAXIMIZE)
            _force_foreground(target_hwnd)
            return
        except Exception:
            pass

    try:
        placement = win32gui.GetWindowPlacement(target_hwnd)
        if placement[1] == win32con.SW_SHOWMAXIMIZED:
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            _t.sleep(0.2)
    except Exception:
        pass

    def _apply():
        try:
            win32gui.SetWindowPos(
                target_hwnd, win32con.HWND_TOP,
                x, y, w, h, win32con.SWP_SHOWWINDOW,
            )
            _force_foreground(target_hwnd)
            return True
        except Exception:
            return False

    _apply()
    _t.sleep(0.3)
    try:
        r = win32gui.GetWindowRect(target_hwnd)
        if abs((r[2]-r[0]) - w) > 20 or abs((r[3]-r[1]) - h) > 20:
            _apply()
    except Exception:
        pass


def _clamp_to_visible_monitor(x, y, w, h):
    try:
        import win32api
        import win32con
        point = (x + w // 2, y + h // 2)
        for hmon, _, rect in win32api.EnumDisplayMonitors():
            if rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]:
                return x, y, w, h
        primary = win32api.GetMonitorInfo(
            win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
        )
        wa = primary['Work']
        pw, ph = wa[2] - wa[0], wa[3] - wa[1]
        return wa[0] + (pw - min(w, pw-40)) // 2, \
               wa[1] + (ph - min(h, ph-40)) // 2, \
               min(w, pw-40), min(h, ph-40)
    except Exception:
        return x, y, w, h