"""
hands/workspace_modules/browser_sessions.py

Reads which tabs are open in Chrome, Edge and Brave straight from the browser's own session file, so workspaces
capture every tab without the Seven extension, and restore knows exactly what is already open.

HOW CHROMIUM STORES A SESSION
    <User Data>\\<Profile>\\Sessions\\Session_<time> is an append-only log ("SNSS"): a 4-byte magic, an int32
    version, then commands of [uint16 size][uint8 id][payload]. Replaying the log gives the live state:

        0  SetTabWindow              {int32 window_id, int32 tab_id}
        2  SetTabIndexInWindow       {int32 tab_id, int32 index}
        6  UpdateTabNavigation       pickle: {uint32 size, int32 tab_id, int32 nav_index, string url, string16 title}
        7  SetSelectedNavigationIndex{int32 tab_id, int32 nav_index}      which history entry is showing
        8  SetSelectedTabInIndex     {int32 window_id, int32 tab_index}    the active tab of a window
        9  SetWindowType             {int32 window_id, int32 type}         0 = normal window
        12 SetPinnedState            {int32 tab_id, bool pinned}
        16 TabClosed / 17 WindowClosed {int32 id, int64 time}

    The current page of a tab is its navigation at the selected index, not every page in its back history.
    Tabs_* files in the same folder are recently CLOSED tabs and must never be read as open ones.

Chromium saves the log about 2.5 seconds after a change, so this is as fresh as the extension in practice.
"""

import json
import os
import struct
from typing import Dict, List, Optional

_LOCAL = os.environ.get("LOCALAPPDATA", "")

BROWSERS = {
    "chrome": {"data": os.path.join(_LOCAL, "Google", "Chrome", "User Data"), "exe_name": "chrome.exe",
               "exe": [os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
                       os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
                       os.path.join(_LOCAL, "Google", "Chrome", "Application", "chrome.exe")],
               "label": "Chrome"},
    "edge": {"data": os.path.join(_LOCAL, "Microsoft", "Edge", "User Data"), "exe_name": "msedge.exe",
             "exe": [os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
                     os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe")],
             "label": "Edge"},
    "brave": {"data": os.path.join(_LOCAL, "BraveSoftware", "Brave-Browser", "User Data"), "exe_name": "brave.exe",
              "exe": [os.path.join(os.environ.get("PROGRAMFILES", ""), "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
                      os.path.join(_LOCAL, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")],
              "label": "Brave"},
}

_SKIP_SCHEMES = ("chrome://", "edge://", "brave://", "chrome-extension://", "devtools://", "about:", "chrome-search://")


def find_exe(browser: str) -> Optional[str]:
    for path in BROWSERS.get(browser, {}).get("exe", []):
        if path and os.path.exists(path):
            return path
    return None


def _read_pickle_string(buf: bytes, pos: int, wide: bool):
    (length,) = struct.unpack_from("<i", buf, pos)
    pos += 4
    nbytes = length * 2 if wide else length
    if length < 0 or pos + nbytes > len(buf):
        raise ValueError("bad string")
    raw = buf[pos:pos + nbytes]
    pos += (nbytes + 3) & ~3                                # pickle fields are 4-byte aligned
    return raw.decode("utf-16-le" if wide else "utf-8", errors="replace"), pos


def parse_session(path: str) -> List[Dict]:
    """Open windows in a session file: [{window_id, active_index, tabs: [{url, title, pinned}]}] in tab order."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    if len(data) < 8 or data[:4] != b"SNSS":
        return []

    navs: Dict[tuple, tuple] = {}            # (tab, nav_index) -> (url, title)
    selected_nav: Dict[int, int] = {}
    tab_window: Dict[int, int] = {}
    tab_index: Dict[int, int] = {}
    pinned: Dict[int, bool] = {}
    window_active: Dict[int, int] = {}
    window_type: Dict[int, int] = {}
    closed_tabs, closed_windows = set(), set()

    pos, end = 8, len(data)
    while pos + 2 <= end:
        (size,) = struct.unpack_from("<H", data, pos)
        pos += 2
        if size == 0 or pos + size > end:
            break
        cid, body = data[pos], data[pos + 1:pos + size]
        pos += size
        try:
            if cid == 6 and len(body) >= 12:
                _, tab, idx = struct.unpack_from("<Iii", body, 0)
                url, p = _read_pickle_string(body, 12, wide=False)
                title = ""
                try:
                    title, _ = _read_pickle_string(body, p, wide=True)
                except Exception:
                    pass
                navs[(tab, idx)] = (url, title)
            elif cid == 0 and len(body) >= 8:
                win, tab = struct.unpack_from("<ii", body, 0)
                tab_window[tab] = win
            elif cid == 7 and len(body) >= 8:
                tab, idx = struct.unpack_from("<ii", body, 0)
                selected_nav[tab] = idx
            elif cid == 2 and len(body) >= 8:
                tab, idx = struct.unpack_from("<ii", body, 0)
                tab_index[tab] = idx
            elif cid == 8 and len(body) >= 8:
                win, idx = struct.unpack_from("<ii", body, 0)
                window_active[win] = idx
            elif cid == 9 and len(body) >= 8:
                win, kind = struct.unpack_from("<ii", body, 0)
                window_type[win] = kind
            elif cid == 12 and len(body) >= 5:
                (tab,) = struct.unpack_from("<i", body, 0)
                pinned[tab] = bool(body[4])
            elif cid == 16 and len(body) >= 4:
                closed_tabs.add(struct.unpack_from("<i", body, 0)[0])
            elif cid == 17 and len(body) >= 4:
                closed_windows.add(struct.unpack_from("<i", body, 0)[0])
        except (struct.error, ValueError):
            continue

    windows: Dict[int, List] = {}
    for tab, win in tab_window.items():
        if tab in closed_tabs or win in closed_windows or window_type.get(win, 0) != 0:
            continue
        indexes = [i for (t, i) in navs if t == tab]
        if not indexes:
            continue
        nav = selected_nav.get(tab, max(indexes))
        url, title = navs.get((tab, nav)) or navs[(tab, max(indexes))]
        windows.setdefault(win, []).append((tab_index.get(tab, 0), {"url": url, "title": title,
                                                                    "pinned": pinned.get(tab, False)}))
    out = []
    for win, tabs in windows.items():
        tabs.sort(key=lambda t: t[0])
        out.append({"window_id": win, "active_index": window_active.get(win, 0), "tabs": [t for _, t in tabs]})
    return out


def newest_session_file(profile_path: str) -> Optional[str]:
    folder = os.path.join(profile_path, "Sessions")
    try:
        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.startswith("Session_") and not f.endswith((".tmp", ".bak"))]
    except OSError:
        return None
    return max(files, key=os.path.getmtime) if files else None


def profile_windows(browser: str, profile_dir: str) -> List[Dict]:
    """Restorable windows of one profile (internal pages dropped, empty windows skipped)."""
    base = BROWSERS.get(browser, {}).get("data", "")
    path = newest_session_file(os.path.join(base, profile_dir))
    if not path:
        return []
    out = []
    for w in parse_session(path):
        tabs = [t for t in w["tabs"] if t["url"] and not t["url"].startswith(_SKIP_SCHEMES)]
        if tabs:
            active = w["tabs"][min(w["active_index"], len(w["tabs"]) - 1)] if w["tabs"] else {}
            out.append({"tabs": tabs, "active_title": active.get("title", "")})
    return out


def _local_state(browser: str) -> dict:
    try:
        with open(os.path.join(BROWSERS[browser]["data"], "Local State"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, KeyError):
        return {}


def open_profiles(browser: str) -> List[str]:
    """Profiles open in the running browser, from Local State (last_active_profiles is kept current while it runs)."""
    prof = _local_state(browser).get("profile", {})
    active = [p for p in prof.get("last_active_profiles", []) if p]
    return active or ([prof["last_used"]] if prof.get("last_used") else ["Default"])


def profile_label(browser: str, profile_dir: str) -> str:
    info = _local_state(browser).get("profile", {}).get("info_cache", {}).get(profile_dir, {})
    return info.get("gaia_name") or info.get("name") or profile_dir


def restores_last_session(browser: str, profile_dir: str) -> bool:
    """True when the profile is set to "Continue where you left off": a cold launch reopens its last tabs."""
    try:
        with open(os.path.join(BROWSERS[browser]["data"], profile_dir, "Preferences"), "r", encoding="utf-8") as f:
            prefs = json.load(f)
        return prefs.get("session", {}).get("restore_on_startup") == 1
    except (OSError, ValueError, KeyError):
        return False


def is_running(browser: str) -> bool:
    try:
        import psutil
        name = BROWSERS[browser]["exe_name"]
        return any((p.info.get("name") or "").lower() == name for p in psutil.process_iter(["name"]))
    except Exception:
        return False


def open_urls(browser: str, profile_dir: str) -> set:
    """Normalised URLs open right now in one profile."""
    from hands.workspace_modules.url_matching import normalize_url
    if not is_running(browser):
        return set()
    return {normalize_url(t["url"]) for w in profile_windows(browser, profile_dir) for t in w["tabs"]}
