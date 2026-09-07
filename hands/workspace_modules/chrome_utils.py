"""
hands/workspace_modules/chrome_utils.py
Chrome profile detection, tab URL collection, and profile matching.

BUG FIX (v1.3.3): Removed duplicate _browser_profile_matches_window.
Only the advanced version (with stop_words + token overlap) is kept.
"""
import os
import re
import json
from colorama import Fore

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    pass

from hands.workspace_modules.url_matching import normalize_url, extract_domain


def get_open_chrome_profiles() -> set:
    """
    Detect which Chrome profiles have open windows right now.
    Reads Chrome window titles and matches against Local State profiles.
    """
    profiles = set()
    try:
        chrome_base = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Google", "Chrome", "User Data"
        )
        local_state_path = os.path.join(chrome_base, "Local State")
        if not os.path.exists(local_state_path):
            return profiles

        with open(local_state_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        info_cache = state.get("profile", {}).get("info_cache", {})

        profile_map = {}
        default_email = ""
        for profile_dir, info in info_cache.items():
            email = (
                info.get("user_name") or
                info.get("signin", {}).get("login", "") or
                ""
            ).lower()
            display_name = (info.get("name") or "").lower()
            if email:
                if display_name:
                    profile_map[display_name] = email
                if profile_dir.lower() == "default":
                    default_email = email

        if not profile_map and not default_email:
            return profiles

        chrome_titles = []

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                if proc.name().lower() == "chrome.exe":
                    chrome_titles.append(title.lower())
            except Exception:
                pass

        win32gui.EnumWindows(_cb, None)

        if not chrome_titles:
            return profiles

        matched_any = False
        for title in chrome_titles:
            for display_name, email in profile_map.items():
                if display_name in title:
                    profiles.add(email)
                    profiles.add(email.split("@")[0])
                    matched_any = True

        if not matched_any and chrome_titles and default_email:
            profiles.add(default_email)
            profiles.add(default_email.split("@")[0])

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome profile detection: {e}")

    return profiles


def browser_profile_matches_window(saved_cfg: dict,
                                    current_browser_titles: list) -> bool:
    """
    Infer whether a saved browser profile is already open by comparing
    saved tab titles/domains against currently visible browser window titles.

    Uses stop-word filtering and token overlap for robust matching.
    This is the SINGLE authoritative version (duplicate removed in v1.3.3).
    """
    tabs = saved_cfg.get("tabs", []) or []
    if not tabs or not current_browser_titles:
        return False

    stop_words = {
        "google", "chrome", "free", "online", "the", "and",
        "for", "with", "your", "from", "app", "www", "com",
        "net", "org"
    }

    candidates = set()

    for tab in tabs[:10]:
        title = (tab.get("title") or "").strip().lower()
        url   = (tab.get("url") or "").strip().lower()

        if title:
            candidates.add(title)

            for frag in re.split(r"[|\-:•]+", title):
                frag = frag.strip()
                if len(frag) >= 4:
                    candidates.add(frag)

            for tok in re.findall(r"[a-z0-9]+", title):
                if len(tok) >= 5 and tok not in stop_words:
                    candidates.add(tok)

        if url:
            domain = extract_domain(url)
            if domain:
                candidates.add(domain)
                for part in domain.split("."):
                    part = part.strip().lower()
                    if len(part) >= 4 and part not in stop_words:
                        candidates.add(part)

    # Direct substring match
    for win_title in current_browser_titles:
        w = (win_title or "").lower()
        for c in candidates:
            if c and c in w:
                return True

    # Token overlap match
    for win_title in current_browser_titles:
        w_tokens = {
            tok for tok in re.findall(r"[a-z0-9]+",
                                       (win_title or "").lower())
            if len(tok) >= 4 and tok not in stop_words
        }

        for tab in tabs[:10]:
            title = (tab.get("title") or "").lower()
            t_tokens = {
                tok for tok in re.findall(r"[a-z0-9]+", title)
                if len(tok) >= 4 and tok not in stop_words
            }
            if len(t_tokens & w_tokens) >= 2:
                return True

    return False


def get_open_chrome_tabs() -> tuple:
    """
    Get all currently open Chrome tab URLs.
    Returns (open_urls: set, open_domains: set).
    Mode 1: Chrome extension via Seven backend.
    Mode 2: Chrome DevTools Protocol on port 9222.
    """
    open_urls    = set()
    open_domains = set()

    # Mode 1: Chrome extension
    try:
        from backend.routes.chrome import get_tabs_by_profile
        profile_tabs = get_tabs_by_profile()
        if profile_tabs:
            for tabs in profile_tabs.values():
                for t in tabs:
                    url = t.get("url", "")
                    if url and url.startswith("http"):
                        norm   = normalize_url(url)
                        domain = extract_domain(url)
                        open_urls.add(norm)
                        open_domains.add(domain)
            if open_urls:
                print(Fore.CYAN + f"[WORKSPACE] Chrome tabs via extension: "
                      f"{len(open_urls)} URLs, "
                      f"{len(open_domains)} domains")
                return open_urls, open_domains
    except Exception:
        pass

    # Mode 2: DevTools Protocol
    import socket as _socket
    try:
        _s = _socket.create_connection(("127.0.0.1", 9222), timeout=0.1)
        _s.close()
    except Exception:
        return open_urls, open_domains

    try:
        import urllib.request
        req = urllib.request.urlopen("http://127.0.0.1:9222/json",
                                     timeout=0.5)
        tabs_data = json.loads(req.read().decode("utf-8"))
        for tab in tabs_data:
            url = tab.get("url", "")
            if url and url.startswith("http"):
                norm   = normalize_url(url)
                domain = extract_domain(url)
                open_urls.add(norm)
                open_domains.add(domain)
        if open_urls:
            print(Fore.CYAN + f"[WORKSPACE] Chrome tabs via DevTools: "
                  f"{len(open_urls)} URLs, "
                  f"{len(open_domains)} domains")
    except Exception:
        pass

    return open_urls, open_domains