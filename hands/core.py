"""
=============================================================================
PROJECT SEVEN - hands/core.py (The Executioner)
Version: 2.0 (Dashboard-Ready + Three-Tier App Launch)

CHANGES FROM V1.1.1:
    1. NEW: App aliases now read from config.json (user-editable via dashboard)
    2. NEW: Custom app paths — user can map names to .exe paths
    3. NEW: Failed app log — records failures for dashboard "Fix" feature
    4. NEW: Three-tier launch: aliases → AppOpener → custom paths
    5. KEPT: All close logic unchanged
    6. KEPT: All command logging + mood feedback
=============================================================================
"""

import os
import threading
import webbrowser
import pyautogui
import datetime
import psutil
import subprocess
from AppOpener import open as app_opener
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine
import config

# PROTECTED SYSTEM APPS
SAFE_APPS = ["system", "registry", "service", "nvidia", "antivirus", "explorer"]

# FAST LAUNCH TABLE - bypasses AppOpener for common apps
# Key: lowercase name fragment, Value: launch command or URI
_FAST_LAUNCH = {
    "chrome":      ("exe", "chrome"),
    "firefox":     ("exe", "firefox"),
    "edge":        ("uri", "microsoft-edge:"),
    "notepad":     ("exe", "notepad"),
    "notepad++":   ("exe", "notepad++"),
    "vlc":         ("exe", "vlc"),
    "spotify":     ("uri", "spotify:"),
    "telegram":    ("exe", "telegram"),
    "discord":     ("exe", "discord"),
    "steam":       ("exe", "steam"),
    "vs code":     ("exe", "code"),
    "vscode":      ("exe", "code"),
    "code":        ("exe", "code"),
    "word":        ("exe", "winword"),
    "excel":       ("exe", "excel"),
    "powerpoint":  ("exe", "powerpnt"),
    "paint":       ("exe", "mspaint"),
    "cmd":         ("exe", "cmd"),
    "terminal":    ("exe", "wt"),
    "powershell":  ("exe", "powershell"),
    "task manager":("exe", "taskmgr"),
    "obs":         ("exe", "obs64"),
    "zoom":        ("exe", "zoom"),
    "teams":       ("uri", "msteams:"),
    "outlook":     ("exe", "outlook"),
    "file manager":("exe", "explorer"),
    "files":       ("exe", "explorer"),
}


def _fast_launch(app_name):
    """
    Try launching from fast lookup table first.
    Returns True if launched, False if not in table.
    Zero AppOpener overhead.
    """
    clean = app_name.lower().strip()
    entry = None

    # Exact match first
    if clean in _FAST_LAUNCH:
        entry = _FAST_LAUNCH[clean]
    else:
        # Partial match
        for key, val in _FAST_LAUNCH.items():
            if key in clean or clean in key:
                entry = val
                break

    if not entry:
        return False

    launch_type, target = entry
    try:
        if launch_type == "uri":
            os.startfile(target)
        else:
            # Direct ShellExecute bypasses cmd.exe completely for sub-15ms launches
            try:
                os.startfile(target)
            except FileNotFoundError:
                _CREATE_NO_WINDOW = 0x08000000
                subprocess.Popen(target, creationflags=_CREATE_NO_WINDOW)
        print(Fore.GREEN + f"   -> Fast launch (Lightning API): {target}")
        return True
    except Exception as e:
        print(Fore.YELLOW + f"   -> Fast launch failed: {e}")
        return False


def _get_aliases():
    """Get app aliases from config (user-editable via dashboard)."""
    return config.KEY.get("commands", {}).get("app_aliases", {})


def _get_custom_paths():
    """Get custom app exe paths from config."""
    return config.KEY.get("commands", {}).get("app_paths", {})


def _resolve_alias(app_name):
    """
    Resolve an app name through aliases.
    Returns the resolved name (or original if no alias found).
    """
    aliases = _get_aliases()
    clean = app_name.lower().strip()
    if clean in aliases:
        resolved = aliases[clean]
        print(Fore.CYAN + f"   -> Alias '{clean}' → '{resolved}'")
        return resolved
    return clean


# Maps custom alias -> process name that opened it
# So "close pic" can find "Microsoft.Photos.exe" or "vlc.exe"
_EXTENSION_PROCESS_MAP = {
    # Default app order — _watch_new_process will register the exact one used
    ".jpg":  ["Microsoft.Photos", "Photos", "mspaint", "gimp"],
    ".jpeg": ["Microsoft.Photos", "Photos", "mspaint"],
    ".png":  ["Microsoft.Photos", "Photos", "mspaint", "gimp"],
    ".gif":  ["Microsoft.Photos", "Photos"],
    ".bmp":  ["mspaint", "Microsoft.Photos"],
    ".heic": ["Microsoft.Photos", "Photos"],
    ".webp": ["Microsoft.Photos", "Photos", "mspaint"],
    ".raw":  ["Microsoft.Photos", "Photos"],
    ".mp4":  ["vlc", "vlc.exe", "wmplayer", "WindowsMediaPlayer", "Movies"],
    ".mp3":  ["vlc", "vlc.exe", "wmplayer", "Groove", "Music"],
    ".avi":  ["vlc", "vlc.exe", "wmplayer"],
    ".mkv":  ["vlc", "vlc.exe", "wmplayer"],
    ".mov":  ["vlc", "vlc.exe", "wmplayer"],
    ".pdf":  ["AcroRd32", "Acrobat", "FoxitReader", "edge", "chrome"],
    ".docx": ["WINWORD"],
    ".xlsx": ["EXCEL"],
    ".pptx": ["POWERPNT"],
    ".mp3": ["vlc", "wmplayer", "Groove", "Music"],
    ".pdf": ["AcroRd32", "Acrobat", "FoxitReader", "edge", "chrome"],
    ".docx": ["WINWORD"],
    ".xlsx": ["EXCEL"],
    ".pptx": ["POWERPNT"],
}

_custom_alias_to_process = {}

def _load_process_registry():
    """Load saved alias->process mappings from config on startup."""
    saved = config.KEY.get("commands", {}).get("alias_process_map", {})
    for alias, procs in saved.items():
        _custom_alias_to_process[alias] = procs if isinstance(procs, list) else [procs]
    if saved:
        print(Fore.CYAN + f"   -> Loaded {len(saved)} alias->process mappings from config")

_load_process_registry()

def _register_custom_process(alias, file_path):
    """Remember what process handles a custom alias."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _EXTENSION_PROCESS_MAP:
        _custom_alias_to_process[alias] = _EXTENSION_PROCESS_MAP[ext]
        print(Fore.CYAN + f"   -> Registered {alias} -> {_EXTENSION_PROCESS_MAP[ext]}")


def _try_custom_path(app_name):
    """
    Try launching an app via custom path.
    Handles: .exe, .png, .pdf, .mp4, paths with spaces, any file type.
    Returns True if successful, False if not found or failed.
    """
    paths = _get_custom_paths()
    clean = app_name.lower().strip()

    if clean not in paths:
        return False

    exe_path = paths[clean]

    if not os.path.exists(exe_path):
        print(Fore.RED + f"   -> Custom path not found: {exe_path}")
        return False

    try:
        ext = os.path.splitext(exe_path)[1].lower()

        # Snapshot PIDs BEFORE launch so _focus_new_window can find the new process
        _before_launch = {p.pid for p in psutil.process_iter(['pid'])}

        if ext == '.exe':
            subprocess.Popen([exe_path])
        elif os.path.isdir(exe_path):
            import ctypes as _ctypes
            subprocess.Popen(f'explorer "{exe_path}"', shell=True)
            def _focus_explorer():
                import time
                time.sleep(1.5)
                try:
                    hwnd = _ctypes.windll.user32.FindWindowW("CabinetWClass", None)
                    if hwnd:
                        _ctypes.windll.user32.ShowWindow(hwnd, 9)
                        _ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            import threading as _thr
            _thr.Thread(target=_focus_explorer, daemon=True).start()    
        elif ext in {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.heic', '.webp', '.raw'}:
            # os.startfile opens in user's default image app
            # Pass absolute path — Windows opens the specific file, not gallery
            os.startfile(os.path.abspath(exe_path))
        else:
            os.startfile(exe_path)

        # Bring new window to foreground by finding it via new process PID
        def _focus_new_window(before_pids_snap):
            import time
            import ctypes
            import ctypes.wintypes

            user32  = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.wintypes.BOOL,
                ctypes.wintypes.HWND,
                ctypes.wintypes.LPARAM,
            )

            def _try_focus():
                """Find visible titled window in new processes and bring to front."""
                new_pids = set()
                for p in psutil.process_iter(['pid']):
                    try:
                        if p.pid not in before_pids_snap:
                            new_pids.add(p.pid)
                    except Exception:
                        continue

                if not new_pids:
                    return False

                found = [0]

                def _cb(hwnd, _):
                    try:
                        if not user32.IsWindowVisible(hwnd):
                            return True
                        pid = ctypes.wintypes.DWORD(0)
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value not in new_pids:
                            return True
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length < 1:
                            return True
                        found[0] = hwnd
                        return False   # Stop enumeration — found it
                    except Exception:
                        return True

                user32.EnumWindows(WNDENUMPROC(_cb), 0)

                if found[0]:
                    user32.ShowWindow(found[0], 9)        # SW_RESTORE
                    user32.SetForegroundWindow(found[0])
                    user32.BringWindowToTop(found[0])
                    print(Fore.GREEN + f"   -> Window focused: hwnd={found[0]}")
                    return True
                return False

            # Poll every second for up to 12 seconds for new process window
            for attempt in range(12):
                time.sleep(1.0)
                try:
                    if _try_focus():
                        return
                except Exception:
                    pass

            # Try known media player window classes
            try:
                _player_classes = [
                    "Qt5152QWindowIcon",        # VLC
                    "MediaPlayerClassicW",       # MPC-HC
                    "VLC VideoLanClt",           # VLC alternate
                    "ApplicationFrameWindow",    # Windows Media Player (UWP)
                    "WMPlayerApp",               # Old Windows Media Player
                ]
                for _cls in _player_classes:
                    hwnd = user32.FindWindowW(_cls, None)
                    if hwnd:
                        user32.ShowWindow(hwnd, 9)
                        user32.SetForegroundWindow(hwnd)
                        user32.BringWindowToTop(hwnd)
                        print(Fore.GREEN + f"   -> Found media player by class: {hwnd}")
                        return
                # Last resort — find any visible window with media player process
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        pn = proc.info['name'].lower()
                        if any(mp in pn for mp in ['vlc', 'wmplayer', 'mpc']):
                            found_vlc = [0]
                            def _vlc_cb(hwnd, _):
                                pid = ctypes.wintypes.DWORD(0)
                                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                                if pid.value == proc.pid and user32.IsWindowVisible(hwnd):
                                    if user32.GetWindowTextLengthW(hwnd) > 0:
                                        found_vlc[0] = hwnd
                                return True
                            user32.EnumWindows(WNDENUMPROC(_vlc_cb), 0)
                            if found_vlc[0]:
                                user32.ShowWindow(found_vlc[0], 9)
                                user32.SetForegroundWindow(found_vlc[0])
                                print(Fore.GREEN + f"   -> Found VLC window: {found_vlc[0]}")
                                return
                    except Exception:
                        continue
            except Exception as _e:
                print(Fore.YELLOW + f"   -> Media window search failed: {_e}")
            print(Fore.YELLOW + "   -> Could not bring window to front")

        threading.Thread(target=_focus_new_window, args=(_before_launch,), daemon=True).start()

        print(Fore.GREEN + f"   -> Launched via custom path: {exe_path}")
        command_log.log_command("OPEN", clean, True, f"Custom path: {exe_path}")
        mood_engine.on_command_result(True)

        # Watch for the new process — pass before_pids from BEFORE launch
        def _watch_new_process(alias, path, before_pids):
            import time
            time.sleep(3.0)

            _system_procs = {
                'svchost.exe', 'conhost.exe', 'RuntimeBroker.exe',
                'SearchIndexer.exe', 'WmiPrvSE.exe', 'dllhost.exe',
                'backgroundTaskHost.exe', 'sihost.exe', 'taskhostw.exe',
                'ApplicationFrameHost.exe', 'ShellExperienceHost.exe',
            }

            # Find new process — must be a real app process
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if p.pid not in before_pids:
                        pname = p.info['name']
                        if pname in _system_procs:
                            continue
                        if not pname.lower().endswith('.exe'):
                            continue
                        # Register as single string, not list
                        _custom_alias_to_process[alias] = [pname]
                        try:
                            _apm = config.KEY.get("commands", {}).get("alias_process_map", {})
                            _apm[alias] = [pname]
                            if "commands" not in config.KEY:
                                config.KEY["commands"] = {}
                            config.KEY["commands"]["alias_process_map"] = _apm
                            config.save_config()
                        except Exception:
                            pass
                        print(Fore.GREEN + f"   -> Registered '{alias}' -> '{pname}'")
                        return
                except Exception:
                    continue

            # No new process found — app reused existing instance (VLC, Photos)
            # For media files, scan running processes for known players
            ext = os.path.splitext(path)[1].lower()
            _media_map = {
                '.mp4': ['vlc.exe', 'wmplayer.exe', 'Movies.exe'],
                '.avi': ['vlc.exe', 'wmplayer.exe'],
                '.mkv': ['vlc.exe', 'wmplayer.exe'],
                '.mov': ['vlc.exe', 'wmplayer.exe'],
                '.mp3': ['vlc.exe', 'wmplayer.exe', 'Groove.exe'],
                '.jpg': ['Photos.exe', 'Microsoft.Photos.exe'],
                '.jpeg': ['Photos.exe', 'Microsoft.Photos.exe'],
                '.png': ['Photos.exe', 'Microsoft.Photos.exe'],
            }
            if ext in _media_map:
                for candidate in _media_map[ext]:
                    cname = candidate.lower().replace('.exe', '')
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            if cname in proc.info['name'].lower():
                                actual_name = proc.info['name']
                                _custom_alias_to_process[alias] = [actual_name]
                                try:
                                    _apm = config.KEY.get("commands", {}).get("alias_process_map", {})
                                    _apm[alias] = [actual_name]
                                    if "commands" not in config.KEY:
                                        config.KEY["commands"] = {}
                                    config.KEY["commands"]["alias_process_map"] = _apm
                                    config.save_config()
                                except Exception:
                                    pass
                                print(Fore.GREEN + f"   -> Registered '{alias}' -> '{actual_name}' (existing process)")
                                return
                        except Exception:
                            continue

            # Final fallback
            _register_custom_process(alias, path)

        threading.Thread(
            target=_watch_new_process,
            args=(clean, exe_path, _before_launch),
            daemon=True
        ).start()
        return True

    except Exception as e:
        print(Fore.RED + f"   -> Custom path launch failed: {e}")
        command_log.log_command("OPEN", clean, False, f"Custom path failed: {e}")
        mood_engine.on_command_result(False)
        return False    


def _log_failed_app(user_phrase, attempted_name, error_detail):
    """Log a failed app open attempt for the dashboard Fix feature."""
    failed_list = config.KEY.get("commands", {}).get("failed_apps", [])
    
    entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "phrase": user_phrase,
        "attempted": attempted_name,
        "error": error_detail
    }
    
    failed_list.append(entry)
    
    # Keep only last 50 failures
    if len(failed_list) > 50:
        failed_list = failed_list[-50:]
    
    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    config.KEY["commands"]["failed_apps"] = failed_list
    config.save_config()


# Process name resolution table - maps common names to actual Windows process names
# This is why "close camera" works even though process is "WindowsCamera.exe"
_PROCESS_NAME_MAP = {
    # camera intentionally excluded — UWP app needs psutil PID kill, not taskkill /IM
    "monitor":       ["perfmon.exe", "resmon.exe"],
    "resource monitor": ["perfmon.exe", "resmon.exe"],
    "calculator":    ["CalculatorApp.exe", "calc.exe"],
    "photos":        ["Microsoft.Photos.exe", "Photos.exe"],
    "store":         ["WinStore.App.exe"],
    "mail":          ["HxOutlook.exe", "HxTsr.exe"],
    "maps":          ["Maps.exe"],
    "clock":         ["TimeDate.CPL"],
    "settings":      ["SystemSettings.exe"],
    "paint":         ["mspaint.exe"],
    "notepad":       ["notepad.exe"],
    "explorer":      ["explorer.exe"],
    "chrome":        ["chrome.exe"],
    "firefox":       ["firefox.exe"],
    "edge":          ["msedge.exe"],
    "brave":         ["brave.exe"],
    "spotify":       ["Spotify.exe"],
    "discord":       ["Discord.exe"],
    "telegram":      ["Telegram.exe"],
    "whatsapp":      ["WhatsApp.exe", "WhatsAppDesktop.exe"],
    "vlc":           ["vlc.exe"],
    "zoom":          ["Zoom.exe"],
    "teams":         ["Teams.exe", "ms-teams.exe"],
    "outlook":       ["OUTLOOK.EXE"],
    "word":          ["WINWORD.EXE"],
    "excel":         ["EXCEL.EXE"],
    "powerpoint":    ["POWERPNT.EXE"],
    "obs":           ["obs64.exe", "obs32.exe"],
    "steam":         ["steam.exe"],
    "vs code":       ["Code.exe"],
    "vscode":        ["Code.exe"],
    "code":          ["Code.exe"],
    "task manager":  ["Taskmgr.exe"],
    "powershell":    ["powershell.exe", "pwsh.exe"],
    "cmd":           ["cmd.exe"],
    "terminal":      ["WindowsTerminal.exe"],
}


def close_app(app_name):
    raw_name = app_name.strip()

    close_all = False
    if raw_name.upper().startswith("ALL_"):
        close_all = True
        raw_name = raw_name[4:]

    clean_name = raw_name.lower().strip()

    # Resolve alias from config first
    clean_name = _resolve_alias(clean_name)

    _CREATE_NO_WINDOW = 0x08000000
    _flag = "/F" if close_all else ""

    # LIGHTNING FAST-PATH: Use process name map for instant kill
    # This correctly maps "camera" → "WindowsCamera.exe" etc.
    _target_processes = _PROCESS_NAME_MAP.get(clean_name, [])

    if _target_processes:
        for _proc_exe in _target_processes:
            try:
                _result = subprocess.call(
                    f"taskkill /IM {_proc_exe} {_flag}",
                    shell=True,
                    creationflags=_CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if _result == 0:
                    print(Fore.GREEN + f"   -> Lightning kill: {_proc_exe}")
                    command_log.log_command("CLOSE", clean_name, True, f"Lightning: {_proc_exe}")
                    mood_engine.on_command_result(True)
                    return True
            except Exception:
                continue
        # Map had entries but none matched — fall through to psutil scan
        print(Fore.YELLOW + f"   -> Process map miss for '{clean_name}', trying psutil scan...")
    else:
        # Not in map — try direct name match first (fast)
        _direct_exe = f"{clean_name}.exe"
        try:
            _result = subprocess.call(
                f"taskkill /IM {_direct_exe} {_flag}",
                shell=True,
                creationflags=_CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if _result == 0:
                print(Fore.GREEN + f"   -> Direct taskkill: {_direct_exe}")
                command_log.log_command("CLOSE", clean_name, True, f"Direct: {_direct_exe}")
                mood_engine.on_command_result(True)
                return True
        except Exception:
            pass

    print(Fore.CYAN + f"HANDS: Closing '{clean_name}'" + (" (ALL instances)" if close_all else "") + "...")

    # Check if this is a custom alias with a known process
    # Check in-memory registry first, then fall back to config path lookup
    process_names_to_try = _custom_alias_to_process.get(clean_name, [])

    # If not in memory registry, check config for the file path and infer process
    if not process_names_to_try:
        custom_paths = _get_custom_paths()
        if clean_name in custom_paths:
            file_path = custom_paths[clean_name]
            ext = os.path.splitext(file_path)[1].lower()
            process_names_to_try = _EXTENSION_PROCESS_MAP.get(ext, [])
            print(Fore.CYAN + f"   -> Inferred process list from extension {ext}: {process_names_to_try}")

    # If this is a known custom alias, only use alias-based close
    # Do not fall through to smart process closer — that causes double close
    _is_custom_alias = (
        clean_name in _custom_alias_to_process or
        clean_name in _get_custom_paths()
    )

    if process_names_to_try:
        # Flatten in case _register_custom_process stored a list-of-lists
        _flat = []
        for item in process_names_to_try:
            if isinstance(item, list):
                _flat.extend(item)
            else:
                _flat.append(item)
        process_names_to_try = _flat

        for proc_name in process_names_to_try:
            if not isinstance(proc_name, str):
                continue
            pn_lower = proc_name.lower().replace('.exe', '')
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    p_lower = proc.info['name'].lower()
                    if pn_lower in p_lower or p_lower.startswith(pn_lower):
                        proc.kill()
                        print(Fore.GREEN + f"   -> Closed {proc.info['name']} for '{clean_name}'")
                        command_log.log_command("CLOSE", clean_name, True, f"Via alias -> {proc.info['name']}")
                        mood_engine.on_command_result(True)
                        return True  # Hard return — never try next process name
                except Exception:
                    continue
            # This process name not running — try next in list
            continue
        # Nothing found running
        print(Fore.YELLOW + f"   -> No running process found for alias '{clean_name}'")
        if _is_custom_alias:
            # Try one more approach — scan all processes for video/image players
            _media_procs = ["vlc", "wmplayer", "movies", "groove",
                           "mspaint", "photos", "microsoft.photos"]
            custom_paths = _get_custom_paths()
            if clean_name in custom_paths:
                _file_ext = os.path.splitext(custom_paths[clean_name])[1].lower()
                _is_media = _file_ext in {
                    '.mp4', '.avi', '.mkv', '.mov', '.mp3',
                    '.jpg', '.jpeg', '.png', '.gif', '.bmp'
                }
                if _is_media:
                    for _proc in psutil.process_iter(['pid', 'name']):
                        try:
                            _pn = _proc.info['name'].lower().replace('.exe', '')
                            if any(_pn.startswith(mp) or mp in _pn
                                   for mp in _media_procs):
                                _proc.kill()
                                print(Fore.GREEN + f"   -> Closed media player: {_proc.info['name']}")
                                command_log.log_command("CLOSE", clean_name, True, "Media player kill")
                                mood_engine.on_command_result(True)
                                return True
                        except Exception:
                            continue
            command_log.log_command("CLOSE", clean_name, False, "Process not running")
            mood_engine.on_command_result(False)
            return False
        # Not a custom alias — fall through to special cases and smart closer

    # 1. SPECIAL CASE: ACTIVE WINDOW
    if clean_name in ["current", "this", "it", "active window"]:
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                # WM_CLOSE = 0x0010 — instant, no Alt+F4 keypress delay
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
                print(Fore.GREEN + f"   -> WM_CLOSE sent to hwnd: {hwnd}")
        except Exception:
            pyautogui.hotkey('alt', 'f4')  # fallback
        command_log.log_command("CLOSE", clean_name, True, "Active window WM_CLOSE")
        mood_engine.on_command_result(True)
        return True

    # 2. SPECIAL CASE: CONTROL PANEL
    if "control panel" in clean_name:
        print("   -> Closing Control Panel window...")
        subprocess.Popen('powershell -command "(New-Object -ComObject Shell.Application).Windows() | Where-Object { $_.LocationName -match \'Control Panel\' } | ForEach-Object { $_.quit() }"', shell=True)
        command_log.log_command("CLOSE", "control panel", True, "PowerShell COM")
        mood_engine.on_command_result(True)
        return True

    # 3. SPECIAL CASE: EXPLORER
    if "explorer" in clean_name or "file" in clean_name:
        if close_all:
            subprocess.Popen(['powershell', '-command', "(New-Object -ComObject Shell.Application).Windows() | foreach-object { $_.quit() }"])
            print(Fore.GREEN + "   -> Closed ALL Explorer windows")
            command_log.log_command("CLOSE", "explorer", True, "All windows closed")
        else:
            subprocess.Popen(['powershell', '-command', "(New-Object -ComObject Shell.Application).Windows() | Select-Object -Last 1 | foreach-object { $_.quit() }"])
            print(Fore.GREEN + "   -> Closed 1 Explorer window")
            command_log.log_command("CLOSE", "explorer", True, "1 window closed")
        mood_engine.on_command_result(True)
        return True

    # SPECIAL CASE: CALCULATOR
    if "calculator" in clean_name or "calc" in clean_name:
        subprocess.Popen("taskkill /im CalculatorApp.exe /f", shell=True)
        command_log.log_command("CLOSE", "calculator", True, "Force kill")
        mood_engine.on_command_result(True)
        return True

    # SPECIAL CASE: WHATSAPP
    # Windows Store WhatsApp runs under multiple possible process names
    if "whatsapp" in clean_name:
        killed = False
        for _wa_proc in psutil.process_iter(['pid', 'name']):
            try:
                _pname = _wa_proc.info['name'].lower()
                if 'whatsapp' in _pname:
                    _wa_proc.kill()
                    print(Fore.GREEN + f"   -> Killed WhatsApp process: {_wa_proc.info['name']}")
                    killed = True
            except Exception:
                continue
        if not killed:
            # Fallback: taskkill with common names
            for _wname in ["WhatsApp.exe", "whatsapp.exe", "WhatsAppDesktop.exe"]:
                subprocess.Popen(f"taskkill /im {_wname} /f", shell=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        command_log.log_command("CLOSE", "whatsapp", True, "Force kill")
        mood_engine.on_command_result(True)
        return True

    # SPECIAL CASE: CAMERA (UWP app — taskkill /IM does not work, need PID)
    if "camera" in clean_name:
        _cam_killed = False
        # Try psutil scan for UWP camera process
        _cam_names = ["windowscamera", "camera"]
        for _proc in psutil.process_iter(['pid', 'name']):
            try:
                _pn = _proc.info['name'].lower()
                if any(_cn in _pn for _cn in _cam_names):
                    _proc.kill()
                    print(Fore.GREEN + f"   -> Killed camera process: {_proc.info['name']}")
                    _cam_killed = True
            except Exception:
                continue
        if not _cam_killed:
            # UWP fallback via PowerShell
            subprocess.Popen(
                ['powershell', '-command',
                 'Get-Process | Where-Object {$_.Name -like "*camera*"} | Stop-Process -Force'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            _cam_killed = True
        command_log.log_command("CLOSE", "camera", _cam_killed, "UWP kill via psutil")
        mood_engine.on_command_result(_cam_killed)
        return _cam_killed

    # 5. TASK MANAGER
    if "task manager" in clean_name:
        subprocess.Popen("powershell -Command \"Start-Process taskkill -ArgumentList '/im Taskmgr.exe /f' -Verb RunAs\"", shell=True)
        command_log.log_command("CLOSE", "task manager", True, "Admin kill")
        mood_engine.on_command_result(True)
        return True

    # 6. BROWSERS
    browsers = ["chrome", "firefox", "edge", "brave", "opera"]
    is_browser = any(b in clean_name for b in browsers)
    
    if is_browser:
        if close_all:
            proc_names = {
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "edge": "msedge.exe",
                "brave": "brave.exe",
                "opera": "opera.exe",
            }
            for b, pname in proc_names.items():
                if b in clean_name:
                    subprocess.Popen(f"taskkill /im {pname} /f", shell=True)
                    print(Fore.GREEN + f"   -> Force killed ALL {pname}")
                    command_log.log_command("CLOSE", clean_name, True, f"All {pname} killed")
                    break
        else:
            import time
            try:
                subprocess.Popen(f'powershell -command "(New-Object -ComObject WScript.Shell).AppActivate(\'chrome\')"', shell=True)
                time.sleep(0.3)
                pyautogui.hotkey('alt', 'f4')
                print(Fore.GREEN + f"   -> Closed frontmost {clean_name} window")
                command_log.log_command("CLOSE", clean_name, True, "Alt+F4 frontmost window")
            except Exception as e:
                print(Fore.RED + f"   -> Failed: {e}")
                command_log.log_command("CLOSE", clean_name, False, str(e))
                mood_engine.on_command_result(False)
                return False
        mood_engine.on_command_result(True)
        return True

    # 7. SMART PROCESS CLOSER
    matching_procs = []
    for proc in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            p_name = proc.info['name'].lower()
            if clean_name in p_name:
                if any(safe in p_name for safe in SAFE_APPS):
                    continue
                matching_procs.append(proc)
                print(Fore.CYAN + f"   -> Found: {proc.info['name']} (PID: {proc.info['pid']})")
        except:
            pass
    
    if not matching_procs:
        print(Fore.RED + f"❌ HANDS: Could not find process for '{clean_name}'")
        command_log.log_command("CLOSE", clean_name, False, "Process not found")
        mood_engine.on_command_result(False)
        return False
    
    if close_all:
        for proc in matching_procs:
            try:
                proc.kill()
            except:
                pass
        print(Fore.GREEN + f"   -> Closed ALL {len(matching_procs)} instances of '{clean_name}'")
        command_log.log_command("CLOSE", clean_name, True, f"All {len(matching_procs)} terminated")
        mood_engine.on_command_result(True)
        return True
    else:
        try:
            matching_procs.sort(key=lambda p: p.info.get('create_time', 0), reverse=True)
            newest = matching_procs[0]
            newest.kill()
            remaining = len(matching_procs) - 1
            if remaining > 0:
                print(Fore.GREEN + f"   -> Closed 1 instance of '{clean_name}' ({remaining} still running)")
            else:
                print(Fore.GREEN + f"   -> Closed '{clean_name}'")
            command_log.log_command("CLOSE", clean_name, True, f"1 terminated, {remaining} remaining")
            mood_engine.on_command_result(True)
            return True
        except Exception as e:
            print(Fore.RED + f"❌ HANDS: Failed to close '{clean_name}': {e}")
            command_log.log_command("CLOSE", clean_name, False, str(e))
            mood_engine.on_command_result(False)
            return False
        
def _check_already_running(app_name):
    """
    Check if an app is already running.
    Returns the process name if found, None if not running.
    """
    search_terms = [app_name]
    aliases = _get_aliases()
    if app_name in aliases:
        search_terms.append(aliases[app_name])

    for proc in psutil.process_iter(['name']):
        try:
            pname = proc.info['name'].lower()
            for term in search_terms:
                if term in pname or pname.replace('.exe', '') in term:
                    return proc.info['name']
        except Exception:
            continue
    return None


def open_app(app_name):
    original_name = app_name.lower().strip()
    clean_name = original_name.replace("activated", "").replace("!", "").strip()

    # Check if already running before opening
    # Only for non-custom-path apps
    _already_running = _check_already_running(clean_name)

    # =====================================================================
    # THREE-TIER APP LAUNCH SYSTEM
    # Tier 1: Resolve alias from config → use resolved name
    # Tier 2: Try AppOpener (+ manual overrides for native apps)
    # Tier 3: Try custom .exe path from config
    # If all fail: log failure for dashboard "Fix" feature
    # =====================================================================

    # TIER 1: Resolve alias
    clean_name = _resolve_alias(clean_name)

    # URL SUPPORT — if target looks like a URL, open in browser
    import webbrowser as _wb
    if any(clean_name.startswith(p) for p in ['http://', 'https://']) or any(clean_name.endswith(d) for d in ['.com', '.org', '.net', '.io', '.dev', '.app', '.co']):
        url = clean_name if clean_name.startswith('http') else f'https://{clean_name}'
        _wb.open(url)
        command_log.log_command("OPEN", clean_name, True, f"URL: {url}")
        mood_engine.on_command_result(True)
        return True
    
    print(Fore.CYAN + f"🔧 HANDS: Opening '{clean_name}'...")

    try:
        # --- TIER 2: MANUAL OVERRIDES + APPOPENER ---
        
        # Windows native apps (manual overrides — these don't work with AppOpener)
        if "camera" in clean_name:
            # Direct registry launch — faster than explorer URI
            subprocess.Popen(
                'start microsoft.windows.camera:',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Give camera time to launch then bring to front
            import threading, time
            def _focus_camera():
                time.sleep(2.5)
                try:
                    import win32gui, win32con
                    def _cb(hwnd, _):
                        title = win32gui.GetWindowText(hwnd)
                        if "camera" in title.lower() and win32gui.IsWindowVisible(hwnd):
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                        return True
                    win32gui.EnumWindows(_cb, None)
                except Exception:
                    pass
            threading.Thread(target=_focus_camera, daemon=True).start()
            command_log.log_command("OPEN", "camera", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True
        
        if "control panel" in clean_name:
            subprocess.Popen("control", shell=True)
            command_log.log_command("OPEN", "control panel", True, "Direct command")
            mood_engine.on_command_result(True)
            return True
            
        if "settings" in clean_name:
            subprocess.Popen(
                ["explorer.exe", "ms-settings:"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            command_log.log_command("OPEN", "settings", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True
            
        if "calculator" in clean_name:
            subprocess.Popen(
                "calc",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
            command_log.log_command("OPEN", "calculator", True, "Direct command")
            mood_engine.on_command_result(True)
            return True
            
        if "notepad" in clean_name:
            os.startfile("notepad")
            command_log.log_command("OPEN", "notepad", True, "os.startfile")
            mood_engine.on_command_result(True)
            return True
            
        if any(x in clean_name for x in ["explorer", "file explorer", "files", "file manager"]):
            subprocess.Popen("explorer.exe", shell=False)
            command_log.log_command("OPEN", "explorer", True, "subprocess explorer")
            mood_engine.on_command_result(True)
            return True
            
        if "whatsapp" in clean_name:
            subprocess.Popen(
                ["explorer.exe", "whatsapp:"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            command_log.log_command("OPEN", "whatsapp", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        # TIER 1.5: Lightning fast PATH Check via OS Kernel (<10ms)
        if _fast_launch(clean_name):
            command_log.log_command("OPEN", clean_name, True, "FastLaunch")
            mood_engine.on_command_result(True)
            return True

        # Try custom paths FIRST — user-defined paths take priority over everything
        if _try_custom_path(clean_name):
            return True
        if original_name != clean_name and _try_custom_path(original_name):
            return True

        # Only try raw OS execution for names that look like executables
        # Prevents "work" from opening Word, "files" from opening Explorer, etc.
        if clean_name.endswith('.exe') or '\\' in clean_name or '/' in clean_name:
            try:
                os.startfile(clean_name)
                command_log.log_command("OPEN", clean_name, True, "OS Kernel Startfile")
                mood_engine.on_command_result(True)
                return True
            except Exception:
                pass
        # TIER 2: AppOpener — Wrapped in Background Thread for ZERO UI Blocking
        print(Fore.YELLOW + f"   -> Dispatched async AppOpener crawl for '{clean_name}'...")
        import threading
        def _async_appopener():
            try:
                app_opener(clean_name, match_closest=True, throw_error=True)
                command_log.log_command("OPEN", clean_name, True, "AppOpener Async")
                mood_engine.on_command_result(True)
            except Exception as appopener_error:
                print(Fore.YELLOW + f"   -> Async AppOpener failed: {appopener_error}")
                _log_failed_app(original_name, clean_name, str(appopener_error))

        threading.Thread(target=_async_appopener, daemon=True).start()
        # Return success instantly so Seven UI feels lightning fast
        command_log.log_command("OPEN", clean_name, True, "AppOpener Dispatched")
        mood_engine.on_command_result(True)
        return True
        
    except Exception as e:
        print(Fore.RED + f"❌ HANDS: Failed to open '{clean_name}'. Error: {e}")
        command_log.log_command("OPEN", clean_name, False, str(e))
        mood_engine.on_command_result(False)
        _log_failed_app(original_name, clean_name, str(e))
        return False


def search_web(query):
    print(f"🔧 HANDS: Searching Web for '{query}'...")
    webbrowser.open(f"https://www.google.com/search?q={query}")
    command_log.log_command("SEARCH", query, True, "Google search")
    return True


def system_control(command):
    cmd = command.lower()
    if "volume up" in cmd: pyautogui.press("volumeup", presses=5)
    elif "volume down" in cmd: pyautogui.press("volumedown", presses=5)
    elif "mute" in cmd: pyautogui.press("volumemute")
    elif "screenshot" in cmd:
        if not os.path.exists("screenshots"): os.makedirs("screenshots")
        pyautogui.screenshot(f"screenshots/snap_{datetime.datetime.now().strftime('%H%M%S')}.png")
    command_log.log_command("SYS", command, True, "System control")
    return True