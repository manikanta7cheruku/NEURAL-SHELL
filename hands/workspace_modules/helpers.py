"""
hands/workspace_modules/helpers.py
Chrome path resolution utilities.
"""
import os
import json


def find_chrome_exe():
    for p in [
        os.path.join(os.environ.get("PROGRAMFILES", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Google", "Chrome", "Application", "chrome.exe"),
    ]:
        if os.path.exists(p):
            return p
    return None


def find_chrome_profile_dir(chrome_base, profile_name):
    if not profile_name or not os.path.exists(chrome_base):
        return None

    for item in os.listdir(chrome_base):
        if item != "Default" and not item.startswith("Profile"):
            continue
        prefs = os.path.join(chrome_base, item, "Preferences")
        if not os.path.exists(prefs):
            continue
        try:
            with open(prefs, "r", encoding="utf-8") as f:
                data = json.load(f)
            for acc in data.get("account_info", []):
                email = acc.get("email", "").lower()
                if (profile_name.lower() in email or
                        email.split("@")[0] == profile_name.lower()):
                    return item
            pname = data.get("profile", {}).get("name", "")
            if pname.lower() == profile_name.lower():
                return item
        except Exception:
            continue

    profiles = [
        d for d in os.listdir(chrome_base)
        if d == "Default" or d.startswith("Profile")
    ]
    if len(profiles) == 1:
        return profiles[0]
    return None