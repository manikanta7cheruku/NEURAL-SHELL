"""
hands/app_launcher.py
App launching logic for Seven v2.

Launch priority:
  1. URL detection (http/https/domain)
  2. Special Windows apps (camera, settings, control panel, etc.)
  3. Fast launch table (common apps, hardcoded)
  4. App Discovery index (Start Menu + Registry + UWP + PATH + Desktop)
  5. Direct path/exe fallback
  6. AppOpener (last resort, async)

No aliases. No custom paths. Discovery is authoritative.

Public API:
  open_app(app_name) -> bool
"""

import os
import threading
import subprocess
import webbrowser
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine

_CREATE_NO_WINDOW = 0x08000000


# ── Fast launch table ─────────────────────────────────────────────────
# Instant launch for the most common apps. Bypasses discovery for speed.
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

# -- Special Windows folder shortcuts --
# "open downloads" / "open screenshots folder" etc. open the actual folder.
_SPECIAL_FOLDERS = {}

def _init_special_folders():
    """Build folder shortcuts from real user profile paths."""
    home = os.path.expanduser("~")
    mapping = {
        "downloads":       os.path.join(home, "Downloads"),
        "download":        os.path.join(home, "Downloads"),
        "documents":       os.path.join(home, "Documents"),
        "document":        os.path.join(home, "Documents"),
        "pictures":        os.path.join(home, "Pictures"),
        "picture":         os.path.join(home, "Pictures"),
        "photos":          os.path.join(home, "Pictures"),
        "videos":          os.path.join(home, "Videos"),
        "video":           os.path.join(home, "Videos"),
        "music":           os.path.join(home, "Music"),
        "desktop":         os.path.join(home, "Desktop"),
        "screenshots":     os.path.join(home, "Pictures", "Screenshots"),
        "screenshot":      os.path.join(home, "Pictures", "Screenshots"),
        "recordings":      os.path.join(home, "Videos", "Recordings"),
        "captures":        os.path.join(home, "Videos", "Captures"),
        "onedrive":        os.path.join(home, "OneDrive"),
        "recent":          "shell:recent",
        "startup":         "shell:startup",
        "appdata":         os.path.join(home, "AppData"),
        "local appdata":   os.path.join(home, "AppData", "Local"),
        "roaming":         os.path.join(home, "AppData", "Roaming"),
        "temp":            os.path.join(home, "AppData", "Local", "Temp"),
    }
    for key, path in mapping.items():
        if path.startswith("shell:"):
            _SPECIAL_FOLDERS[key] = path
        elif os.path.exists(path):
            _SPECIAL_FOLDERS[key] = path

_init_special_folders()

# Extension to default player mapping (used by app_closer.py)
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
# Backward compatibility stubs (safe no-op returns for legacy callers)
def _get_aliases():
    return {}

def _get_custom_paths():
    return {}

def _resolve_alias(app_name: str) -> str:
    return app_name.lower().strip()

_custom_alias_to_process = {}


def _fast_launch(app_name: str) -> bool:
    """Try fast launch table. Returns True if launched."""
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
                subprocess.Popen(target, creationflags=_CREATE_NO_WINDOW)
        print(Fore.GREEN + f"   -> Fast launch: {target}")
        return True
    except Exception as e:
        print(Fore.YELLOW + f"   -> Fast launch failed: {e}")
        return False


def _launch_via_discovery(app_name: str) -> bool:
    """Query app_discovery index and launch the best match."""
    try:
        from hands.app_discovery import search_apps
        hits = search_apps(app_name, limit=3)
        if not hits:
            return False

        best = hits[0]
        launch_cmd = best["launch"]
        display = best["name"]

        print(Fore.CYAN + f"   -> Discovery match: '{display}' ({best['source']})")

        if launch_cmd.startswith("explorer.exe shell:AppsFolder"):
            subprocess.Popen(launch_cmd, shell=True, creationflags=_CREATE_NO_WINDOW)
        elif launch_cmd.endswith(".lnk"):
            os.startfile(launch_cmd)
        else:
            subprocess.Popen(launch_cmd, shell=True, creationflags=_CREATE_NO_WINDOW)

        print(Fore.GREEN + f"   -> Launched via discovery: {display}")
        return True

    except Exception as e:
        print(Fore.YELLOW + f"   -> Discovery launch failed: {e}")
        return False


def open_app(app_name: str) -> bool:
    """
    Launch an application by name.

    Priority:
      1. URL detection
      2. Special Windows apps (camera, settings, etc.)
      3. Fast launch table
      4. App Discovery index (universal)
      5. Direct path/exe
      6. AppOpener (last resort, async)

    Returns True if launch was initiated.
    """
    original = app_name.lower().strip()
    clean = original.replace("activated", "").replace("!", "").strip()

    # ── 1. URL detection ────────────────────────────────────────
    if (any(clean.startswith(p) for p in ['http://', 'https://'])
            or any(clean.endswith(d) for d in
                   ['.com', '.org', '.net', '.io', '.dev', '.app', '.co'])):
        url = clean if clean.startswith('http') else f'https://{clean}'
        webbrowser.open(url)
        command_log.log_command("OPEN", clean, True, f"URL: {url}")
        mood_engine.on_command_result(True)
        return True

    # ── 1b. Drive open (e.g. "open disk M", "open drive D") ─────
    import re
    drive_match = re.match(r'^(?:disk|drive)\s+([a-z])$', clean)
    if drive_match:
        drive_letter = drive_match.group(1).upper()
        drive_path = f"{drive_letter}:\\"
        if os.path.exists(drive_path):
            subprocess.Popen(f'explorer "{drive_path}"', shell=True)
            command_log.log_command("OPEN", clean, True, f"Drive: {drive_path}")
            mood_engine.on_command_result(True)
            return True

    # ── 1c. Special folder shortcuts ────────────────────────────
    _folder_clean = clean.replace(" folder", "").replace(" directory", "").strip()
    if _folder_clean in _SPECIAL_FOLDERS:
        _fpath = _SPECIAL_FOLDERS[_folder_clean]
        try:
            if _fpath.startswith("shell:"):
                subprocess.Popen(f'explorer {_fpath}', shell=True)
            else:
                subprocess.Popen(f'explorer "{_fpath}"', shell=True)
            command_log.log_command("OPEN", clean, True, f"Folder: {_fpath}")
            mood_engine.on_command_result(True)
            print(Fore.GREEN + f"   -> Opened folder: {_fpath}")
            return True
        except Exception as e:
            print(Fore.YELLOW + f"   -> Folder open failed: {e}")
    print(Fore.CYAN + f"HANDS: Opening '{clean}'...")

    try:
        # ── 2. Special Windows apps ─────────────────────────────
        if "camera" in clean:
            subprocess.Popen(
                'start microsoft.windows.camera:',
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            def _focus_camera():
                import time
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

        if "control panel" in clean:
            subprocess.Popen("control", shell=True)
            command_log.log_command("OPEN", "control panel", True, "Direct")
            mood_engine.on_command_result(True)
            return True

        if "settings" in clean:
            subprocess.Popen(
                ["explorer.exe", "ms-settings:"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            command_log.log_command("OPEN", "settings", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        if "calculator" in clean:
            subprocess.Popen("calc", shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            command_log.log_command("OPEN", "calculator", True, "Direct")
            mood_engine.on_command_result(True)
            return True

        if "notepad" in clean:
            os.startfile("notepad")
            command_log.log_command("OPEN", "notepad", True, "os.startfile")
            mood_engine.on_command_result(True)
            return True

        if any(x in clean for x in ["explorer", "file explorer", "file manager"]):
            subprocess.Popen("explorer.exe", shell=False)
            command_log.log_command("OPEN", "explorer", True, "subprocess")
            mood_engine.on_command_result(True)
            return True

        if "whatsapp" in clean:
            subprocess.Popen(
                ["explorer.exe", "whatsapp:"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            command_log.log_command("OPEN", "whatsapp", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        # ── 3. Fast launch table ────────────────────────────────
        if _fast_launch(clean):
            command_log.log_command("OPEN", clean, True, "FastLaunch")
            mood_engine.on_command_result(True)
            return True

        # ── 4. App Discovery index ──────────────────────────────
        if _launch_via_discovery(clean):
            command_log.log_command("OPEN", clean, True, "Discovery")
            mood_engine.on_command_result(True)
            return True

        # ── 5. Direct path/exe ──────────────────────────────────
        if clean.endswith('.exe') or '\\' in clean or '/' in clean:
            try:
                os.startfile(clean)
                command_log.log_command("OPEN", clean, True, "Direct path")
                mood_engine.on_command_result(True)
                return True
            except Exception:
                pass

        # ── 6. AppOpener (last resort, async) ───────────────────
        print(Fore.YELLOW + f"   -> Falling back to AppOpener for '{clean}'...")
        appopener_worked = threading.Event()
        try:
            from AppOpener import open as app_opener

            def _async_appopener():
                try:
                    app_opener(clean, match_closest=True, throw_error=True)
                    command_log.log_command("OPEN", clean, True, "AppOpener")
                    mood_engine.on_command_result(True)
                    appopener_worked.set()
                except Exception as err:
                    print(Fore.YELLOW + f"   -> AppOpener failed: {err}")

            t = threading.Thread(target=_async_appopener, daemon=True)
            t.start()
            t.join(timeout=3.0)

            if appopener_worked.is_set():
                return True
        except ImportError:
            pass

        # ── 7. Web fallback for known services ──────────────────
        WEB_SERVICES = {
            "github": "https://github.com",
            "youtube": "https://youtube.com",
            "gmail": "https://mail.google.com",
            "google": "https://google.com",
            "twitter": "https://twitter.com",
            "x": "https://x.com",
            "linkedin": "https://linkedin.com",
            "reddit": "https://reddit.com",
            "facebook": "https://facebook.com",
            "instagram": "https://instagram.com",
            "netflix": "https://netflix.com",
            "amazon": "https://amazon.com",
            "twitch": "https://twitch.tv",
            "stackoverflow": "https://stackoverflow.com",
            "chatgpt": "https://chat.openai.com",
            "claude": "https://claude.ai",
            "notion": "https://notion.so",
            "wikipedia": "https://en.wikipedia.org",
            "spotify": "https://open.spotify.com",
            "discord": "https://discord.com",
            "telegram": "https://web.telegram.org",
            "whatsapp": "https://web.whatsapp.com",
            "zoom": "https://zoom.us",
            "slack": "https://slack.com",
            "figma": "https://figma.com",
            "canva": "https://canva.com",
            "drive": "https://drive.google.com",
            "maps": "https://maps.google.com",
            "calendar": "https://calendar.google.com",
        }
        if clean in WEB_SERVICES:
            webbrowser.open(WEB_SERVICES[clean])
            command_log.log_command("OPEN", clean, True, f"Web: {WEB_SERVICES[clean]}")
            mood_engine.on_command_result(True)
            return True

        # ── 8. Universal URL fallback ───────────────────────────
        # If nothing else worked and the name looks like a domain,
        # try opening it as a website. Handles "open wikipedia",
        # "open canva", "open figma", any single-word service.
        if ' ' not in clean and len(clean) >= 3 and clean.isalnum():
            _guess_url = f"https://{clean}.com"
            print(Fore.CYAN + f"   -> Trying universal URL: {_guess_url}")
            webbrowser.open(_guess_url)
            command_log.log_command("OPEN", clean, True, f"Universal URL: {_guess_url}")
            mood_engine.on_command_result(True)
            return True

        print(Fore.RED + f"   -> Cannot find '{clean}' anywhere.")
        command_log.log_command("OPEN", clean, False, "Not found in any source")
        mood_engine.on_command_result(False)
        return False

    except Exception as e:
        print(Fore.RED + f"HANDS: Failed to open '{clean}': {e}")
        command_log.log_command("OPEN", clean, False, str(e))
        mood_engine.on_command_result(False)
        return False