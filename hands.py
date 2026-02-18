"""
=============================================================================
PROJECT SEVEN - hands.py (The Executioner)
Version: 1.1.1 (+ Command Logging + Mood Feedback)

CHANGES FROM V1.5:
    1. NEW: Every command logged via command_log
    2. NEW: Mood engine notified of success/failure
    3. KEPT: All existing app open/close logic unchanged
=============================================================================
"""

import os
import webbrowser
import pyautogui
import datetime
import psutil
from AppOpener import open as app_opener
import subprocess
from colorama import Fore
from memory.command_log import command_log
from memory.mood import mood_engine

# PROTECTED SYSTEM APPS
# Prevents accidentally killing the OS
SAFE_APPS = ["system", "registry", "service", "nvidia", "antivirus", "explorer"]

# APP ALIASES — common names mapped to actual app names
APP_ALIASES = {
    "browser": "chrome",
    "web browser": "chrome",
    "internet": "chrome",
    "files": "explorer",
    "file manager": "explorer",
    "my computer": "explorer",
    "this pc": "explorer",
    "terminal": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "music": "spotify",
    "player": "spotify",
    "mail": "outlook",
    "email": "outlook",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "paint": "mspaint",
    "snip": "snippingtool",
    "screenshot tool": "snippingtool",
    "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:",
    "clock": "ms-clock:",
    "alarm": "ms-clock:",
    "maps": "bingmaps:",
    "photos": "ms-photos:",
    "recorder": "soundrecorder:",
    "voice recorder": "soundrecorder:",
}

def close_app(app_name):
    raw_name = app_name.strip()
    
    # V1.5: Check for ALL_ prefix
    close_all = False
    if raw_name.upper().startswith("ALL_"):
        close_all = True
        raw_name = raw_name[4:]
    
    clean_name = raw_name.lower().strip()
    print(Fore.CYAN + f"🔧 HANDS: Closing '{clean_name}'" + (" (ALL instances)" if close_all else "") + "...")

    # V1.5: Resolve aliases
    if clean_name in APP_ALIASES:
        resolved = APP_ALIASES[clean_name]
        print(Fore.CYAN + f"   -> Alias '{clean_name}' → '{resolved}'")
        clean_name = resolved

    # 1. SPECIAL CASE: ACTIVE WINDOW
    if clean_name in ["current", "this", "it", "active window"]:
        pyautogui.hotkey('alt', 'f4')
        command_log.log_command("CLOSE", clean_name, True, "Active window (Alt+F4)")
        mood_engine.on_command_result(True)
        return True

    # 2. SPECIAL CASE: CONTROL PANEL
    # Must use Title matching so we don't close File Explorer by mistake
    if "control panel" in clean_name:
        print("   -> Closing Control Panel window...")
        subprocess.Popen('powershell -command "(New-Object -ComObject Shell.Application).Windows() | Where-Object { $_.LocationName -match \'Control Panel\' } | ForEach-Object { $_.quit() }"', shell=True)
        command_log.log_command("CLOSE", "control panel", True, "PowerShell COM")
        mood_engine.on_command_result(True)
        return True

    # 3. SPECIAL CASE: EXPLORER (Generic Folders)
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

    # 4. SPECIAL CASE: CAMERA (Force Kill)
    if "camera" in clean_name:
        subprocess.Popen("taskkill /im WindowsCamera.exe /f", shell=True)
        command_log.log_command("CLOSE", "camera", True, "Force kill")
        mood_engine.on_command_result(True)
        return True
    
     # 5. TASK MANAGER FIX (needs admin rights)
    if "task manager" in clean_name:
        subprocess.Popen("powershell -Command \"Start-Process taskkill -ArgumentList '/im Taskmgr.exe /f' -Verb RunAs\"", shell=True)
        command_log.log_command("CLOSE", "task manager", True, "Admin kill")
        mood_engine.on_command_result(True)
        return True
    
    # 6. SPECIAL CASE: BROWSERS (Chrome, Firefox, Edge)
    browsers = ["chrome", "firefox", "edge", "brave", "opera"]
    
    is_browser = any(b in clean_name for b in browsers)
    
    if is_browser:
        if close_all:
            # Find the actual process name
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
            # Close just the current/frontmost window using Alt+F4
            # First bring the browser to focus, then close it
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

    # 6. SMART PROCESS CLOSER
    # Finds matching processes. Closes only ONE instance (most recent).
    # User says "close all chrome" → closes all. Otherwise just one.

    
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
        # Kill all instances
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
        # Kill only the MOST RECENT instance (highest create_time)
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
    clean_name = app_name.lower().strip()
    # Remove AI junk words
    clean_name = clean_name.replace("activated", "").replace("!", "").strip()

    # V1.5: Resolve aliases
    if clean_name in APP_ALIASES:
        resolved = APP_ALIASES[clean_name]
        print(Fore.CYAN + f"   -> Alias '{clean_name}' → '{resolved}'")
        clean_name = resolved
    
    print(Fore.CYAN + f"🔧 HANDS: Opening '{clean_name}'...")

    try:
        # --- 1. WINDOWS NATIVE APPS (Manual Override) ---
        # These apps are hidden from the standard registry, so we force them.
        
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

        # --- 2. UNIVERSAL APP OPENER (The Fallback) ---
        # This searches for Firefox, Chrome, Games, Spotify, etc.
        app_opener(clean_name, match_closest=True, throw_error=True)
        command_log.log_command("OPEN", clean_name, True, "AppOpener")
        mood_engine.on_command_result(True)
        return True
        
    except Exception as e:
        print(Fore.RED + f"❌ HANDS: Failed to open '{clean_name}'. Error: {e}")
        command_log.log_command("OPEN", clean_name, False, str(e))
        mood_engine.on_command_result(False)
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