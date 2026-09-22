"""
hands/workspace_modules/chrome_utils.py
Chrome profile detection, tab URL collection, and profile matching.

BUG FIX (v1.3.3): Removed duplicate _browser_profile_matches_window.
Only the advanced version (with stop_words + token overlap) is kept.
"""
import os
import re
import json
import struct
from colorama import Fore

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    pass

from hands.workspace_modules.url_matching import normalize_url, extract_domain


def _build_profile_dir_map() -> dict:
    """
    Map extension profile names → Chrome disk directory names.
    Reads each profile's Preferences file to extract emails, usernames,
    and display names, then maps them to the folder name on disk.

    Returns: {lowercase_name: "Default"|"Profile 1"|...}
    This is the canonical bridge between the extension's ambiguous
    profile identifiers and Chrome's actual directory structure.
    """
    chrome_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    if not os.path.isdir(chrome_base):
        return {}

    mapping = {}
    try:
        for entry in os.listdir(chrome_base):
            if entry != "Default" and not entry.startswith("Profile"):
                continue
            prefs_path = os.path.join(chrome_base, entry, "Preferences")
            if not os.path.isfile(prefs_path):
                continue
            try:
                with open(prefs_path, "r", encoding="utf-8") as f:
                    prefs = json.load(f)

                for acc in prefs.get("account_info", []):
                    email = (acc.get("email") or "").lower().strip()
                    if email:
                        mapping[email] = entry
                        mapping[email.split("@")[0]] = entry

                pname = (prefs.get("profile", {}).get("name") or "").lower().strip()
                if pname:
                    mapping[pname] = entry

                uname = (prefs.get("profile", {}).get("user_name") or "").lower().strip()
                if uname:
                    mapping[uname] = entry
                    if "@" in uname:
                        mapping[uname.split("@")[0]] = entry
            except Exception:
                continue
    except Exception:
        pass
    return mapping


def _rekey_by_profile_dir(grouped: dict) -> dict:
    """
    Re-key a {extension_profile_name: [tabs]} dict to {disk_directory: [tabs]}.
    Uses _build_profile_dir_map() for resolution.
    Falls back to original key if no match found.
    """
    if not grouped:
        return grouped

    dir_map = _build_profile_dir_map()
    rekeyed = {}

    for prof_key, tabs_list in grouped.items():
        pk_lower = prof_key.lower().strip()

        # Exact match
        resolved = dir_map.get(pk_lower, "")

        # Fuzzy match
        if not resolved:
            for map_key, map_dir in dir_map.items():
                if pk_lower in map_key or map_key in pk_lower:
                    resolved = map_dir
                    break

        final_key = resolved or prof_key
        if final_key not in rekeyed:
            rekeyed[final_key] = []
        rekeyed[final_key].extend(tabs_list)

    return rekeyed


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


def _is_seven_backend_alive() -> bool:
    """
    50ms socket probe to check if a backend/listener is running on port 7777.
    """
    import socket as _socket
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(0.05)
        result = s.connect_ex(("127.0.0.1", 7777))
        s.close()
        return result == 0
    except Exception:
        return False


def _load_cached_tabs_from_disk() -> dict:
    """
    Fallback: Reads the latest live Chrome tab snapshot directly from disk cache.
    Handles both multi-profile dicts and flattened tab arrays.
    """
    cache_path = os.path.join(
        os.environ.get("APPDATA", ""), "SEVEN", "cache", "live_chrome_tabs.json"
    )
    if not os.path.isfile(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data or not isinstance(data, dict) or not data.get("available"):
            return {}

        # 1. Try multi-profile map
        profiles_map = data.get("profiles")
        if isinstance(profiles_map, dict) and profiles_map:
            grouped = {}
            for prof_name, tabs in profiles_map.items():
                clean_tabs = []
                for t in tabs:
                    url = (t.get("url") or "").strip()
                    if url and not url.startswith(("chrome://", "edge://", "chrome-extension://")):
                        clean_tabs.append({
                            "url": url,
                            "title": t.get("title", ""),
                            "pinned": t.get("pinned", False),
                        })
                if clean_tabs:
                    grouped[prof_name] = clean_tabs
            if grouped:
                return _rekey_by_profile_dir(grouped)

        # 2. Fallback to flat tabs list
        tabs_list = data.get("tabs", [])
        if tabs_list:
            grouped = {}
            for t in tabs_list:
                prof = t.get("profile") or "default"
                url = (t.get("url") or "").strip()
                if not url or url.startswith(("chrome://", "edge://", "chrome-extension://")):
                    continue
                if prof not in grouped:
                    grouped[prof] = []
                grouped[prof].append({
                    "url": url,
                    "title": t.get("title", ""),
                    "pinned": t.get("pinned", False),
                })
            if grouped:
                return _rekey_by_profile_dir(grouped)
    except Exception:
        pass
    return {}


def _fetch_tabs_via_http(retries=2, delay=0.2) -> dict:
    """
    Fetch live Chrome tab data from port 7777 (FastAPI server or offline listener).
    Falls back to disk cache if socket is transitioning.
    """
    import urllib.request
    import time as _time

    if _is_seven_backend_alive():
        for attempt in range(retries):
            try:
                req = urllib.request.urlopen(
                    "http://127.0.0.1:7777/api/chrome/tabs",
                    timeout=0.8
                )
                data = json.loads(req.read().decode("utf-8"))
                if data and isinstance(data, dict) and data.get("available"):
                    grouped = {}

                    # Check profiles map first
                    if isinstance(data.get("profiles"), dict):
                        for prof_name, tabs in data["profiles"].items():
                            clean = [
                                {"url": t.get("url", ""), "title": t.get("title", ""), "pinned": t.get("pinned", False)}
                                for t in tabs
                                if (t.get("url") or "").startswith("http")
                            ]
                            if clean:
                                grouped[prof_name] = clean
                    else:
                        # Fallback to flat tabs
                        for t in data.get("tabs", []):
                            prof = t.get("profile") or "default"
                            url = t.get("url", "")
                            if not url.startswith("http"):
                                continue
                            if prof not in grouped:
                                grouped[prof] = []
                            grouped[prof].append({
                                "url": url,
                                "title": t.get("title", ""),
                                "pinned": t.get("pinned", False),
                            })

                    if grouped:
                        grouped = _rekey_by_profile_dir(grouped)
                        total = sum(len(v) for v in grouped.values())
                        print(Fore.CYAN + f"[WORKSPACE] Live tabs fetched: "
                              f"{total} tabs across {len(grouped)} profile(s) "
                              f"(dirs: {list(grouped.keys())})")
                        return grouped
                if attempt < retries - 1:
                    _time.sleep(delay)
                    continue
            except Exception:
                if attempt < retries - 1:
                    _time.sleep(delay)
                    continue

    # Fallback to direct disk cache
    cached = _load_cached_tabs_from_disk()
    if cached:
        total = sum(len(v) for v in cached.values())
        print(Fore.CYAN + f"[WORKSPACE] Live tabs from cache: "
              f"{total} tabs across {len(cached)} profile(s)")
        return cached

    return {}


def _get_chrome_user_data_dir() -> str:
    """Returns path to Chrome User Data directory."""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return ""
    return os.path.join(local_app_data, "Google", "Chrome", "User Data")


def _parse_snss_file(filepath: str) -> list:
    """
    Parses Chromium SNSS (Session Navigation Storage System) binary file.
    Reads open tabs and closed tab events in real-time from disk.
    Works offline without Chrome extension or backend server.
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read()
    except Exception:
        return []

    if len(data) < 8 or data[:4] != b"SNSS":
        return []

    offset = 8
    active_tabs = {}     # tab_id (int) -> url (str)
    closed_tabs = set()  # set of closed tab_ids
    tab_windows = {}     # tab_id -> window_id
    closed_windows = set()

    data_len = len(data)
    while offset + 2 <= data_len:
        size = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        if size == 0 or offset + size > data_len:
            break

        cmd_id = data[offset]
        payload = data[offset + 1:offset + size]
        offset += size

        # UpdateTabNavigation commands (id 6 in standard Chromium, 1 or 10 in variants)
        if cmd_id in (1, 6, 10) and len(payload) >= 8:
            tab_id = struct.unpack_from("<i", payload, 0)[0]
            # Search for URL prefix in payload
            for prefix in (b"https://", b"http://", b"file://", b"chrome://"):
                idx = payload.find(prefix)
                if idx >= 0:
                    end = idx
                    while end < len(payload) and 33 <= payload[end] <= 126 and payload[end] not in (ord('"'), ord("'"), ord("<"), ord(">")):
                        end += 1
                    try:
                        url_str = payload[idx:end].decode("utf-8", errors="ignore")
                        if url_str.startswith(("http://", "https://", "file://", "chrome://")):
                            active_tabs[tab_id] = url_str
                            closed_tabs.discard(tab_id)
                    except Exception:
                        pass
                    break

        # TabClosed (id 2 or 15)
        elif cmd_id in (2, 15) and len(payload) >= 4:
            tab_id = struct.unpack_from("<i", payload, 0)[0]
            closed_tabs.add(tab_id)

        # SetTabWindow (id 0)
        elif cmd_id == 0 and len(payload) >= 8:
            tab_id = struct.unpack_from("<i", payload, 0)[0]
            win_id = struct.unpack_from("<i", payload, 4)[0]
            tab_windows[tab_id] = win_id

        # WindowClosed (id 3 or 16)
        elif cmd_id in (3, 16) and len(payload) >= 4:
            win_id = struct.unpack_from("<i", payload, 0)[0]
            closed_windows.add(win_id)

    # Filter out tabs that were closed or belonged to closed windows
    result = []
    for tab_id, url in active_tabs.items():
        if tab_id in closed_tabs:
            continue
        win_id = tab_windows.get(tab_id)
        if win_id is not None and win_id in closed_windows:
            continue
        result.append({"url": url, "title": ""})

    return result


def read_open_tabs_from_session_file(profile_dir_path: str) -> list:
    """
    Finds and parses the newest Tabs_* or Session_* file for a profile directory.
    """
    sessions_dir = os.path.join(profile_dir_path, "Sessions")
    if not os.path.isdir(sessions_dir):
        return []

    tab_files = []
    try:
        for fname in os.listdir(sessions_dir):
            if fname.startswith(("Tabs_", "Session_")) and not fname.endswith((".tmp", ".bak")):
                full_p = os.path.join(sessions_dir, fname)
                if os.path.isfile(full_p):
                    tab_files.append(full_p)
    except Exception:
        return []

    if not tab_files:
        return []

    tab_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    for filepath in tab_files:
        try:
            tabs = _parse_snss_file(filepath)
            if tabs:
                return tabs
        except Exception:
            continue

    return []


def _get_open_tabs_from_disk_sessions() -> dict:
    """
    Offline fallback: Scans Chrome User Data directory and reads live
    open tabs directly from disk session files for all open profiles.
    Returns: { profile_dir: [ {"url": url, "title": ""}, ... ] }
    """
    user_data = _get_chrome_user_data_dir()
    if not user_data or not os.path.isdir(user_data):
        return {}

    result = {}
    try:
        entries = os.listdir(user_data)
    except Exception:
        return {}

    for entry in entries:
        if entry != "Default" and not entry.startswith("Profile"):
            continue

        pdir = os.path.join(user_data, entry)
        if not os.path.isdir(pdir):
            continue

        tabs = read_open_tabs_from_session_file(pdir)
        if tabs:
            result[entry] = tabs

    return result


def get_open_chrome_tabs() -> tuple:
    """
    Get all currently open Chrome tab URLs (flat, all profiles combined).
    Returns (open_urls: set, open_domains: set).
    """
    open_urls    = set()
    open_domains = set()

    profile_tabs = _fetch_tabs_via_http()

    if not profile_tabs:
        try:
            from backend.routes.chrome import get_tabs_by_profile
            profile_tabs = get_tabs_by_profile()
        except Exception:
            pass

    if profile_tabs:
        for tabs in profile_tabs.values():
            for t in tabs:
                url = t.get("url", "")
                if url and url.startswith("http"):
                    open_urls.add(normalize_url(url))
                    open_domains.add(extract_domain(url))
        if open_urls:
            print(Fore.CYAN + f"[WORKSPACE] Chrome tabs loaded: "
                  f"{len(open_urls)} URLs, "
                  f"{len(open_domains)} domains")
            return open_urls, open_domains

    return open_urls, open_domains


def get_open_chrome_tabs_per_profile() -> dict:
    """
    Get currently open Chrome tab URLs grouped by profile directory.
    Returns dict: { profile_dir: set(normalized_urls) }
    """
    profile_url_map = {}

    profile_tabs = _fetch_tabs_via_http()

    if not profile_tabs:
        try:
            from backend.routes.chrome import get_tabs_by_profile
            profile_tabs = get_tabs_by_profile()
        except Exception:
            pass

    if not profile_tabs:
        profile_tabs = _load_cached_tabs_from_disk()

    if profile_tabs:
        profile_tabs = _rekey_by_profile_dir(profile_tabs)

        for prof_key, tabs in profile_tabs.items():
            pk = prof_key.strip()
            url_set = set()
            for t in tabs:
                url = t.get("url", "")
                if url and url.startswith("http"):
                    url_set.add(normalize_url(url))
            if url_set:
                profile_url_map[pk] = url_set

        if profile_url_map:
            total = sum(len(v) for v in profile_url_map.values())
            print(Fore.CYAN + f"[WORKSPACE] Chrome per-profile: "
                  f"{len(profile_url_map)} profiles, {total} total URLs")

    return profile_url_map