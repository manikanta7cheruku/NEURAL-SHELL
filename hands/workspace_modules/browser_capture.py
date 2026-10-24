"""
hands/workspace_modules/browser_capture.py

Turns each open Chrome, Edge or Brave window into a workspace entry with its tabs, profile and position.

    1. UI Automation reads the window's tab titles and the address of the active tab (browser_tabs.py).
    2. The Seven extension, when installed, reports every tab's URL with its title (backend/routes/chrome.py,
       or the cache the offline listener keeps). Titles are matched one to one, so each window keeps its own
       tabs even when two windows show the same site.
    3. The profile comes from the matched tabs, the browser's command line, or the profile name Edge puts in
       its window title.

A tab whose URL is unknown (no extension, not the active tab) is kept with its title so the workspace shows it
and restore can tell whether it is already open, but it cannot be reopened. tabs_without_url says how many.
"""

import re
from collections import Counter
from typing import Dict, List

from colorama import Fore

from hands.workspace_modules import browser_sessions
from hands.workspace_modules.browser_tabs import window_tabs

_INTERNAL = ("chrome://", "edge://", "brave://", "chrome-extension://", "devtools://", "about:", "chrome-search://")
_MORE_PAGES = re.compile(r"\s+and \d+ more pages?$")      # Edge: "Notes.pdf and 3 more pages"
# Chrome: "Page - Google Chrome" or "Page - Google Chrome - Mani". Edge: "Page - Personal - Microsoft Edge".
_CHROME = re.compile(r"\s+-\s+Google Chrome(?:\s+-\s+(?P<profile>.+))?\s*$")
_EDGE = re.compile(r"\s+-\s+Microsoft​?\s?Edge\s*$")
_BRAVE = re.compile(r"\s+-\s+Brave\s*$")


def _profile_names(browser: str) -> Dict[str, str]:
    """{display name (lower): profile directory} for one browser."""
    cache = browser_sessions._local_state(browser).get("profile", {}).get("info_cache", {})
    return {(info.get(k) or "").strip().lower(): d for d, info in cache.items()
            for k in ("name", "gaia_name", "shortcut_name") if (info.get(k) or "").strip()}


def split_title(browser: str, window_title: str):
    """(page title, profile directory or "") from a browser window title."""
    title, profile = (window_title or "").strip(), ""
    m = _CHROME.search(title)
    if m:
        title, profile = title[:m.start()], (m.group("profile") or "").strip()
    elif _EDGE.search(title):
        title = _EDGE.sub("", title)
        head, sep, last = title.rpartition(" - ")
        if sep and last.strip().lower() in _profile_names(browser):     # only a real profile name is stripped
            title, profile = head, last.strip()
    else:
        title = _BRAVE.sub("", title)
    directory = _profile_names(browser).get(profile.lower(), "") if profile else ""
    return _MORE_PAGES.sub("", title.strip()), directory


def _extension_pool() -> List[Dict]:
    """Every tab the extension knows about, with its profile directory."""
    pool = []
    try:
        from hands.workspace_modules.chrome_utils import _fetch_tabs_via_http, _load_cached_tabs_from_disk
        by_profile = _fetch_tabs_via_http() or _load_cached_tabs_from_disk()
    except Exception:
        by_profile = {}
    for profile_dir, tabs in (by_profile or {}).items():
        for t in tabs:
            if t.get("url"):
                pool.append({"url": t["url"], "title": (t.get("title") or "").strip(),
                             "pinned": bool(t.get("pinned")), "profile_dir": profile_dir})
    return pool


def _take(pool: List[Dict], title: str):
    for i, t in enumerate(pool):
        if t["title"] == title:
            return pool.pop(i)
    return None


def _profile_from_title(browser: str, window_title: str) -> str:
    """Edge, and Chrome with several profiles open, put the profile name in the window title."""
    return split_title(browser, window_title)[1]


def _profile_from_buttons(browser: str, buttons: List[str]) -> str:
    """Chrome's toolbar shows the profile's name (or first name) on the avatar button."""
    cache = browser_sessions._local_state(browser).get("profile", {}).get("info_cache", {})
    names = {b.strip().lower() for b in buttons}
    for directory, info in cache.items():
        for key in ("name", "gaia_given_name", "gaia_name", "shortcut_name"):
            value = (info.get(key) or "").strip().lower()
            if value and (value in names or value.split()[0] in names):
                return directory
    return ""


def enrich_browsers(apps: List[Dict]) -> None:
    entries = [a for a in apps if a.get("_is_browser")]
    if not entries:
        return
    pool = _extension_pool()
    total = unknown = 0
    for entry in entries:
        entry.pop("_is_browser", None)
        browser = entry.get("type", "chrome")
        window_title = (entry.get("window") or {}).get("title", "")
        info = window_tabs(entry["hwnd"]) if entry.get("hwnd") else {"titles": [], "active_url": "", "buttons": []}
        if "Incognito" in info.get("buttons", []) or "InPrivate" in window_title:
            entry["tabs"] = []                   # private windows are never saved
            continue
        active_title = split_title(browser, window_title)[0]

        tabs, profiles = [], Counter()
        for title in info["titles"] or [active_title]:
            match = _take(pool, title.strip())
            if match:
                profiles[match["profile_dir"]] += 1
                tabs.append({"url": match["url"], "title": title, "pinned": match["pinned"]})
            else:
                is_active = title.strip() == active_title or (active_title and title.startswith(active_title[:40]))
                url = info["active_url"] if is_active and info["active_url"] else ""
                if not url and title.startswith(("http://", "https://", "file:///")):
                    url = title                      # pages without a title show their address
                tabs.append({"url": url, "title": title, "pinned": False})
        tabs = [t for t in tabs if not t["url"].startswith(_INTERNAL) and (t["url"] or t["title"])]

        profile_dir = (_profile_from_buttons(browser, info.get("buttons", []))
                       or (profiles.most_common(1)[0][0] if profiles else "")
                       or _profile_from_title(browser, window_title) or entry.get("profile_dir") or "Default")
        label = browser_sessions.BROWSERS.get(browser, {}).get("label", browser.title())
        profile_name = browser_sessions.profile_label(browser, profile_dir)
        missing = sum(1 for t in tabs if not t["url"])
        entry.update(tabs=tabs, profile_dir=profile_dir, profile_name=profile_name,
                     name=f"{label} ({profile_name}) - {len(tabs)} tab{'' if len(tabs) == 1 else 's'}",
                     tabs_without_url=missing)
        total += len(tabs)
        unknown += missing
    apps[:] = [a for a in apps if not (a.get("type") in browser_sessions.BROWSERS and not a.get("tabs"))]
    note = f", {unknown} without an address (install the Seven extension to save those)" if unknown else ""
    print(Fore.GREEN + f"[WORKSPACE] Browsers: {len(entries)} windows, {total} tabs{note}")


def browsers_overview() -> List[Dict]:
    """Every open browser profile with its windows and tabs, and how many tabs have a full address (from the
    extension) versus a title only. For the Workspaces page."""
    from hands.workspace_modules.browser_restore import _browser_windows
    import win32gui
    pool = _extension_pool()
    rows: Dict[tuple, Dict] = {}
    for browser in browser_sessions.BROWSERS:
        if not browser_sessions.is_running(browser):
            continue
        for hwnd in _browser_windows(browser):
            info = window_tabs(hwnd)
            if "Incognito" in info.get("buttons", []):
                continue
            title = win32gui.GetWindowText(hwnd)
            if "InPrivate" in title:
                continue
            profile = (_profile_from_buttons(browser, info.get("buttons", []))
                       or _profile_from_title(browser, title) or "Default")
            row = rows.setdefault((browser, profile), {
                "browser": browser, "label": browser_sessions.BROWSERS[browser]["label"], "profile_dir": profile,
                "profile_name": browser_sessions.profile_label(browser, profile), "windows": 0, "tabs": 0,
                "with_address": 0})
            row["windows"] += 1
            row["tabs"] += len(info["titles"])
            pooled = [t for t in pool if t["profile_dir"] == profile]
            row["with_address"] += sum(1 for t in info["titles"] if any(p["title"] == t for p in pooled))
    out = list(rows.values())
    for r in out:
        r["extension"] = r["with_address"] > 0 and r["browser"] in ("chrome", "edge", "brave")
    return sorted(out, key=lambda r: (r["label"], r["profile_name"]))
