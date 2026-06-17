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
    ".jpg": ["Photos", "Microsoft.Photos", "mspaint", "gimp"],
    ".jpeg": ["Photos", "Microsoft.Photos", "mspaint"],
    ".png": ["Photos", "Microsoft.Photos", "mspaint", "gimp"],
    ".gif": ["Photos", "Microsoft.Photos"],
    ".bmp": ["Photos", "Microsoft.Photos", "mspaint"],
    ".mp4": ["vlc", "wmplayer", "Movies", "Microsoft.Media.Player"],
    ".mp3": ["vlc", "wmplayer", "Groove", "Music"],
    ".pdf": ["AcroRd32", "Acrobat", "FoxitReader", "edge", "chrome"],
    ".docx": ["WINWORD"],
    ".xlsx": ["EXCEL"],
    ".pptx": ["POWERPNT"],
}

_custom_alias_to_process = {}


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

        if ext == '.exe':
            subprocess.Popen([exe_path], shell=False)
        else:
            os.startfile(exe_path)

        # No alt+tab needed - os.startfile handles focus
        # alt+tab was CAUSING the minimize by switching away

        print(Fore.GREEN + f"   -> Launched via custom path: {exe_path}")
        command_log.log_command("OPEN", clean, True, f"Custom path: {exe_path}")
        mood_engine.on_command_result(True)

        # Register which process this custom name maps to
        # So "close pic" knows to look for the Photos app process
        _register_custom_process(clean, exe_path)
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


def close_app(app_name):
    raw_name = app_name.strip()

    close_all = False
    if raw_name.upper().startswith("ALL_"):
        close_all = True
        raw_name = raw_name[4:]

    clean_name = raw_name.lower().strip()
    print(Fore.CYAN + f"HANDS: Closing '{clean_name}'" + (" (ALL instances)" if close_all else "") + "...")

    # Resolve aliases from config
    clean_name = _resolve_alias(clean_name)

    # Check if this is a custom alias with a known process
    if clean_name in _custom_alias_to_process:
        process_names = _custom_alias_to_process[clean_name]
        for proc_name in process_names:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc_name.lower() in proc.info['name'].lower():
                        proc.terminate()
                        print(Fore.GREEN + f"   -> Closed {proc.info['name']} for alias '{clean_name}'")
                        command_log.log_command("CLOSE", clean_name, True, f"Via alias -> {proc.info['name']}")
                        mood_engine.on_command_result(True)
                        return True
                except Exception:
                    continue
        print(Fore.YELLOW + f"   -> No running process found for alias '{clean_name}'")

    # 1. SPECIAL CASE: ACTIVE WINDOW
    if clean_name in ["current", "this", "it", "active window"]:
        pyautogui.hotkey('alt', 'f4')
        command_log.log_command("CLOSE", clean_name, True, "Active window (Alt+F4)")
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

    # 4. SPECIAL CASE: CAMERA
    if "camera" in clean_name:
        subprocess.Popen("taskkill /im WindowsCamera.exe /f", shell=True)
        command_log.log_command("CLOSE", "camera", True, "Force kill")
        mood_engine.on_command_result(True)
        return True

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
                proc.terminate()
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
            newest.terminate()
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


def open_app(app_name):
    original_name = app_name.lower().strip()
    clean_name = original_name.replace("activated", "").replace("!", "").strip()

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
            os.system("start microsoft.windows.camera:")
            command_log.log_command("OPEN", "camera", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True
        
        if "control panel" in clean_name:
            os.system("control")
            command_log.log_command("OPEN", "control panel", True, "Direct command")
            mood_engine.on_command_result(True)
            return True
            
        if "settings" in clean_name:
            os.system("start ms-settings:")
            command_log.log_command("OPEN", "settings", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True
            
        if "calculator" in clean_name:
            os.system("calc")
            command_log.log_command("OPEN", "calculator", True, "Direct command")
            mood_engine.on_command_result(True)
            return True
            
        if "notepad" in clean_name:
            os.startfile("notepad")
            command_log.log_command("OPEN", "notepad", True, "os.startfile")
            mood_engine.on_command_result(True)
            return True
            
        if "explorer" in clean_name:
            os.startfile("explorer")
            command_log.log_command("OPEN", "explorer", True, "os.startfile")
            mood_engine.on_command_result(True)
            return True
            
        if "whatsapp" in clean_name:
            os.system("start whatsapp:")
            command_log.log_command("OPEN", "whatsapp", True, "Windows URI")
            mood_engine.on_command_result(True)
            return True

        # AppOpener — universal fallback
        try:
            app_opener(clean_name, match_closest=True, throw_error=True)
            command_log.log_command("OPEN", clean_name, True, "AppOpener")
            mood_engine.on_command_result(True)
            return True
        except Exception as appopener_error:
            print(Fore.YELLOW + f"   -> AppOpener failed: {appopener_error}")
            
            # --- TIER 3: CUSTOM .EXE PATH ---
            if _try_custom_path(clean_name):
                return True
            
            # Also try the original name (before alias resolution)
            if original_name != clean_name and _try_custom_path(original_name):
                return True
            
            # ALL TIERS FAILED
            error_msg = str(appopener_error)
            print(Fore.RED + f"❌ HANDS: All launch methods failed for '{clean_name}'")
            command_log.log_command("OPEN", clean_name, False, error_msg)
            mood_engine.on_command_result(False)
            
            # Log failure for dashboard "Fix" feature
            _log_failed_app(original_name, clean_name, error_msg)
            
            return False
        
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