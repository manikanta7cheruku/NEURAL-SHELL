"""
hands/workspace_modules/enrichment.py
Post-scan enrichment — Chrome tabs, VS Code workspace, Explorer paths.
"""
import os
import json
from colorama import Fore


def enrich_chrome(apps):
    """Replace raw browser entries with per-profile tab data from extension."""
    browser_entries = [a for a in apps if a.get("_is_browser")]
    if not browser_entries:
        return

    profile_tabs = {}
    try:
        from backend.routes.chrome import get_tabs_by_profile
        profile_tabs = get_tabs_by_profile()
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome extension: {e}")

    if not profile_tabs:
        for b in browser_entries:
            b["tabs"] = []
            b.pop("_is_browser", None)
        print(Fore.YELLOW + "[WORKSPACE] Chrome: extension not installed "
              "— tabs not captured")
        return

    browser_type = browser_entries[0].get("type", "chrome")
    exe_path     = browser_entries[0].get("exe_path", "")

    # Collect profile_dir and pid from original entries
    _pid_to_profile_dir = {}
    for b in browser_entries:
        pd = b.get("profile_dir", "")
        pid = b.get("pid", 0)
        if pd and pid:
            _pid_to_profile_dir[pid] = pd

    for entry in browser_entries:
        if entry in apps:
            apps.remove(entry)

    # Build on-disk profile database for smart pigeonhole allocation
    _chrome_base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    pdir_info = {}
    if os.path.exists(_chrome_base):
        try:
            for item in os.listdir(_chrome_base):
                if item == "Default" or item.startswith("Profile"):
                    prefs_path = os.path.join(_chrome_base, item, "Preferences")
                    if os.path.exists(prefs_path):
                        with open(prefs_path, "r", encoding="utf-8") as f:
                            prefs = json.loads(f.read())
                        emails = [acc.get("email", "").lower().strip() for acc in prefs.get("account_info", [])]
                        pname = (prefs.get("profile", {}).get("name") or "").lower().strip()
                        uname = (prefs.get("profile", {}).get("user_name") or "").lower().strip()
                        pdir_info[item] = {
                            "emails": emails,
                            "profile_name": pname,
                            "user_name": uname
                        }
        except Exception:
            pass

    # Pigeonhole Allocation Stage 1: Explicit match on emails/names
    pdir_matches = {}
    for prof in profile_tabs.keys():
        prof_lower = prof.lower().strip()
        matched_dir = None

        for pdir, info in pdir_info.items():
            if any(prof_lower == email or prof_lower == email.split("@")[0] for email in info["emails"]):
                matched_dir = pdir
                break
            if prof_lower == info["profile_name"] or prof_lower == info["user_name"] or prof_lower == info["user_name"].split("@")[0]:
                matched_dir = pdir
                break

        if matched_dir:
            pdir_matches[prof] = matched_dir

    # Pigeonhole Allocation Stage 2: Match remaining keys to unused open directories
    unmatched_keys = [k for k in profile_tabs.keys() if k not in pdir_matches]
    used_dirs = set(pdir_matches.values())
    open_dirs_unmatched = [d for d in _pid_to_profile_dir.values() if d not in used_dirs]

    for k in unmatched_keys:
        if open_dirs_unmatched:
            pdir_matches[k] = open_dirs_unmatched.pop(0)
        else:
            remaining_dirs = [d for d in pdir_info.keys() if d not in used_dirs and d not in pdir_matches.values()]
            if remaining_dirs:
                pdir_matches[k] = remaining_dirs[0]
            elif k.lower() == "default":
                pdir_matches[k] = "Default"
            else:
                pdir_matches[k] = "Default"

    total = 0
    for prof, tabs in profile_tabs.items():
        clean = [
            {
                "url":     t.get("url", ""),
                "title":   t.get("title", ""),
                "profile": prof,
                "pinned":  t.get("pinned", False),
            }
            for t in tabs
            if t.get("url", "") and
               not t["url"].startswith("chrome://") and
               not t["url"].startswith("chrome-extension://") and
               not t["url"].startswith("edge://")
        ]
        if not clean:
            continue
        total += len(clean)
        tab_count = len(clean)

        # Resolve correct profile_dir from our pigeonhole allocation matches
        _resolved_dir = pdir_matches.get(prof, "")

        # Fallback if somehow still unresolved
        if not _resolved_dir:
            _resolved_dir = "Default"

        apps.append({
            "type":         browser_type,
            "name":         f"Chrome ({prof}) - {tab_count} "
                            f"tab{'s' if tab_count != 1 else ''}",
            "exe_path":     exe_path,
            "tabs":         clean,
            "profile_name": prof,
            "profile_dir":  _resolved_dir,
            "window":       {"title": f"Chrome - {prof}"},
        })
        print(Fore.CYAN + f"  Chrome profile '{prof}': {tab_count} tabs (dir: {_resolved_dir})")

    print(Fore.GREEN + f"[WORKSPACE] Chrome: {total} tabs, "
          f"{len(profile_tabs)} profiles")


def enrich_vscode(apps):
    """Read VS Code workspace path from state.vscdb."""
    vscode_entries = [a for a in apps if a.get("type") == "vscode"]
    if not vscode_entries:
        return

    appdata = os.environ.get("APPDATA", "")
    db_path = os.path.join(appdata, "Code", "User", "globalStorage",
                           "state.vscdb")
    if not os.path.exists(db_path):
        return

    try:
        import sqlite3
        from urllib.parse import unquote
        conn = sqlite3.connect(db_path, timeout=2)
        row  = conn.execute(
            "SELECT value FROM ItemTable "
            "WHERE key = 'history.recentlyOpenedPathsList'"
        ).fetchone()
        conn.close()

        if row:
            entries = json.loads(row[0]).get("entries", [])
            if entries:
                ws = entries[0].get("folderUri", "")
                ws = ws.replace("file:///", "").replace("/", "\\")
                ws = unquote(ws)
                if len(ws) >= 2 and ws[1] == ":":
                    ws = ws[0].upper() + ws[1:]
                for v in vscode_entries:
                    v["workspace_path"] = ws
                    v["name"] = "Visual Studio Code"
                print(Fore.CYAN + f"[WORKSPACE] VS Code: {ws}")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] VS Code state: {e}")


def enrich_explorer(apps):
    """Get Explorer window paths via Shell COM."""
    explorers = [a for a in apps if a.get("type") == "explorer"]
    if not explorers:
        return

    try:
        import win32com.client
        from urllib.parse import unquote

        shell   = win32com.client.Dispatch("Shell.Application")
        windows = shell.Windows()
        folders = []

        for i in range(windows.Count):
            try:
                w = windows.Item(i)
                if not w:
                    continue
                url  = w.LocationURL or ""
                loc  = w.LocationName or ""
                path = ""

                if url:
                    path = unquote(
                        url.replace("file:///", "").replace("/", "\\")
                    )
                    if len(path) >= 2 and path[1] == ":":
                        path = path[0].upper() + path[1:]

                if path or loc:
                    folders.append({"path": path, "name": loc})

            except Exception:
                continue

        for i, exp in enumerate(explorers):
            if i < len(folders):
                f = folders[i]
                if f["path"]:
                    exp["folder_path"] = f["path"]
                if f["name"]:
                    exp["name"] = f"File Explorer: {f['name']}"
                print(Fore.CYAN + f"[WORKSPACE] Explorer: "
                      f"{f['path']} ({f['name']})")
            else:
                print(Fore.YELLOW + "[WORKSPACE] Explorer: "
                      "could not get path from Shell COM")

    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Explorer enrichment failed: {e}")