"""
hands/core.py
Public interface for app control and system functions.

This module acts as a re-export shim.
All implementations live in:
  hands/app_launcher.py  - open_app, focus_target_window, and launch utilities
  hands/app_closer.py    - close_app and process utilities

Importing from hands.core continues to work identically.
"""

from hands.app_launcher import open_app, focus_target_window
from hands.app_closer   import close_app
import webbrowser
import pyautogui
import datetime
import os


def search_web(query: str) -> bool:
    """Open a Google search in the default browser."""
    webbrowser.open(f"https://www.google.com/search?q={query}")
    return True


def system_control(command: str) -> bool:
    """Basic system media, volume, and screenshot control."""
    cmd = command.lower()
    if "volume up"   in cmd: pyautogui.press("volumeup",   presses=5)
    elif "volume down" in cmd: pyautogui.press("volumedown", presses=5)
    elif "mute"        in cmd: pyautogui.press("volumemute")
    elif "screenshot"  in cmd:
        os.makedirs("screenshots", exist_ok=True)
        pyautogui.screenshot(
            f"screenshots/snap_{datetime.datetime.now().strftime('%H%M%S')}.png"
        )
    return True