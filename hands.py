import os
import webbrowser
import pyautogui
import datetime
import psutil
from AppOpener import open as app_opener

# VERSION 1.5: HANDS (EXECUTION ENGINE)

def close_app(app_name):
    # 1. Handle "Close Current" (Alt+F4)
    if app_name == "CURRENT":
        print(f"🔧 HANDS: Closing active window (Alt+F4)...")
        pyautogui.hotkey('alt', 'f4')
        return True

    # 2. Handle Specific App Kill
    print(f"🔧 HANDS: Attempting to kill process -> {app_name}")
    
    # --- PROCESS MAPPING DICTIONARY ---
    # Left Side: What Brain sends (from User)
    # Right Side: What Windows Task Manager calls it
    process_mapping = {
        # Browsers
        "google chrome": "chrome",
        "chrome": "chrome",
        "firefox": "firefox",
        "edge": "msedge",
        "brave": "brave",
        
        # System Apps
        "file explorer": "explorer", # WARNING: This restarts the Taskbar
        "files": "explorer",
        "notepad": "notepad",
        "calculator": "calculator",
        "settings": "SystemSettings",
        "task manager": "Taskmgr",
        
        # Media / Chat
        "discord": "discord",
        "spotify": "spotify",
        "vlc": "vlc",
        
        # Camera (UWP Apps are tricky, adding common variants)
        "camera": "WindowsCamera",
        "windows camera": "WindowsCamera",
    }
    
    # Normalize input
    clean_name = app_name.lower().strip()
    
    # Get the system name (Default to the cleaned name if not in map)
    target_process = process_mapping.get(clean_name, clean_name)
    
    killed_any = False
    
    # SCAN PROCESSES
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Check if target is part of the process name
            # e.g. "chrome" is inside "chrome.exe"
            proc_name = proc.info['name'].lower()
            
            if target_process in proc_name:
                print(f"🔧 HANDS: Killing PID {proc.info['pid']} ({proc_name})")
                proc.kill()
                killed_any = True
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if killed_any:
        print(f"🔧 HANDS: Successfully closed {app_name}.")
        return True
    else:
        print(f"🔧 HANDS: Could not find process '{target_process}'. Falling back to Alt+F4...")
        # FALLBACK: If we can't find the specific background app,
        # we try Alt+F4. This handles cases where the user is looking AT the app
        # but we got the name wrong.
        pyautogui.hotkey('alt', 'f4')
        return False

def open_app(app_name):
    print(f"🔧 HANDS: Opening {app_name}...")
    try:
        # match_closest=True helps with typos
        app_opener(app_name, match_closest=True, throw_error=True)
        return True
    except:
        print(f"❌ HANDS: Failed to open {app_name}")
        return False

def search_web(query):
    print(f"🔧 HANDS: Searching {query}...")
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)
    return True

def system_control(command):
    print(f"🔧 HANDS: Received System Command -> {command}")
    
    command = command.lower()
    
    if "volume up" in command:
        pyautogui.press("volumeup", presses=5)
    elif "volume down" in command:
        pyautogui.press("volumedown", presses=5)
    elif "mute" in command:
        pyautogui.press("volumemute")
    elif "screenshot" in command:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")
        pyautogui.screenshot(f"screenshots/screenshot_{timestamp}.png")
    else:
        print(f"❌ HANDS: Invalid Command '{command}' ignored.")
        return False
        
    return True