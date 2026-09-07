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

    for entry in browser_entries:
        if entry in apps:
            apps.remove(entry)

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
        apps.append({
            "type":         browser_type,
            "name":         f"Chrome ({prof}) - {tab_count} "
                            f"tab{'s' if tab_count != 1 else ''}",
            "exe_path":     exe_path,
            "tabs":         clean,
            "profile_name": prof,
            "window":       {"title": f"Chrome - {prof}"},
        })
        print(Fore.CYAN + f"  Chrome profile '{prof}': {tab_count} tabs")

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