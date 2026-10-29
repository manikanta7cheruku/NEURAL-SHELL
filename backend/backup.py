"""
backend/backup.py
Backup and restore of everything that is yours in Seven: one JSON file.

    export_all()      the backup, as a dict
    import_all(data)  restore a backup; returns what was added and what was skipped

What is in it: facts (with the history of each), every saved chat with its messages, goals and what Seven learned,
reminders and alarms, tasks, triggers, workspaces, the commands you gave, and your settings. What is not: documents you
added to Knowledge (they are your own files; add them again), your licence and email, and settings tied to this PC
(the microphone, the AI model chosen, folders).

Restoring adds to what is already here and never replaces it, and it can be done twice: anything already present is
skipped. It goes through the same stores and plan limits as the app itself: reminders and triggers beyond the plan's
limit are not switched on (triggers are kept, turned off). Backups made by older versions (facts and chats as plain
lists) are read too.
"""
import datetime
import json
import os
import sqlite3
import threading

FORMAT = "seven-backup"
VERSION = 2

# Settings worth carrying to another PC, and the keys inside them that belong to this one.
_SECTIONS = ("voice", "brain", "interrupt", "web", "windows", "system", "scheduler", "privacy", "appearance",
             "updates", "voice_bar")
_THIS_PC = {"voice": {"mic"}, "brain": {"model_name", "model_tiers"}}
_IDENTITY_KEYS = ("wake_words", "pause_words", "resume_words", "shutdown_words")


def _owner() -> str:
    try:
        from brain_modules import session
        return session.resolve_key("default")
    except Exception:
        return "default"


def _limit(feature: str) -> int:
    """The plan's limit for a feature (-1 for none). If the plan can't be read, nothing is limited."""
    try:
        from backend.api_server import check_limit
        return check_limit(feature, 0).get("limit", -1)
    except Exception:
        return -1


def _settings() -> dict:
    import config
    out = {}
    for name in _SECTIONS:
        section = config.KEY.get(name)
        if isinstance(section, dict):
            out[name] = {k: v for k, v in section.items() if k not in _THIS_PC.get(name, ())}
    ident = config.KEY.get("identity", {})
    out["identity"] = {k: ident[k] for k in _IDENTITY_KEYS if k in ident}
    return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_all() -> dict:
    import config
    from seven_utils.version import get_version
    out = {
        "format": FORMAT, "version": VERSION, "exported_at": datetime.datetime.now().isoformat(),
        "app_version": get_version(), "owner": _owner(),
        "identity": {"name": config.KEY.get("identity", {}).get("user_name", "")},
        "settings": {}, "facts": [], "conversations": [], "learning": {}, "schedules": [], "tasks": [],
        "triggers": [], "workspaces": [], "commands": [], "warnings": [],
    }

    def part(name, fn):
        try:
            out[name] = fn()
        except Exception as exc:                          # one broken store never costs you the rest of the backup
            out["warnings"].append(f"{name}: {exc}")

    from memory import conversation_store, facts_store, learning_store
    from memory.command_log import command_log
    part("settings", _settings)
    part("facts", facts_store.export_rows)
    part("conversations", conversation_store.export_all)
    part("learning", learning_store.export_all)
    part("commands", command_log.export_entries)
    part("schedules", lambda: _schedules())
    part("tasks", lambda: _tasks())
    part("triggers", lambda: _triggers())
    part("workspaces", lambda: _workspaces())
    return out


def _schedules() -> list:
    from hands import scheduler
    return scheduler.get_all_schedules()


def _tasks() -> list:
    from backend.routes.tasks import TASKS_DB, _get_conn, _row_to_dict
    if not os.path.exists(TASKS_DB):
        return []
    with _get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()]


def _trigger_conn():
    from backend.routes.triggers import TRIGGERS_DB, init_db
    init_db()
    conn = sqlite3.connect(TRIGGERS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _triggers() -> list:
    conn = _trigger_conn()
    try:
        out = []
        for row in conn.execute("SELECT * FROM triggers ORDER BY id ASC").fetchall():
            d = dict(row)
            d["enabled"], d["silent"] = bool(d.get("enabled", 1)), bool(d.get("silent", 0))
            try:
                d["action_data"] = json.loads(d.get("action_data") or "{}")
            except Exception:
                d["action_data"] = {}
            out.append(d)
        return out
    finally:
        conn.close()


def _workspaces() -> list:
    conn = _trigger_conn()
    try:
        out = []
        for row in conn.execute("SELECT * FROM workspaces ORDER BY id ASC").fetchall():
            d = dict(row)
            try:
                d["apps"] = json.loads(d.get("apps") or "[]")
            except Exception:
                d["apps"] = []
            out.append(d)
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _legacy_conversation(pairs: list, owner: str) -> dict:
    """Older backups kept chats as {user, seven, timestamp} pairs: one chat from them."""
    msgs = []
    for p in pairs:
        if not isinstance(p, dict):
            continue
        user = (p.get("user") or p.get("user_input") or p.get("prompt") or p.get("input") or "").strip()
        seven = (p.get("seven") or p.get("seven_response") or p.get("response") or p.get("output") or "").strip()
        ts = p.get("timestamp")
        if user and seven:
            msgs.append({"role": "user", "content": user, "ts": ts})
            msgs.append({"role": "assistant", "content": seven, "ts": ts})
    if not msgs:
        return {}
    first = msgs[0]["ts"] or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"id": "imported-" + str(abs(hash(json.dumps(msgs[:4], sort_keys=True))) % 10 ** 10),
            "speaker_key": owner, "title": "Imported conversation", "created_at": first, "messages": msgs}


def import_all(data) -> dict:
    """Restore a backup. Raises ValueError if the file is not a Seven backup."""
    if not isinstance(data, dict) or not any(k in data for k in (
            "facts", "conversations", "schedules", "tasks", "triggers", "workspaces", "settings", "commands")):
        raise ValueError("That file is not a Seven backup.")
    if data.get("format") == FORMAT and int(data.get("version") or 0) > VERSION:
        raise ValueError("That backup was made by a newer Seven. Update Seven, then import it.")

    owner = _owner()
    theirs = data.get("owner")
    speaker_map = {theirs: owner} if theirs and theirs != owner else {}
    added: dict = {}
    skipped: dict = {}
    notes: list = []

    def run(name, fn):
        try:
            fn()
        except Exception as exc:
            notes.append(f"{name} could not be restored ({exc})")

    # facts
    def facts():
        from memory import facts_store
        rows = data.get("facts") or data.get("user_facts") or []
        norm = []
        for r in rows if isinstance(rows, list) else []:
            if isinstance(r, str):
                r = {"value": r}
            if isinstance(r, dict):
                r = dict(r)
                if "value" not in r:                                     # older backups: {text, category, timestamp}
                    r["value"] = r.get("text") or r.get("fact") or r.get("document") or ""
                    r["created_at"] = r.get("created_at") or r.get("timestamp")
                    r.setdefault("speaker_id", owner)
                norm.append(r)
        n, skip, live = facts_store.import_rows(norm, speaker_map)
        added["facts"], skipped["facts"] = n, skip
        if live:                                                         # the semantic index catches up in the background
            def reindex():
                from memory import fact_service
                for _ in range(60):
                    if not fact_service.reindex_pending(100):
                        break
            threading.Thread(target=reindex, daemon=True, name="BackupReindex").start()
    run("Facts", facts)

    # chats
    def chats():
        from memory import conversation_store
        raw = data.get("conversations") or data.get("history") or []
        convs = [c for c in raw if isinstance(c, dict) and isinstance(c.get("messages"), list)]
        legacy = [c for c in raw if isinstance(c, dict) and "messages" not in c]
        if legacy:
            convs.append(_legacy_conversation(legacy, owner))
        n = m = skip = 0
        for conv in filter(None, convs):
            restored = conversation_store.import_conversation(conv, speaker_map.get(conv.get("speaker_key"), conv.get("speaker_key") or owner))
            if restored:
                n += 1
                m += restored
            else:
                skip += 1
        added["conversations"], added["messages"], skipped["conversations"] = n, m, skip
    run("Chats", chats)

    # what Seven learned
    def learning():
        from memory import learning_store
        added["learning"] = learning_store.import_all(data.get("learning") or {}, speaker_map)
    if data.get("learning"):
        run("What Seven learned", learning)

    # reminders and alarms
    def schedules():
        from hands import scheduler
        n, skip, over = scheduler.import_schedules(data.get("schedules") or data.get("reminders") or [], _limit("schedules"))
        added["schedules"], skipped["schedules"] = n, skip
        if over:
            notes.append(f"{over} reminder{'s' if over != 1 else ''} not added: over your plan's limit")
    run("Reminders", schedules)

    # tasks
    def tasks():
        from backend.routes.tasks import _get_conn, init_db
        init_db()
        n = skip = 0
        with _get_conn() as conn:
            have = {(r[0], r[1], r[2]) for r in conn.execute("SELECT text, due_date, created_at FROM tasks").fetchall()}
            for t in data.get("tasks") or data.get("todos") or []:
                if not isinstance(t, dict) or not str(t.get("text") or "").strip():
                    continue
                text, created = str(t["text"]).strip(), t.get("created_at") or datetime.datetime.now().isoformat()
                if (text, t.get("due_date"), created) in have:
                    skip += 1
                    continue
                subtasks = t.get("subtasks") if isinstance(t.get("subtasks"), list) else []
                tags = t.get("tags")
                conn.execute(
                    "INSERT INTO tasks (text, due_date, due_time, priority, completed, created_at, completed_at, tags, "
                    "description, subtasks) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (text, t.get("due_date"), t.get("due_time"), t.get("priority", "medium"), 1 if t.get("completed") else 0,
                     created, t.get("completed_at"), ",".join(tags) if isinstance(tags, list) else (tags or ""),
                     t.get("description"), json.dumps(subtasks)))
                have.add((text, t.get("due_date"), created))
                n += 1
            conn.commit()
        added["tasks"], skipped["tasks"] = n, skip
    run("Tasks", tasks)

    # triggers
    def triggers():
        from backend.routes.triggers import _normalize_hotkey, _signal_daemon_reload
        limit = _limit("triggers")
        now = datetime.datetime.now().isoformat()
        n = skip = off = 0
        conn = _trigger_conn()
        try:
            rows = conn.execute("SELECT name, action_type, hotkey, voice_phrase, audio_pattern, enabled FROM triggers").fetchall()
            have = {(r["name"], r["action_type"], r["hotkey"], r["voice_phrase"], r["audio_pattern"]) for r in rows}
            active = sum(1 for r in rows if r["enabled"])
            hotkeys = {r["hotkey"] for r in rows if r["enabled"] and r["hotkey"]}
            phrases = {(r["voice_phrase"] or "").lower() for r in rows if r["enabled"] and r["voice_phrase"]}
            for t in data.get("triggers") or []:
                if not isinstance(t, dict) or not t.get("name") or not t.get("action_type"):
                    continue
                hotkey = _normalize_hotkey(t["hotkey"]) if t.get("hotkey") else None
                phrase = t["voice_phrase"].lower().strip() if t.get("voice_phrase") else None
                sig = (str(t["name"]).strip(), t["action_type"], hotkey, phrase, t.get("audio_pattern"))
                if sig in have:
                    skip += 1
                    continue
                # On, unless that would pass the plan's limit or take a hotkey or phrase another active trigger uses.
                wanted = bool(t.get("enabled", True))
                clash = (hotkey in hotkeys) or (phrase in phrases)
                on = wanted and not clash and (limit == -1 or active < limit)
                data_json = json.dumps(t.get("action_data") if isinstance(t.get("action_data"), dict) else {})
                try:
                    conn.execute(
                        "INSERT INTO triggers (name, action_type, action_data, hotkey, voice_phrase, audio_pattern, enabled, "
                        "silent, icon, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (sig[0], sig[1], data_json, hotkey, phrase, t.get("audio_pattern"), 1 if on else 0,
                         1 if t.get("silent") else 0, t.get("icon"), t.get("created_at") or now, now))
                except sqlite3.IntegrityError:
                    notes.append(f"Trigger \"{sig[0]}\" could not be restored")
                    continue
                have.add(sig)
                n += 1
                if on:
                    active += 1
                    if hotkey:
                        hotkeys.add(hotkey)
                    if phrase:
                        phrases.add(phrase)
                elif wanted:
                    off += 1
            conn.commit()
        finally:
            conn.close()
        added["triggers"], skipped["triggers"] = n, skip
        if off:
            notes.append(f"{off} trigger{'s' if off != 1 else ''} restored but turned off (plan limit or a shortcut already in use)")
        if n:
            _signal_daemon_reload()
    run("Triggers", triggers)

    # workspaces
    def workspaces():
        conn = _trigger_conn()
        n = skip = 0
        now = datetime.datetime.now().isoformat()
        try:
            have = {(r["name"], r["apps"]) for r in conn.execute("SELECT name, apps FROM workspaces").fetchall()}
            for w in data.get("workspaces") or []:
                if not isinstance(w, dict) or not w.get("name"):
                    continue
                apps = json.dumps(w.get("apps") if isinstance(w.get("apps"), list) else [])
                if (str(w["name"]).strip(), apps) in have:
                    skip += 1
                    continue
                conn.execute("INSERT INTO workspaces (name, description, apps, icon, created_at, updated_at, last_used, use_count) "
                             "VALUES (?,?,?,?,?,?,?,?)",
                             (str(w["name"]).strip(), w.get("description"), apps, w.get("icon"), w.get("created_at") or now,
                              w.get("updated_at") or now, w.get("last_used"), w.get("use_count") or 0))
                have.add((str(w["name"]).strip(), apps))
                n += 1
            conn.commit()
        finally:
            conn.close()
        added["workspaces"], skipped["workspaces"] = n, skip
    run("Workspaces", workspaces)

    # the commands you gave
    def commands():
        from memory.command_log import command_log
        added["commands"], skipped["commands"] = command_log.import_entries(data.get("commands") or [])
    if data.get("commands"):
        run("Command history", commands)

    # settings
    def settings():
        import config
        incoming = data.get("settings") or {}
        updates = {}
        for name in _SECTIONS:
            if isinstance(incoming.get(name), dict):
                updates[name] = {k: v for k, v in incoming[name].items() if k not in _THIS_PC.get(name, ())}
        ident = incoming.get("identity")
        if isinstance(ident, dict):
            updates["identity"] = {k: ident[k] for k in _IDENTITY_KEYS if k in ident}
        if updates and config.update_config(updates):
            added["settings"] = len(updates)
    if data.get("settings"):
        run("Settings", settings)

    try:                                   # short-term chat state may still hold what was there before
        import brain
        brain.reset_session()
    except Exception:
        pass

    return {"success": not notes or bool(added), "added": added, "skipped": skipped, "notes": notes,
            "message": _message(added, skipped, notes)}


def _message(added: dict, skipped: dict, notes: list) -> str:
    names = [("facts", "fact"), ("conversations", "chat"), ("schedules", "reminder"), ("tasks", "task"),
             ("triggers", "trigger"), ("workspaces", "workspace")]
    parts = [f"{added[k]} {label}{'s' if added[k] != 1 else ''}" for k, label in names if added.get(k)]
    if added.get("settings"):
        parts.append("your settings")
    text = ("Restored " + ", ".join(parts) + ".") if parts else "Nothing new to restore."
    dup = sum(skipped.values())
    if dup:
        text += f" {dup} already here, skipped."
    if notes:
        text += " " + "; ".join(notes) + "."
    return text
