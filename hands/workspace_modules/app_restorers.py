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
    """
    Type-agnostic app restoration.

    Instead of hardcoded if/elif chains, we detect CAPABILITIES from the
    config data itself. Any app that Seven captured — including apps that
    don't exist yet (Cursor, new AI tools, custom software) — goes through
    the generic restorer which reads whatever data is present:
      - exe_path         → launch executable
      - working_dir      → set cwd (for terminals and dev tools)
      - open_files       → reopen documents (universal)
      - tabs             → Chrome extension knows how (only Chrome/Edge)
      - workspace_path   → VS Code / editor project (only VS Code)
      - folder_path      → File Explorer navigation (only explorer.exe)
      - protocol         → UWP app URI (only UWP apps)

    Specialized restorers are OPT-IN only when we have data to exploit:
      - Chrome/Edge tabs need extension deduplication → _restore_browser
      - VS Code workspace needs `code` CLI → _restore_vscode
      - Explorer folder needs explorer.exe folder arg → _restore_explorer
      - UWP needs URI protocol → _restore_uwp

    Everything else — Notepad, Word, Excel, terminals, Cursor, Notion,
    Figma, Photoshop, whatever the user installs next year — flows
    through _restore_generic which uses exe_path + open_files + working_dir.
    """
    t    = (cfg.get("type") or "").lower()
    name = cfg.get("name", "?")
    tabs = cfg.get("tabs", [])
    ws   = cfg.get("workspace_path", "")
    fld  = cfg.get("folder_path", "")
    prot = cfg.get("protocol", "")

    try:
        # ── SPECIALIZED RESTORERS (opt-in based on data present) ──
        # Chrome/Edge with tab data → use browser restorer for dedup
        if tabs and t in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(cfg)
        # VS Code with workspace path → use `code` CLI
        elif ws and t == "vscode":
            _restore_vscode(cfg)
        # File Explorer with folder path → use explorer.exe with folder arg
        elif t == "explorer":
            _restore_explorer(cfg)
        # UWP app with protocol URI → use os.startfile(protocol)
        elif prot and t == "uwp":
            _restore_uwp(cfg)
        # Terminals with working_dir need CREATE_NEW_CONSOLE flag
        elif t in ("powershell", "cmd", "terminal", "pwsh"):
            _restore_terminal(cfg)
        # Everything else — Notepad, Word, Cursor, Notion, ANY app —
        # uses the generic restorer which reads exe_path + open_files
        else:
            _restore_generic(cfg)

        # ── Universal document reopen (all app types) ──
        # If the app had open documents that weren't handled by the
        # specialized restorer, reopen them via os.startfile()
        # which uses the file's default program association.
        open_files = cfg.get("open_files", [])
        if open_files and t not in ("chrome", "edge", "brave", "firefox"):
            # Skip if generic restorer already handled files
            if t not in ("app", ""):
                time.sleep(1.2)
                try:
                    from hands.workspace_modules.document_capture import restore_open_files
                    _opened = restore_open_files(open_files)
                    if _opened > 0:
                        print(Fore.GREEN + f"  [+] {name} (+ {_opened} files)")
                except Exception as _fe:
                    print(Fore.YELLOW + f"  [~] {name} file restore: {_fe}")

        # ── Universal window geometry restore ──
        # Works for ANY app since it uses Win32 SetWindowPos on the HWND
        _restore_window_geometry(cfg, name)

        print(Fore.GREEN + f"  [+] {name}")
    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")

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

    Multi-monitor safe: if saved coordinates are on a monitor that no
    longer exists (disconnected/rearranged), clamps to nearest monitor.
    """
    import time as _t
    try:
        import win32gui
        import win32con
        import win32process
        import win32api
        import psutil
    except ImportError:
        return

    exe_path = (cfg.get("exe_path") or "").lower()
    exe_name = os.path.basename(exe_path).lower() if exe_path else ""
    saved_title = (cfg.get("window", {}).get("title") or "").lower().strip()

    # ── Multi-monitor safety: clamp coordinates to valid screen space ──
    x, y, w, h = _clamp_to_visible_monitor(x, y, w, h)

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
            candidates.sort(reverse=True)
            _, target_hwnd, matched_title = candidates[0]
            print(Fore.CYAN + f"  [POS] Found '{app_name}' → '{matched_title}' "
                  f"(hwnd={target_hwnd})")
            break

    if target_hwnd is None:
        print(Fore.YELLOW + f"  [POS] Could not find window for '{app_name}' "
              f"within 8s — skipping position restore")
        return

    # Restore window if minimized
    try:
        placement = win32gui.GetWindowPlacement(target_hwnd)
        if placement[1] in (win32con.SW_SHOWMINIMIZED, win32con.SW_MINIMIZE):
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            _t.sleep(0.15)
    except Exception:
        pass

    # Apply the (clamped) saved geometry
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


def _clamp_to_visible_monitor(x, y, w, h):
    """
    Multi-monitor safety: if saved coordinates are on a disconnected or
    rearranged monitor, clamp to the nearest available monitor.

    Uses Win32 MonitorFromPoint to find which monitor the saved position
    belongs to. If none, falls back to primary monitor.

    Returns (clamped_x, clamped_y, clamped_w, clamped_h).
    """
    try:
        import win32api
        import win32con

        # Check if the saved (x, y) point is on any current monitor
        # MonitorFromPoint returns HMONITOR or primary if outside all
        # MONITOR_DEFAULTTONULL = 0 → returns 0 if point is off-screen
        point = (x + w // 2, y + h // 2)  # test window center

        monitors = win32api.EnumDisplayMonitors()
        target_monitor = None

        for hmon, _, rect in monitors:
            mx1, my1, mx2, my2 = rect
            if mx1 <= point[0] <= mx2 and my1 <= point[1] <= my2:
                target_monitor = (mx1, my1, mx2, my2)
                break

        # Saved position is on a valid monitor → use as-is
        if target_monitor:
            return x, y, w, h

        # Saved position is off-screen → clamp to primary monitor
        primary = win32api.GetMonitorInfo(
            win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
        )
        work_area = primary['Work']  # (left, top, right, bottom)
        pw = work_area[2] - work_area[0]
        ph = work_area[3] - work_area[1]

        # Clamp size to fit primary monitor
        new_w = min(w, pw - 40)
        new_h = min(h, ph - 40)
        # Center on primary monitor
        new_x = work_area[0] + (pw - new_w) // 2
        new_y = work_area[1] + (ph - new_h) // 2

        print(Fore.YELLOW + f"  [POS] Off-screen position ({x},{y}) — "
              f"clamped to primary monitor ({new_x},{new_y})")
        return new_x, new_y, new_w, new_h

    except Exception:
        # If clamping fails, use original coordinates
        return x, y, w, h


def _restore_browser(cfg):
    """
    Restore browser tabs with profile-pinning and URL deduplication.

    Chrome has its own session restore that reopens last tabs on launch.
    The Seven Chrome extension syncs tab data every 3 seconds.

    Race condition fix:
      1. Check if Chrome is already running with this profile
      2. If NOT running → launch Chrome → wait up to 6s for extension sync
      3. If already running → extension data should be fresh
      4. Diff saved URLs against extension-reported open URLs
      5. Only open truly missing tabs

    This prevents the "3 tabs become 6" duplication bug.
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

    from hands.workspace_modules.url_matching import normalize_url
    from backend.routes.chrome import get_tabs_by_profile

    chrome_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    profile_dir = find_chrome_profile_dir(chrome_base, profile_name) or "Default"

    # ── STEP 1: Check if Chrome is already running ──
    chrome_was_running = False
    try:
        import psutil as _ps
        for _p in _ps.process_iter(['name']):
            try:
                if _p.info['name'] and 'chrome' in _p.info['name'].lower():
                    chrome_was_running = True
                    break
            except Exception:
                pass
    except Exception:
        pass

    # ── STEP 2: Launch Chrome if not running ──
    if not chrome_was_running:
        print(Fore.CYAN + f"[WORKSPACE] Chrome not running — launching "
              f"profile '{profile_dir}'")
        subprocess.Popen([chrome_exe, f"--profile-directory={profile_dir}"])
        # Wait for Chrome to finish its own session restore
        time.sleep(3.0)

    # ── STEP 3: Poll extension for tab data ──
    # The extension sends tab data every 3 seconds. After Chrome launches,
    # it takes 2-5 seconds for the extension to initialize and first sync.
    # We poll up to 6 seconds to get fresh tab data.
    open_urls_in_profile = set()
    max_wait = 6.0 if not chrome_was_running else 2.0
    poll_interval = 1.0
    elapsed = 0.0

    while elapsed < max_wait:
        try:
            current_profile_tabs = get_tabs_by_profile()
            for prof_key, tab_list in current_profile_tabs.items():
                # Match by profile name, directory, or email prefix
                pk = prof_key.lower()
                pn = profile_name.lower()
                pd = profile_dir.lower()
                if pk == pn or pk == pd or pn in pk or pk in pn:
                    for t in tab_list:
                        u = t.get("url", "")
                        if u:
                            open_urls_in_profile.add(normalize_url(u))

            # If we found tabs for this profile, stop polling
            if open_urls_in_profile:
                print(Fore.CYAN + f"[WORKSPACE] Extension synced: "
                      f"{len(open_urls_in_profile)} tabs found for "
                      f"'{profile_name}' after {elapsed:.0f}s")
                break
        except Exception:
            pass

        time.sleep(poll_interval)
        elapsed += poll_interval

    # ── STEP 4: Diff and open only missing tabs ──
    if open_urls_in_profile:
        missing_urls = [
            u for u in urls
            if normalize_url(u) not in open_urls_in_profile
        ]
        skipped = len(urls) - len(missing_urls)
        if skipped > 0:
            print(Fore.CYAN + f"[WORKSPACE] Chrome ({profile_name}): "
                  f"{skipped} tab(s) already open (session restore), "
                  f"{len(missing_urls)} missing")
    else:
        # Extension never synced — fall back to opening all tabs
        # This is better than opening zero tabs
        print(Fore.YELLOW + f"[WORKSPACE] Chrome ({profile_name}): "
              f"Extension not synced after {max_wait}s — "
              f"opening all {len(urls)} tabs (may duplicate)")
        missing_urls = list(urls)

    if not missing_urls:
        print(Fore.GREEN + f"[WORKSPACE] Chrome ({profile_name}): "
              f"All {len(urls)} tabs already open — nothing to do")
        return

    # ── STEP 5: Open only the missing tabs ──
    print(Fore.GREEN + f"[WORKSPACE] Chrome ({profile_name}): "
          f"Opening {len(missing_urls)} missing tab(s) in '{profile_dir}'")
    for u in missing_urls:
        subprocess.Popen([chrome_exe, f"--profile-directory={profile_dir}", u])
        time.sleep(0.15)


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
    """
    Universal restorer — works for ANY app past, present, or future.

    Priority chain (each step returns True if it worked):
      1. Reopen saved documents (they launch the associated app)
      2. Launch exe_path directly with saved working_dir
      3. Try hands.core.open_app (uses fast launch table + AppOpener)
      4. Fall back to AppOpener alone

    No app type detection. No hardcoded lists. Just data-driven launch.
    """
    exe        = cfg.get("exe_path", "")
    name       = cfg.get("name", "")
    open_files = cfg.get("open_files", [])
    work_dir   = cfg.get("working_dir", "")

    # ── Priority 1: Open saved documents ──
    # os.startfile() reads current disk contents so if user edited the file
    # after scanning, the LATEST version opens. Windows opens it in whatever
    # app is currently associated with that extension.
    if open_files:
        try:
            from hands.workspace_modules.document_capture import restore_open_files
            opened = restore_open_files(open_files)
            if opened > 0:
                # Document opened — the associated app launches automatically
                # Still try to restore working directory context if terminal-like
                return
        except Exception:
            pass

    # ── Priority 2: Direct exe launch with working directory ──
    # This handles ANY app: Cursor, Notion, Figma, custom .exe files,
    # dev tools installed in AppData, portable apps in D:\Tools\, etc.
    if exe and os.path.exists(exe):
        try:
            cwd_arg = work_dir if work_dir and os.path.isdir(work_dir) else None
            subprocess.Popen([exe], cwd=cwd_arg)
            return
        except Exception as e:
            print(Fore.YELLOW + f"  [~] Direct launch failed for {name}: {e}")

    # ── Priority 3: hands.core (fast launch table + Windows URI) ──
    # Handles apps by name using system integrations for:
    # Camera, Settings, Store apps, Calculator, etc.
    clean = name.split(" - ")[-1].strip() if " - " in name else name
    if not clean:
        return

    try:
        from hands.core import open_app
        open_app(clean)
        return
    except Exception:
        pass

    # ── Priority 4: AppOpener (last resort) ──
    # Scans Start Menu for closest name match. Works for installed apps.
    try:
        import AppOpener
        AppOpener.open(clean)
    except Exception:
        pass