"""
hands/chrome_setup.py

Chrome Tab Sync extension setup for Seven.

HONEST APPROACH:
  Chrome blocks all silent extension installation since v73 (2019).
  No registry trick, Group Policy, or API can install extensions
  without user interaction on consumer Chrome.

  Our approach: Guide the user through a 30-second setup.
  Seven handles everything except the 4 clicks Chrome requires.

FLOW:
  1. Seven copies extension files to permanent location
  2. Seven opens Chrome to chrome://extensions
  3. Seven shows step-by-step guide overlay
  4. User toggles Developer Mode + clicks Load Unpacked
  5. Seven auto-copies the folder path to clipboard
  6. User selects the folder
  7. Extension connects within 3 seconds
  8. Done forever
"""

import os
import sys
import shutil
import subprocess
import time
from colorama import Fore


def get_extension_source():
    """Get path to extension source files in project."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ext_dir = os.path.join(project_root, "chrome_extension")
    if os.path.exists(os.path.join(ext_dir, "manifest.json")):
        return ext_dir
    return None


def get_extension_install_dir():
    """Get permanent install location for extension files."""
    appdata = os.environ.get("APPDATA", "")
    install_dir = os.path.join(appdata, "SEVEN", "chrome_extension")
    os.makedirs(install_dir, exist_ok=True)
    return install_dir


def prepare_extension():
    """
    Copy extension files to permanent location.
    Returns (success, install_path, message).
    """
    source = get_extension_source()
    if not source:
        # Also check if files already exist at install location
        install_dir = get_extension_install_dir()
        if os.path.exists(os.path.join(install_dir, "manifest.json")):
            return True, install_dir, "Extension files already present."
        return False, "", "Extension source files not found."

    install_dir = get_extension_install_dir()

    try:
        # Ensure directory exists
        os.makedirs(install_dir, exist_ok=True)

        # Clear old files
        for item in os.listdir(install_dir):
            item_path = os.path.join(install_dir, item)
            if os.path.isfile(item_path):
                try:
                    os.remove(item_path)
                except Exception:
                    pass

        # Copy fresh files
        copied = 0
        for item in os.listdir(source):
            src = os.path.join(source, item)
            dst = os.path.join(install_dir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                copied += 1

        # Verify manifest.json was copied
        if not os.path.exists(os.path.join(install_dir, "manifest.json")):
            return False, "", "manifest.json failed to copy"

        print(Fore.GREEN + f"[CHROME SETUP] {copied} files copied to {install_dir}")
        return True, install_dir, "Extension files prepared."

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, "", f"File copy failed: {e}"


def copy_path_to_clipboard(path):
    """Copy the extension folder path to user's clipboard."""
    try:
        subprocess.run(
            ["clip"],
            input=path.encode("utf-8"),
            check=True,
            creationflags=0x08000000
        )
        return True
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.OpenClipboard(0)
            ctypes.windll.user32.EmptyClipboard()
            data = path.encode("utf-16-le") + b"\x00\x00"
            h = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(data))
            p = ctypes.windll.kernel32.GlobalLock(h)
            ctypes.cdll.msvcrt.memcpy(p, data, len(data))
            ctypes.windll.kernel32.GlobalUnlock(h)
            ctypes.windll.user32.SetClipboardData(13, h)
            ctypes.windll.user32.CloseClipboard()
            return True
        except Exception:
            return False


def open_chrome_extensions_page():
    """Open Chrome extensions page. If Chrome is already running, opens as new tab."""
    chrome_exe = _find_chrome_exe()
    if not chrome_exe:
        return False, "Chrome not found"

    try:
        import webbrowser
        webbrowser.open("chrome://extensions/")
        return True, "Chrome extensions page opened"
    except Exception:
        pass

    try:
        subprocess.Popen([chrome_exe, "chrome://extensions/"])
        return True, "Chrome extensions page opened"
    except Exception as e:
        return False, f"Failed to open Chrome: {e}"


def check_extension_status():
    """Check if extension is installed and syncing tabs."""
    install_dir = get_extension_install_dir()
    files_exist = os.path.exists(os.path.join(install_dir, "manifest.json"))

    connected = False
    tab_count = 0
    profile_count = 0

    try:
        from backend.routes.chrome import _tab_snapshots, _last_update
        connected = (time.time() - _last_update) < 10 if _last_update > 0 else False
        profile_count = len(_tab_snapshots)
        for snap in _tab_snapshots.values():
            for win in snap.get("windows", []):
                tab_count += len(win.get("tabs", []))
    except Exception:
        pass

    return {
        "installed":     files_exist,
        "connected":     connected,
        "tab_count":     tab_count,
        "profile_count": profile_count,
        "extension_path": get_extension_install_dir(),
    }


def uninstall_extension():
    """Remove extension files."""
    install_dir = get_extension_install_dir()
    try:
        if os.path.exists(install_dir):
            shutil.rmtree(install_dir)
        return True, "Extension files removed. Remove from chrome://extensions manually."
    except Exception as e:
        return False, f"Removal failed: {e}"


def _find_chrome_exe():
    """Find Chrome executable."""
    paths = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None