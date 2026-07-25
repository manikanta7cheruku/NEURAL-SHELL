"""
hands/core.py
Public interface for app control.

This module is a thin re-export shim.
All implementation lives in:
  hands/app_launcher.py  - open_app and launch utilities
  hands/app_closer.py    - close_app and process utilities

Importing from hands.core continues to work identically.
No external file needs to change.
"""

from hands.app_launcher import open_app, _get_aliases, _get_custom_paths
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
    """Basic system media/volume/screenshot control."""
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