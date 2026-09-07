"""
trigger_modules/window_finder.py
Window enumeration for arrangement cards.

BUG FIX (v1.3.3):
  Previously, SEVEN.exe (production) and Seven's Python daemons could
  slip into the enumeration if they had a visible top-level window.
  This caused the orb to be included in arrangements and moved to the
  top-left. Now hard-filtered by exe basename + path substring.
"""
import os


_SKIP_TITLES_SET = {
    "", "program manager", "microsoft text input application",
    "windows input experience", "nvidia geforce overlay",
    "nvidia geforce overlay dt", "settings",
}

_SKIP_EXE_SET = {
    "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe",
    "runtimebroker.exe", "applicationframehost.exe",
    "msedgewebview2.exe", "nvidia overlay.exe",
    "nvcontainer.exe", "nvidia share.exe",
    "widgets.exe", "widgetservice.exe",
    "lockapp.exe", "systemsettings.exe",
}


def _is_seven_window(exe_name: str, full_exe: str) -> bool:
    """
    Detect SEVEN's own windows.
    Covers: SEVEN.exe (packaged), electron.exe (dev), python.exe daemons.
    """
    exe_lower  = exe_name.lower()
    full_lower = full_exe.lower()

    if exe_lower in ("electron.exe", "seven.exe"):
        if "seven" in full_lower or "mk-projects" in full_lower:
            return True

    if exe_lower in ("python.exe", "pythonw.exe"):
        if "seven" in full_lower or "mk-projects" in full_lower:
            return True

    return False


# ─────────────────────────────────────────────────────────────────────────
# EXE-BASED MATCHING (used for workspace triggers)
# ─────────────────────────────────────────────────────────────────────────
def get_windows_by_workspace_apps(workspace_apps: list) -> tuple:
    """
    Find window handles by matching workspace app definitions.
    Uses exe_path for accurate matching — no fuzzy name matching.

    Returns (triggered_windows, other_windows)
    """
    try:
        import win32gui
        import win32process
        import psutil

        visible = []

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            title_stripped = title.lower().strip() if title else ""
            if not title or title_stripped in _SKIP_TITLES_SET:
                return
            if "nvidia" in title_stripped and "overlay" in title_stripped:
                return

            exe_name = "unknown"
            full_exe = ""
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc = psutil.Process(pid)
                    try:
                        exe_name = proc.name()
                    except Exception:
                        pass
                    try:
                        full_exe = (proc.exe() or "").lower()
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                return

            if exe_name.lower() in _SKIP_EXE_SET:
                return
            if _is_seven_window(exe_name, full_exe):
                return

            visible.append({
                "hwnd":     hwnd,
                "title":    title,
                "exe":      exe_name,
                "full_exe": full_exe,
                "triggered": False,
            })

        win32gui.EnumWindows(_cb, None)
        all_titles = visible

        triggered = []
        used = set()

        for ws_app in workspace_apps:
            exe_path     = (ws_app.get("exe_path") or "").lower()
            exe_basename = os.path.basename(exe_path).lower() if exe_path else ""
            app_type     = (ws_app.get("type") or "").lower()
            ws_window    = ws_app.get("window", {}) or {}
            expected_title = (ws_window.get("title") or "").lower()

            match = None

            # Priority 1: exact full path match
            if exe_path:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if w["full_exe"] == exe_path:
                        match = w
                        break

            # Priority 2: exe basename match
            if not match and exe_basename:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if w["exe"].lower() == exe_basename:
                        match = w
                        break

            # Priority 3: expected title exact match
            if not match and expected_title:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if w["title"].lower() == expected_title:
                        match = w
                        break

            # Priority 4: expected title substring match
            if not match and expected_title:
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if expected_title in w["title"].lower() or \
                       w["title"].lower() in expected_title:
                        match = w
                        break

            # Priority 5: elevated-process title fallback
            if not match and expected_title:
                for t in all_titles:
                    if t["hwnd"] in used:
                        continue
                    if t["title"].lower() == expected_title:
                        match = {
                            "hwnd":     t["hwnd"],
                            "title":    t["title"],
                            "exe":      exe_basename or "unknown",
                            "full_exe": "",
                            "triggered": False,
                        }
                        break

            # Priority 6: chrome profile scoring by tab title relevance
            if not match and app_type == "chrome":
                profile    = (ws_app.get("profile_name") or "").lower()
                tabs       = ws_app.get("tabs", []) or []
                tab_titles = [(t.get("title", "") or "").lower() for t in tabs]

                best = None
                best_score = 0
                for w in visible:
                    if w["hwnd"] in used:
                        continue
                    if "chrome" not in w["exe"].lower():
                        continue
                    wtitle = w["title"].lower()
                    score = 0
                    if profile and profile in wtitle:
                        score += 10
                    for tt in tab_titles:
                        if tt and len(tt) > 6 and tt[:20] in wtitle:
                            score += 5
                            break
                    if score == 0:
                        score = 1
                    if score > best_score:
                        best_score = score
                        best = w
                if best:
                    match = best

            # Priority 7: explorer folder match by title
            if not match and app_type == "explorer":
                folder = os.path.basename(ws_app.get("folder_path", "")).lower()
                if folder:
                    for w in visible:
                        if w["hwnd"] in used:
                            continue
                        if "explorer.exe" in w["exe"].lower() and \
                           folder in w["title"].lower():
                            match = w
                            break

            if match:
                m = dict(match)
                m["triggered"] = True
                m.pop("full_exe", None)
                triggered.append(m)
                used.add(match["hwnd"])

        other = []
        for w in visible:
            if w["hwnd"] in used:
                continue
            w2 = dict(w)
            w2.pop("full_exe", None)
            other.append(w2)

        return triggered, other

    except Exception as e:
        print(f"[TRIGGER DAEMON] Workspace-app enumeration failed: {e}")
        import traceback
        traceback.print_exc()
        return [], []


# ─────────────────────────────────────────────────────────────────────────
# NAME-BASED MATCHING (legacy fallback)
# ─────────────────────────────────────────────────────────────────────────
def get_windows_for_arrange(app_names: list) -> tuple:
    """
    Strict name-based window matching.
    Only returns windows that clearly match — no weak fuzzy matches.
    """
    try:
        import win32gui
        import win32process
        import psutil

        visible = []

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            title_stripped = title.lower().strip() if title else ""
            if not title or title_stripped in _SKIP_TITLES_SET:
                return
            if "nvidia" in title_stripped and "overlay" in title_stripped:
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                proc = psutil.Process(pid)
                exe  = proc.name()
                if exe.lower() in _SKIP_EXE_SET:
                    return
                full_path = (proc.exe() or "").lower()
                if _is_seven_window(exe, full_path):
                    return
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if w < 100 or h < 100:
                        return
                except Exception:
                    pass
                visible.append({
                    "hwnd": hwnd, "title": title,
                    "exe": exe, "triggered": False,
                })
            except Exception:
                pass

        win32gui.EnumWindows(_cb, None)

        triggered = []
        used = set()

        for app_name in app_names:
            if not app_name:
                continue
            name_low = app_name.lower().strip()
            name_key = name_low.replace(".exe", "").replace(" ", "")

            best = None
            best_score = 0
            for w in visible:
                if w["hwnd"] in used:
                    continue
                title_low = w["title"].lower()
                exe_low   = w["exe"].lower().replace(".exe", "")

                score = 0
                if exe_low == name_key or exe_low.startswith(name_key) \
                        or name_key.startswith(exe_low):
                    score = 5
                elif name_low in title_low:
                    score = 4
                elif exe_low in title_low and len(exe_low) >= 4:
                    score = 3

                if score > best_score:
                    best_score = score
                    best = w

            if best and best_score >= 3:
                best = dict(best)
                best["triggered"] = True
                triggered.append(best)
                used.add(best["hwnd"])
                print(f"[TRIGGER DAEMON] Matched '{app_name}' -> "
                      f"'{best['title']}' (score={best_score})")
            else:
                print(f"[TRIGGER DAEMON] No match for '{app_name}'")

        other = [w for w in visible if w["hwnd"] not in used]
        return triggered, other

    except Exception as e:
        print(f"[TRIGGER DAEMON] Window enumeration failed: {e}")
        import traceback
        traceback.print_exc()
        return [], []