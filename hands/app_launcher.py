"""
hands/app_launcher.py
App launching logic for Seven.

Three-tier launch system:
  Tier 1: Alias resolution from config
  Tier 2: Fast launch table, manual overrides, AppOpener
  Tier 3: Custom exe paths from config

Public API:
  open_app(app_name) -> bool
"""

import os
import threading
import subprocess
import datetime
import psutil
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine
import config


# ── Fast launch table ─────────────────────────────────────────────────────
# Bypasses AppOpener for common apps. Key: lowercase name, Value: (type, target)

_FAST_LAUNCH = {
    "chrome":       ("exe", "chrome"),
    "firefox":      ("exe", "firefox"),
    "edge":         ("uri", "microsoft-edge:"),
    "notepad":      ("exe", "notepad"),
    "notepad++":    ("exe", "notepad++"),
    "vlc":          ("exe", "vlc"),
    "spotify":      ("uri", "spotify:"),
    "telegram":     ("exe", "telegram"),
    "discord":      ("exe", "discord"),
    "steam":        ("exe", "steam"),
    "vs code":      ("exe", "code"),
    "vscode":       ("exe", "code"),
    "code":         ("exe", "code"),
    "word":         ("exe", "winword"),
    "excel":        ("exe", "excel"),
    "powerpoint":   ("exe", "powerpnt"),
    "paint":        ("exe", "mspaint"),
    "cmd":          ("exe", "cmd"),
    "terminal":     ("exe", "wt"),
    "powershell":   ("exe", "powershell"),
    "task manager": ("exe", "taskmgr"),
    "obs":          ("exe", "obs64"),
    "zoom":         ("exe", "zoom"),
    "teams":        ("uri", "msteams:"),
    "outlook":      ("exe", "outlook"),
    "file manager": ("exe", "explorer"),
    "files":        ("exe", "explorer"),
}

# Extension to default player mapping
# Used when a custom alias opens a media/document file
_EXTENSION_PROCESS_MAP = {
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
}

# Runtime registry: alias -> process name that opened it
# Persisted to config so close_app can find the right process later
_custom_alias_to_process = {}


def _load_process_registry():
    saved = config.KEY.get("commands", {}).get("alias_process_map", {})
    for alias, procs in saved.items():
        _custom_alias_to_process[alias] = procs if isinstance(procs, list) else [procs]
    if saved:
        print(Fore.CYAN + f"   -> Loaded {len(saved)} alias->process mappings from config")


_load_process_registry()


def _get_aliases():
    return config.KEY.get("commands", {}).get("app_aliases", {})


def _get_custom_paths():
    return config.KEY.get("commands", {}).get("app_paths", {})


def _resolve_alias(app_name: str) -> str:
    aliases = _get_aliases()
    clean = app_name.lower().strip()
    if clean in aliases:
        resolved = aliases[clean]
        print(Fore.CYAN + f"   -> Alias '{clean}' -> '{resolved}'")
        return resolved
    return clean


def _register_custom_process(alias: str, file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _EXTENSION_PROCESS_MAP:
        _custom_alias_to_process[alias] = _EXTENSION_PROCESS_MAP[ext]
        print(Fore.CYAN + f"   -> Registered {alias} -> {_EXTENSION_PROCESS_MAP[ext]}")


def _fast_launch(app_name: str) -> bool:
    clean = app_name.lower().strip()
    entry = _FAST_LAUNCH.get(clean)
    if not entry:
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
            try:
                os.startfile(target)
            except FileNotFoundError:
                subprocess.Popen(target, creationflags=0x08000000)
        print(Fore.GREEN + f"   -> Fast launch: {target}")
        return True
    except Exception as e:
        print(Fore.YELLOW + f"   -> Fast launch failed: {e}")
        return False


def _try_custom_path(app_name: str) -> bool:
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
        _before_launch = {p.pid for p in psutil.process_iter(['pid'])}

        if ext == '.exe':
            subprocess.Popen([exe_path])
        elif os.path.isdir(exe_path):
            subprocess.Popen(f'explorer "{exe_path}"', shell=True)
        elif ext in {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.heic', '.webp', '.raw'}:
            os.startfile(os.path.abspath(exe_path))
        else:
            os.startfile(exe_path)

        def _focus_new_window(before_pids_snap):
            import time
            import ctypes
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.wintypes.BOOL,
                ctypes.wintypes.HWND,
                ctypes.wintypes.LPARAM,
            )
            def _try_focus():
                new_pids = {p.pid for p in psutil.process_iter(['pid'])
                            if p.pid not in before_pids_snap}
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
                        if user32.GetWindowTextLengthW(hwnd) < 1:
                            return True
                        found[0] = hwnd
                        return False
                    except Exception:
                        return True
                user32.EnumWindows(WNDENUMPROC(_cb), 0)
                if found[0]:
                    user32.ShowWindow(found[0], 9)
                    user32.SetForegroundWindow(found[0])
                    user32.BringWindowToTop(found[0])
                    return True
                return False
            for _ in range(12):
                time.sleep(1.0)
                try:
                    if _try_focus():
                        return
                except Exception:
                    pass

        threading.Thread(
            target=_focus_new_window,
            args=(_before_launch,),
            daemon=True
        ).start()

        print(Fore.GREEN + f"   -> Launched via custom path: {exe_path}")
        command_log.log_command("OPEN", clean, True, f"Custom path: {exe_path}")
        mood_engine.on_command_result(True)

        def _watch_new_process(alias, path, before_pids):
            import time
            time.sleep(3.0)
            _system_procs = {
                'svchost.exe', 'conhost.exe', 'RuntimeBroker.exe',
                'SearchIndexer.exe', 'WmiPrvSE.exe', 'dllhost.exe',
                'backgroundTaskHost.exe', 'sihost.exe', 'taskhostw.exe',
                'ApplicationFrameHost.exe', 'ShellExperienceHost.exe',
            }
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if p.pid not in before_pids:
                        pname = p.info['name']
                        if pname in _system_procs:
                            continue
                        if not pname.lower().endswith('.exe'):
                            continue
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


def _log_failed_app(user_phrase: str, attempted_name: str, error_detail: str):
    failed_list = config.KEY.get("commands", {}).get("failed_apps", [])
    failed_list.append({
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "phrase":    user_phrase,
        "attempted": attempted_name,
        "error":     error_detail,
    })
    if len(failed_list) > 50:
        failed_list = failed_list[-50:]
    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    config.KEY["commands"]["failed_apps"] = failed_list
    config.save_config()


def _check_already_running(app_name: str):
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


def open_app(app_name: str) -> bool:
    """
    Launch an application by name.

    Three-tier system:
      1. Alias resolution + fast launch table
      2. Windows native app overrides + AppOpener
      3. Custom exe paths from config

    Returns True if launch was initiated, False if all tiers failed.
    Non-blocking for AppOpener tier — returns True immediately and
    launches in background thread.
    """
    original_name = app_name.lower().strip()
    clean_name = original_name.replace("activated", "").replace("!", "").strip()

    clean_name = _resolve_alias(clean_name)

    import webbrowser as _wb
    if (any(clean_name.startswith(p) for p in ['http://', 'https://'])
            or any(clean_name.endswith(d) for d in
                   ['.com', '.org', '.net', '.io', '.dev', '.app', '.co'])):
        url = clean_name if clean_name.startswith('http') else f'https://{clean_name}'
        _wb.open(url)
        command_log.log_command("OPEN", clean_name, True, f"URL: {url}")
        mood_engine.on_command_result(True)
        return True

    print(Fore.CYAN + f"HANDS: Opening '{clean_name}'...")

    try:
        if "camera" in clean_name:
            subprocess.Popen(
                'start microsoft.windows.camera:',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            import time
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
                stderr=subprocess.DEVNULL,
            )
            command_log.log_command("OPEN", "settings", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        if "calculator" in clean_name:
            subprocess.Popen(
                "calc", shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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
                stderr=subprocess.DEVNULL,
            )
            command_log.log_command("OPEN", "whatsapp", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        if _fast_launch(clean_name):
            command_log.log_command("OPEN", clean_name, True, "FastLaunch")
            mood_engine.on_command_result(True)
            return True

        if _try_custom_path(clean_name):
            return True
        if original_name != clean_name and _try_custom_path(original_name):
            return True

        if clean_name.endswith('.exe') or '\\' in clean_name or '/' in clean_name:
            try:
                os.startfile(clean_name)
                command_log.log_command("OPEN", clean_name, True, "OS Kernel Startfile")
                mood_engine.on_command_result(True)
                return True
            except Exception:
                pass

        print(Fore.YELLOW + f"   -> Dispatched async AppOpener for '{clean_name}'...")
        from AppOpener import open as app_opener

        def _async_appopener():
            try:
                app_opener(clean_name, match_closest=True, throw_error=True)
                command_log.log_command("OPEN", clean_name, True, "AppOpener Async")
                mood_engine.on_command_result(True)
            except Exception as err:
                print(Fore.YELLOW + f"   -> Async AppOpener failed: {err}")
                _log_failed_app(original_name, clean_name, str(err))

        threading.Thread(target=_async_appopener, daemon=True).start()
        command_log.log_command("OPEN", clean_name, True, "AppOpener Dispatched")
        mood_engine.on_command_result(True)
        return True

    except Exception as e:
        print(Fore.RED + f"HANDS: Failed to open '{clean_name}': {e}")
        command_log.log_command("OPEN", clean_name, False, str(e))
        mood_engine.on_command_result(False)
        _log_failed_app(original_name, clean_name, str(e))
        return False