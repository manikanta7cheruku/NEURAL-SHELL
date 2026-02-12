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

def close_app(app_name):
    clean_name = app_name.lower().strip()
    print(Fore.CYAN + f"🔧 HANDS: Closing '{clean_name}'...")

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
        subprocess.Popen(['powershell', '-command', "(New-Object -ComObject Shell.Application).Windows() | foreach-object { $_.quit() }"])
        command_log.log_command("CLOSE", "explorer", True, "PowerShell COM")
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

    # 6. UNIVERSAL PROCESS KILLER
    # Scans all running processes to find a match
    killed = False
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            p_name = proc.info['name'].lower()
            if clean_name in p_name:
                if any(safe in p_name for safe in SAFE_APPS): continue
                proc.terminate()
                killed = True
        except: pass
    
    if killed:
        command_log.log_command("CLOSE", clean_name, True, "Process terminated")
        mood_engine.on_command_result(True)
    else:
        print(Fore.RED + f"❌ HANDS: Could not find process for '{clean_name}'")
        command_log.log_command("CLOSE", clean_name, False, "Process not found")
        mood_engine.on_command_result(False)
        
    return killed

def open_app(app_name):
    clean_name = app_name.lower().strip()
    # Remove AI junk words
    clean_name = clean_name.replace("activated", "").replace("!", "").strip()
    
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