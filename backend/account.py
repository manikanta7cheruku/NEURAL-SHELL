"""
backend/account.py

One Seven account per Windows installation. The device ID is the Windows MachineGuid (telemetry.get_device_id), so
it survives reinstalling Seven. When setup starts on a PC that was used before, Seven finds that account and asks:
continue with it, or start fresh.

Two places can know about an earlier account:
    - this PC: conversations, facts, documents and tasks left in %APPDATA%\\SEVEN (uninstalling keeps them)
    - the Seven server: the device registration (name, email, plan), when online

Starting fresh never deletes: everything is copied to %APPDATA%\\SEVEN\\backups\\<date> first, then cleared. The plan
stays with the device, because a licence belongs to the machine, not to a person.
"""

import datetime
import logging
import os
import shutil
import sqlite3

_log = logging.getLogger("seven.account")
SERVER_URL = "https://seven-server-a825.onrender.com"


def _seven_data() -> str:
    if os.environ.get("SEVEN_KNOWLEDGE_DIR"):          # tests keep everything in a temporary folder
        return os.path.dirname(os.environ["SEVEN_KNOWLEDGE_DIR"])
    from seven_paths import paths
    return os.path.dirname(paths.knowledge_dir)


def _count(fn) -> int:
    try:
        return int(fn() or 0)
    except Exception:
        return 0


def _task_count() -> int:
    try:
        from backend.routes import tasks
        with sqlite3.connect(tasks.TASKS_DB) as conn:
            return conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    except Exception:
        return 0


def local_footprint() -> dict:
    """What an earlier user left on this PC."""
    from memory import conversation_store, facts_store
    from knowledge import store
    import config
    return {
        "name": (config.KEY.get("identity") or {}).get("user_name", "") or "",
        "email": config.KEY.get("email", "") or "",
        "conversations": _count(conversation_store.count_conversations),
        "facts": _count(facts_store.count_facts),
        "documents": len(store.documents()),
        "tasks": _task_count(),
    }


def server_record(timeout: float = 4.0) -> dict:
    """The device registration on the Seven server, or {} when offline or unknown."""
    if os.environ.get("SEVEN_TEST") == "1":
        return {}
    try:
        import requests
        import telemetry
        r = requests.get(f"{SERVER_URL}/api/device/{telemetry.get_device_id()}", timeout=timeout)
        if r.status_code == 200:
            data = r.json() or {}
            return {"name": data.get("name") or "", "email": data.get("email") or "",
                    "tier": data.get("tier") or data.get("plan") or ""}
    except Exception as exc:
        _log.info("server account check skipped: %s", exc)
    return {}


def existing() -> dict:
    """{found, name, email, tier, local: {...}, source} for the setup welcome screen."""
    local = local_footprint()
    used_here = any(local[k] for k in ("conversations", "facts", "documents", "tasks"))
    remote = server_record()
    name = local["name"] if local["name"] and local["name"] != "there" else remote.get("name", "")
    email = local["email"] or remote.get("email", "")
    if not (used_here or remote):
        return {"found": False}
    try:
        import config
        tier = remote.get("tier") or config.KEY.get("license", {}).get("tier", "free")
    except Exception:
        tier = remote.get("tier") or "free"
    return {"found": True, "name": name, "email": email, "tier": tier, "local": local,
            "source": "this_pc" if used_here else "server"}


def _copy_if_present(src, dst):
    """SQLite's -wal and -shm files come and go while Seven runs; one vanishing mid-copy is not an error."""
    try:
        return shutil.copy2(src, dst)
    except FileNotFoundError:
        return dst


def start_fresh() -> dict:
    """Back up this PC's Seven data, then clear it for a new person. Returns where the backup went."""
    data = _seven_data()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup = os.path.join(os.path.dirname(data), "backups", f"before-fresh-start_{stamp}")
    shutil.copytree(data, backup, ignore=shutil.ignore_patterns("*.tmp", "*.lock", "backups"),
                    copy_function=_copy_if_present, dirs_exist_ok=True)

    from backend.routes.memory import clear_all_memory
    clear_all_memory()
    from knowledge import store
    store.clear()
    try:
        from backend.routes import tasks
        with sqlite3.connect(tasks.TASKS_DB) as conn:
            conn.execute("DELETE FROM tasks")
    except Exception as exc:
        _log.warning("tasks not cleared: %s", exc)
    import config
    config.update_config({"identity": {**config.KEY.get("identity", {}), "user_name": ""}, "email": ""})
    return {"success": True, "backup": backup}
