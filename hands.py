import os
import webbrowser
import pyautogui
import datetime
import psutil
from AppOpener import open as app_opener


# Replace the old close_app function with this SAFER version
def close_app(app_name):
    print(f"🔧 HANDS: Closing active window (Safety Mode)...")
    # We ignore 'app_name' for now and just close whatever is in front of you.
    # This prevents accidentally killing background processes like your 2nd Chrome profile.
    pyautogui.hotkey('alt', 'f4')
    return True

def open_app(app_name):
    print(f"🔧 HANDS: Opening {app_name}...")
    try:
        app_opener(app_name, match_closest=True, throw_error=True)
        return True
    except:
        return False

def search_web(query):
    print(f"🔧 HANDS: Searching {query}...")
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)
    return True

def system_control(command):
    print(f"🔧 HANDS: Received System Command -> {command}")
    
    command = command.lower()
    
    # STRICT WHITELIST
    if "volume up" in command:
        pyautogui.press("volumeup", presses=5)
    elif "volume down" in command:
        pyautogui.press("volumedown", presses=5)
    elif "mute" in command:
        pyautogui.press("volumemute")
    elif "screenshot" in command:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pyautogui.screenshot(f"screenshot_{timestamp}.png")
    else:
        # If the brain sent garbage, we catch it here.
        print(f"❌ HANDS: Invalid Command '{command}' ignored.")
        return False
        
    return True