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
    """
    Authoritative Chrome profile directory resolver.
    Inspects 'Local State' info_cache to map profile names, emails,
    and account handles directly to disk folder names (e.g. 'Default', 'Profile 1').
    """
    if not os.path.exists(chrome_base):
        return None

    clean_pname = (profile_name or "default").strip().lower()

    # Step 1: Query Chrome's Master Local State cache
    local_state_path = os.path.join(chrome_base, "Local State")
    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            info_cache = state.get("profile", {}).get("info_cache", {})

            # Exact folder key match
            for pdir in info_cache:
                if pdir.lower() == clean_pname:
                    return pdir

            # Match by email, user_name, or display name
            for pdir, info in info_cache.items():
                email = (info.get("user_name") or info.get("signin", {}).get("login", "") or "").lower()
                dname = (info.get("name") or "").lower()
                gname = (info.get("gaia_name") or "").lower()

                if clean_pname in (email, email.split("@")[0], dname, gname):
                    return pdir
                if clean_pname and (clean_pname in email or clean_pname in dname):
                    return pdir
        except Exception:
            pass

    # Step 2: Query individual profile Preferences
    for item in os.listdir(chrome_base):
        if item != "Default" and not item.startswith("Profile"):
            continue
        if item.lower() == clean_pname:
            return item
        prefs = os.path.join(chrome_base, item, "Preferences")
        if not os.path.exists(prefs):
            continue
        try:
            with open(prefs, "r", encoding="utf-8") as f:
                data = json.load(f)
            for acc in data.get("account_info", []):
                email = acc.get("email", "").lower()
                if clean_pname in email or email.split("@")[0] == clean_pname:
                    return item
            pname = (data.get("profile", {}).get("name") or "").lower()
            if pname == clean_pname:
                return item
        except Exception:
            continue

    # Step 3: Default fallback
    if os.path.exists(os.path.join(chrome_base, "Default")):
        return "Default"

    return "Default"