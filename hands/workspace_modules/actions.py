"""
hands/workspace_modules/actions.py

Saving and restoring workspaces from anywhere (chat, voice, triggers), with the status card at the top of the
screen telling the user what is happening and what came of it:

    "Scanning your workspace"  ->  "Saved Study · 9 apps · 37 tabs"
    "Restoring Study"          ->  "Study is back · 4 opened, 6 already open"

Saving under a name that exists replaces that workspace, so "save my workspace as Study" keeps Study current.
"""

import json
import threading
from datetime import datetime
from typing import Dict, Optional

from colorama import Fore


def _card(title: str, subtitle: str = ""):
    try:
        from seven_overlay.notifications import progress
        return progress(title, subtitle)
    except Exception:
        class _Silent:
            def done(self, *a):
                pass

            def fail(self, *a):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return _Silent()


def default_name() -> str:
    now = datetime.now()
    return f"Workspace {now.strftime('%b')} {now.day}, {now.strftime('%I:%M %p').lstrip('0')}"


def summarize(apps) -> Dict[str, int]:
    tabs = sum(len(a.get("tabs") or []) for a in apps)
    docs = sum(len(a.get("open_files") or []) for a in apps)
    return {"apps": len(apps), "tabs": tabs, "documents": docs,
            "tabs_without_url": sum(a.get("tabs_without_url", 0) for a in apps)}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def save_current(name: Optional[str] = None) -> Dict:
    """Scan what is open now and save it. Returns {"ok", "name", "id", "apps", "tabs", ...}."""
    name = (name or "").strip()
    name = name[0].upper() + name[1:] if name else default_name()
    with _card("Scanning your workspace", "Windows, tabs and documents") as card:
        from hands.workspace_modules.scanner import scan_current
        apps = scan_current()
        if not apps:
            card.fail("Nothing to save", "Open the apps you work with, then ask again")
            return {"ok": False, "name": name, "reason": "nothing open"}

        from backend.routes.workspaces import _get_conn
        now = datetime.now().isoformat()
        stats = summarize(apps)
        description = f"{_plural(stats['apps'], 'app')}, {_plural(stats['tabs'], 'tab')}"
        with _get_conn() as conn:
            row = conn.execute("SELECT id FROM workspaces WHERE LOWER(name) = ?", (name.lower(),)).fetchone()
            if row:
                conn.execute("UPDATE workspaces SET apps = ?, description = ?, updated_at = ? WHERE id = ?",
                             (json.dumps(apps), description, now, row["id"]))
                ws_id, replaced = row["id"], True
            else:
                ws_id = conn.execute("INSERT INTO workspaces (name, description, apps, created_at, updated_at) "
                                     "VALUES (?, ?, ?, ?, ?)", (name, description, json.dumps(apps), now, now)).lastrowid
                replaced = False
            conn.commit()

        detail = _plural(stats["tabs"], "tab") if stats["tabs"] else ""
        card.done(f"Saved {name}", _plural(stats["apps"], "app") + (", updated" if replaced else ""), detail)
        print(Fore.GREEN + f"[WORKSPACE] Saved '{name}' (#{ws_id}): {description}")
        return {"ok": True, "name": name, "id": ws_id, "replaced": replaced, **stats}


def restore(workspace: Dict, wait: bool = False) -> Dict:
    """Bring a saved workspace back, opening only what is not already open. Runs in the background unless wait."""
    name, apps = workspace.get("name", "Workspace"), workspace.get("apps") or []
    result = {"ok": True, "name": name, "apps": len(apps)}

    def _run():
        with _card(f"Restoring {name}", "Opening only what isn't open yet") as card:
            from hands.workspace_modules.restore import smart_restore
            opened, already = smart_restore(apps)
            result.update(opened=opened, already_open=already)
            if opened:
                card.done(f"{name} is back", f"{opened} opened", f"{already} already open" if already else "")
            else:
                card.done(f"{name} is already open", "Nothing needed opening")

    if wait:
        _run()
    else:
        threading.Thread(target=_run, name="seven-workspace-restore", daemon=True).start()
    return result
