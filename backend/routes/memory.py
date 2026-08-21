"""
backend/routes/memory.py
Handles: all /api/memory/* endpoints
"""

from fastapi import APIRouter, HTTPException, Request
import os
import datetime
import logging

_log = logging.getLogger('seven.memory')

router = APIRouter()


@router.post("/api/memory/facts")
def add_manual_fact(data: dict):
    """Manually add a fact. Enforces plan limit."""
    from memory import seven_memory
    from backend.api_server import check_limit, plan_limit_error

    text     = data.get("text", "").strip()
    category = data.get("category", "manual")

    if not text:
        raise HTTPException(status_code=400, detail="Empty fact text")

    try:
        all_facts     = seven_memory.user_facts.get()
        current_count = len(all_facts["documents"]) if all_facts and all_facts.get("documents") else 0
    except Exception:
        current_count = 0

    limit_check = check_limit("facts_limit", current_count)
    if not limit_check["allowed"]:
        raise plan_limit_error("facts_limit", limit_check)

    try:
        seven_memory.store_fact(text, category=category)
        return {
            "success": True,
            "fact": text,
            "usage": {
                "current": current_count + 1,
                "limit":   limit_check["limit"],
                "tier":    limit_check["tier"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/facts")
def get_facts():
    """Get all stored facts."""

    # Try via ChromaDB singleton first
    try:
        from memory import seven_memory
        all_facts = seven_memory.user_facts.get()
        if not all_facts or not all_facts['documents']:
            return []

        facts = []
        for i in range(len(all_facts['documents'])):
            facts.append({
                "id":        all_facts['ids'][i],
                "text":      all_facts['documents'][i],
                "category":  all_facts['metadatas'][i].get("category", "general"),
                "timestamp": all_facts['metadatas'][i].get("timestamp", ""),
                "speaker":   all_facts['metadatas'][i].get("user_id", "default")
            })
        return facts

    except Exception as _chroma_err:
        _log.debug(f"[API] Facts via ChromaDB using fallback: {type(_chroma_err).__name__}")

    # Fallback: read directly from SQLite
    try:
        import sqlite3 as _sq
        from memory.core import MEMORY_DIR as _mdir

        _db = os.path.join(_mdir, "chroma.sqlite3")
        if not os.path.exists(_db):
            return []

        _conn = _sq.connect(_db, timeout=5)

        _facts_row = _conn.execute(
            "SELECT id FROM collections WHERE name = 'user_facts'"
        ).fetchone()
        if not _facts_row:
            _conn.close()
            return []

        _facts_cid = _facts_row[0]
        _seg_rows = _conn.execute(
            "SELECT id FROM segments WHERE collection = ? AND scope = 'METADATA'",
            (_facts_cid,)
        ).fetchall()
        _seg_ids = [r[0] for r in _seg_rows]
        if not _seg_ids:
            _conn.close()
            return []
        _placeholders = ",".join("?" * len(_seg_ids))
        _emb_rows = _conn.execute(
            f"SELECT id, embedding_id FROM embeddings WHERE segment_id IN ({_placeholders})",
            _seg_ids
        ).fetchall()

        facts = []
        for _emb_id, _emb_uuid in _emb_rows:
            _meta_rows = _conn.execute(
                "SELECT key, string_value FROM embedding_metadata WHERE id = ?",
                (_emb_id,)
            ).fetchall()
            meta = {row[0]: row[1] for row in _meta_rows}

            _doc_row = _conn.execute(
                "SELECT c0 FROM embedding_fulltext_search_content WHERE rowid = ?",
                (_emb_id,)
            ).fetchone()
            doc_text = _doc_row[0] if _doc_row else ""

            facts.append({
                "id":        _emb_uuid,
                "text":      doc_text,
                "category":  meta.get("category", "general"),
                "timestamp": meta.get("timestamp", ""),
                "speaker":   meta.get("user_id", "default"),
            })

        _conn.close()
        _log.debug(f"[API] Facts via SQLite fallback: {len(facts)} records")
        return facts

    except Exception as _sq_err:
        _log.warning(f"[API] Facts SQLite fallback failed: {_sq_err}")
        raise HTTPException(status_code=500, detail=str(_sq_err))


@router.delete("/api/memory/facts/{fact_id}")
def delete_fact(fact_id: str):
    """Delete a specific fact."""
    from memory import seven_memory
    try:
        seven_memory.user_facts.delete(ids=[fact_id])
        return {"success": True, "deleted": fact_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/conversations", summary="Get conversation history",
            description="Returns paginated conversation history from ChromaDB. Falls back to direct SQLite read if ChromaDB singleton fails (numpy/tensorflow conflict). Each record includes user_input, seven_response, timestamp, source (chat or voice).")
def get_conversations(limit: int = 500, offset: int = 0):
    """Get stored conversations (paginated)."""

    # Try via ChromaDB singleton first
    try:
        from memory import seven_memory
        all_convos = seven_memory.conversations.get()
        if not all_convos or not all_convos['documents']:
            return {"conversations": [], "total": 0}

        convos = []
        for i in range(len(all_convos['documents'])):
            convos.append({
                "id":             all_convos['ids'][i],
                "text":           all_convos['documents'][i],
                "timestamp":      all_convos['metadatas'][i].get("timestamp", ""),
                "user_input":     all_convos['metadatas'][i].get("user_input", ""),
                "seven_response": all_convos['metadatas'][i].get("seven_response", ""),
                "speaker":        all_convos['metadatas'][i].get("user_id", "default"),
                "source":         all_convos['metadatas'][i].get("source", "chat"),
            })

        convos.sort(key=lambda x: x["timestamp"], reverse=True)
        total     = len(convos)
        paginated = convos[offset:offset + limit]
        return {"conversations": paginated, "total": total}

    except Exception as _chroma_err:
        _log.debug(f"[API] Conversations via ChromaDB using fallback: {type(_chroma_err).__name__}")

    # Fallback: read directly from SQLite without embedding model
    try:
        import sqlite3 as _sq
        from memory.core import MEMORY_DIR as _mdir

        _db = os.path.join(_mdir, "chroma.sqlite3")
        if not os.path.exists(_db):
            return {"conversations": [], "total": 0}

        _conn = _sq.connect(_db, timeout=5)

        # Get conversations collection ID
        _conv_row = _conn.execute(
            "SELECT id FROM collections WHERE name = 'conversations'"
        ).fetchone()
        if not _conv_row:
            _conn.close()
            return {"conversations": [], "total": 0}
        _conv_col_id = _conv_row[0]

        # Get segment IDs that belong to conversations collection
        # metadata segments have scope = METADATA
        _seg_rows = _conn.execute(
            "SELECT id FROM segments WHERE collection = ? AND scope = 'METADATA'",
            (_conv_col_id,)
        ).fetchall()
        _seg_ids = [r[0] for r in _seg_rows]

        if not _seg_ids:
            _conn.close()
            return {"conversations": [], "total": 0}

        # Get all embeddings in those segments
        _placeholders = ",".join("?" * len(_seg_ids))
        _emb_rows = _conn.execute(
            f"SELECT id, embedding_id FROM embeddings WHERE segment_id IN ({_placeholders})",
            _seg_ids
        ).fetchall()

        convos = []
        for _emb_id, _emb_uuid in _emb_rows:
            _meta_rows = _conn.execute(
                "SELECT key, string_value FROM embedding_metadata WHERE id = ?",
                (_emb_id,)
            ).fetchall()
            meta = {row[0]: row[1] for row in _meta_rows}

            _doc_row = _conn.execute(
                "SELECT c0 FROM embedding_fulltext_search_content WHERE rowid = ?",
                (_emb_id,)
            ).fetchone()
            doc_text = _doc_row[0] if _doc_row else ""

            convos.append({
                "id":             _emb_uuid,
                "text":           doc_text,
                "timestamp":      meta.get("timestamp", ""),
                "user_input":     meta.get("user_input", ""),
                "seven_response": meta.get("seven_response", ""),
                "speaker":        meta.get("user_id", "default"),
                "source":         meta.get("source", "chat"),
            })

        _conn.close()
        convos.sort(key=lambda x: x["timestamp"], reverse=True)
        total     = len(convos)
        paginated = convos[offset:offset + limit]
        _log.debug(f"[API] Conversations via SQLite fallback: {total} records")
        return {"conversations": paginated, "total": total}

    except Exception as _sq_err:
        _log.warning(f"[API] Conversations SQLite fallback failed: {_sq_err}")
        raise HTTPException(status_code=500, detail=str(_sq_err))


@router.delete("/api/memory/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a specific conversation."""
    from memory import seven_memory
    try:
        seven_memory.conversations.delete(ids=[conv_id])
        return {"success": True, "deleted": conv_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/export")
def export_memory():
    """
    Export ALL user data as JSON for backup.
    Includes: facts, conversations, schedules, tasks, triggers, workspaces.
    """
    import sqlite3
    import json
    import config as cfg
    from memory.core import MEMORY_DIR

    export = {
        "exported_at": datetime.datetime.now().isoformat(),
        "version":     "1.3.1",
        "identity": {
            "name":  cfg.KEY.get("identity", {}).get("user_name", ""),
            "email": cfg.KEY.get("email", ""),
        },
        "facts":         [],
        "conversations": [],
        "schedules":     [],
        "tasks":         [],
        "triggers":      [],
        "workspaces":    [],
        "usage":         {}
    }

    # 1. Facts
    try:
        from memory import seven_memory
        all_facts = seven_memory.user_facts.get()
        if all_facts and all_facts.get('documents'):
            for i, doc in enumerate(all_facts['documents']):
                meta = all_facts['metadatas'][i] if all_facts.get('metadatas') else {}
                export["facts"].append({
                    "text":     doc,
                    "category": meta.get("category", "general")
                })
    except Exception as e:
        export["facts_error"] = str(e)

    # 2. Conversations
    try:
        from memory import seven_memory
        all_convos = seven_memory.conversations.get()
        if all_convos and all_convos.get('documents'):
            for i, doc in enumerate(all_convos['documents']):
                meta = all_convos['metadatas'][i] if all_convos.get('metadatas') else {}
                user_input     = meta.get("user_input", "")
                seven_response = meta.get("seven_response", doc)
                if user_input and seven_response:
                    export["conversations"].append({
                        "user":  user_input,
                        "seven": seven_response
                    })
    except Exception:
        try:
            import sqlite3 as _sq
            _db = os.path.join(MEMORY_DIR, "chroma.sqlite3")
            if os.path.exists(_db):
                _conn = _sq.connect(_db, timeout=5)
                _conv_row = _conn.execute(
                    "SELECT id FROM collections WHERE name = 'conversations'"
                ).fetchone()
                if _conv_row:
                    _seg_ids = [r[0] for r in _conn.execute(
                        "SELECT id FROM segments WHERE collection = ? AND scope = 'METADATA'",
                        (_conv_row[0],)
                    ).fetchall()]
                    if _seg_ids:
                        _ph = ",".join("?" * len(_seg_ids))
                        _emb_rows = _conn.execute(
                            f"SELECT id FROM embeddings WHERE segment_id IN ({_ph})",
                            _seg_ids
                        ).fetchall()
                        for (_emb_id,) in _emb_rows:
                            _meta = {
                                r[0]: r[1] for r in _conn.execute(
                                    "SELECT key, string_value FROM embedding_metadata WHERE id=?",
                                    (_emb_id,)
                                ).fetchall()
                            }
                            user_in  = _meta.get("user_input", "")
                            seven_r  = _meta.get("seven_response", "")
                            if user_in and seven_r:
                                export["conversations"].append({
                                    "user":  user_in,
                                    "seven": seven_r
                                })
                _conn.close()
        except Exception as _se:
            export["conversations_error"] = str(_se)

    # 3. Schedules
    try:
        _appdata = os.environ.get('APPDATA', '')
        _sched_path = os.path.join(_appdata, 'SEVEN', 'schedules.json')
        if os.path.exists(_sched_path):
            with open(_sched_path, 'r', encoding='utf-8') as _f:
                export["schedules"] = json.load(_f) if _f else []
    except Exception as _e:
        export["schedules_error"] = str(_e)

    # 4. Tasks
    try:
        from backend.routes.tasks import TASKS_DB, _get_conn, _row_to_dict as _task_row
        if os.path.exists(TASKS_DB):
            with _get_conn() as conn:
                rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
                export["tasks"] = [_task_row(r) for r in rows]
    except Exception as _e:
        export["tasks_error"] = str(_e)

    # 5. Triggers
    try:
        from backend.routes.triggers import TRIGGERS_DB
        if os.path.exists(TRIGGERS_DB):
            conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM triggers ORDER BY id ASC").fetchall()
            for row in rows:
                d = dict(row)
                d["enabled"] = bool(d.get("enabled", 1))
                d["silent"]  = bool(d.get("silent", 0))
                try:
                    d["action_data"] = json.loads(d.get("action_data") or "{}")
                except Exception:
                    d["action_data"] = {}
                export["triggers"].append(d)
            conn.close()
    except Exception as _e:
        export["triggers_error"] = str(_e)

    # 6. Workspaces
    try:
        from backend.routes.triggers import TRIGGERS_DB
        if os.path.exists(TRIGGERS_DB):
            conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM workspaces ORDER BY id ASC").fetchall()
            for row in rows:
                d = dict(row)
                try:
                    d["apps"] = json.loads(d.get("apps") or "[]")
                except Exception:
                    d["apps"] = []
                export["workspaces"].append(d)
            conn.close()
    except Exception as _e:
        export["workspaces_error"] = str(_e)

    # 7. Telemetry / Usage
    try:
        db_path = os.path.join(
            os.environ.get("APPDATA", ""), "SEVEN", "data", "telemetry.db"
        )
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            c    = conn.cursor()
            c.execute("SELECT active_hours, last_seen FROM stats LIMIT 1")
            row = c.fetchone()
            if row:
                mins = int((row[0] or 0) * 60)
                export["usage"] = {
                    "total_minutes": mins,
                    "last_seen":     row[1]
                }
            conn.close()
    except Exception:
        pass

    return export

@router.delete("/api/memory/clear", summary="Clear all facts and conversations",
               description="Permanently deletes all stored facts and conversation history from ChromaDB and resets brain session state.")
def clear_all_memory():
    """Clear all facts, conversations, and reset brain session state."""
    try:
        from memory import seven_memory
        if seven_memory:
            seven_memory.clear_all()

        try:
            import brain
            brain.reset_session()
        except Exception as _be:
            _log.debug(f"[API] Brain session reset skipped: {_be}")

        return {"success": True, "message": "All facts and conversations cleared successfully"}
    except Exception as e:
        _log.error(f"[API] Clear memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory/import")
async def import_memory(request: Request):
    """Import ALL user data from backup JSON. Auto-patches DB schema on the fly."""
    try:
        import json
        import sqlite3
        import uuid
        import datetime

        data = await request.json()

        # Ensure ChromaDB memory system is ready
        import time as _t
        _deadline = _t.time() + 10
        seven_memory = None
        while _t.time() < _deadline:
            try:
                from memory import seven_memory as _sm
                if _sm is not None:
                    _sm.user_facts.count()
                    seven_memory = _sm
                    break
            except Exception:
                pass
            _t.sleep(0.3)

        imported = {
            "facts": 0, "conversations": 0, "schedules": 0,
            "tasks": 0, "triggers": 0, "workspaces": 0
        }

        # ── 1. FACTS ──
        raw_facts = data.get("facts") or data.get("user_facts") or []
        if seven_memory and isinstance(raw_facts, list):
            for item in raw_facts:
                text = ""
                cat = "imported"
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = (item.get("text") or item.get("fact") or item.get("document") or "").strip()
                    cat = item.get("category", "imported")
                if text:
                    try:
                        seven_memory.user_facts.add(
                            documents=[text],
                            metadatas=[{
                                "category": cat,
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "user_id": "default",
                                "type": "fact"
                            }],
                            ids=[f"fact_import_{uuid.uuid4().hex}"]
                        )
                        imported["facts"] += 1
                    except Exception as e:
                        print(f"[IMPORT] Fact import error: {e}")

        # ── 2. CONVERSATIONS ──
        raw_convos = data.get("conversations") or data.get("history") or []
        if seven_memory and isinstance(raw_convos, list):
            for item in raw_convos:
                user_txt = ""
                seven_txt = ""
                if isinstance(item, dict):
                    user_txt = (item.get("user") or item.get("user_input") or item.get("prompt") or item.get("input") or "").strip()
                    seven_txt = (item.get("seven") or item.get("seven_response") or item.get("response") or item.get("output") or "").strip()
                if user_txt and seven_txt:
                    try:
                        combined = f"User said: {user_txt} | Seven replied: {seven_txt}"
                        seven_memory.conversations.add(
                            documents=[combined],
                            metadatas=[{
                                "user_input": user_txt,
                                "seven_response": seven_txt,
                                "timestamp": item.get("timestamp") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "user_id": item.get("speaker") or "default",
                                "type": "conversation",
                                "source": item.get("source") or "import"
                            }],
                            ids=[f"conv_import_{uuid.uuid4().hex}"]
                        )
                        imported["conversations"] += 1
                    except Exception as e:
                        print(f"[IMPORT] Convo import error: {e}")

        # ── 3. SCHEDULES ──
        raw_scheds = data.get("schedules") or data.get("reminders") or []
        if isinstance(raw_scheds, list) and raw_scheds:
            try:
                _appdata = os.environ.get('APPDATA', '')
                _sched_path = os.path.join(_appdata, 'SEVEN', 'schedules.json')
                os.makedirs(os.path.dirname(_sched_path), exist_ok=True)
                _existing = []
                if os.path.exists(_sched_path):
                    try:
                        with open(_sched_path, 'r', encoding='utf-8') as _f:
                            _existing = json.load(_f)
                    except Exception:
                        _existing = []

                _existing_ids = {s.get('id') for s in _existing if isinstance(s, dict)}
                _max_id = max([_id for _id in _existing_ids if isinstance(_id, int)] or [0])

                for item in raw_scheds:
                    if isinstance(item, dict) and item.get("message"):
                        _max_id += 1
                        item["id"] = _max_id
                        _existing.append(item)
                        imported["schedules"] += 1

                with open(_sched_path, 'w', encoding='utf-8') as _f:
                    json.dump(_existing, _f, indent=2)
            except Exception as e:
                print(f"[IMPORT] Schedules error: {e}")

        # Helper to dynamically patch missing schema columns
        def _ensure_column(conn, table, column, definition):
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                print(f"[IMPORT] Patched schema: Added {column} to {table}")
            except Exception:
                pass  # Column already exists

        # ── 4. TASKS ──
        raw_tasks = data.get("tasks") or data.get("todos") or []
        if isinstance(raw_tasks, list) and raw_tasks:
            try:
                from backend.routes.tasks import TASKS_DB, init_db as init_tasks_db
                init_tasks_db()
                if os.path.exists(TASKS_DB):
                    conn = sqlite3.connect(TASKS_DB, timeout=10)
                    conn.execute("PRAGMA journal_mode=WAL")
                    
                    # Auto-patch missing columns for older databases
                    _ensure_column(conn, "tasks", "description", "TEXT")
                    _ensure_column(conn, "tasks", "subtasks", "TEXT DEFAULT '[]'")
                    _ensure_column(conn, "tasks", "tags", "TEXT")

                    for item in raw_tasks:
                        if isinstance(item, dict) and item.get("text"):
                            try:
                                subtasks_data = item.get("subtasks") or []
                                subtasks_str = json.dumps(subtasks_data if isinstance(subtasks_data, list) else [])
                                tags_raw = item.get("tags")
                                tags_str = ",".join(tags_raw) if isinstance(tags_raw, list) else (tags_raw or "")
                                conn.execute(
                                    "INSERT INTO tasks (text, due_date, due_time, priority, "
                                    "completed, created_at, completed_at, tags, description, subtasks) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (
                                        str(item.get("text", "")).strip(),
                                        item.get("due_date"),
                                        item.get("due_time"),
                                        item.get("priority", "medium"),
                                        1 if item.get("completed") else 0,
                                        item.get("created_at") or datetime.datetime.now().isoformat(),
                                        item.get("completed_at"),
                                        tags_str,
                                        item.get("description"),
                                        subtasks_str
                                    )
                                )
                                imported["tasks"] += 1
                            except Exception as te:
                                print(f"[IMPORT] Single task error: {te}")
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[IMPORT] Tasks error: {e}")

        # ── 5. TRIGGERS ──
        raw_trigs = data.get("triggers") or []
        if isinstance(raw_trigs, list) and raw_trigs:
            try:
                from backend.routes.triggers import TRIGGERS_DB, init_db as init_trig_db
                init_trig_db()
                if os.path.exists(TRIGGERS_DB):
                    conn = sqlite3.connect(TRIGGERS_DB, timeout=10)
                    conn.execute("PRAGMA journal_mode=WAL")
                    
                    # Auto-patch missing columns for older databases
                    _ensure_column(conn, "triggers", "audio_pattern", "TEXT")
                    _ensure_column(conn, "triggers", "silent", "INTEGER DEFAULT 0")
                    _ensure_column(conn, "triggers", "icon", "TEXT")
                    _ensure_column(conn, "triggers", "last_fired", "TEXT")
                    _ensure_column(conn, "triggers", "fire_count", "INTEGER DEFAULT 0")

                    now_iso = datetime.datetime.now().isoformat()
                    for item in raw_trigs:
                        if isinstance(item, dict) and item.get("name") and item.get("action_type"):
                            try:
                                action_data = item.get("action_data") or {}
                                action_data_str = json.dumps(action_data if isinstance(action_data, dict) else {})
                                conn.execute(
                                    "INSERT INTO triggers (name, action_type, action_data, hotkey, "
                                    "voice_phrase, audio_pattern, enabled, silent, icon, created_at, updated_at) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (
                                        str(item.get("name", "")).strip(),
                                        str(item.get("action_type")),
                                        action_data_str,
                                        item.get("hotkey"),
                                        item.get("voice_phrase"),
                                        item.get("audio_pattern"),
                                        1 if item.get("enabled", True) else 0,
                                        1 if item.get("silent", False) else 0,
                                        item.get("icon"),
                                        item.get("created_at", now_iso),
                                        item.get("updated_at", now_iso)
                                    )
                                )
                                imported["triggers"] += 1
                            except Exception as tre:
                                print(f"[IMPORT] Single trigger error: {tre}")
                    conn.commit()
                    conn.close()
                    try:
                        from backend.routes.triggers import _signal_daemon_reload
                        _signal_daemon_reload()
                    except Exception:
                        pass
            except Exception as e:
                print(f"[IMPORT] Triggers error: {e}")

        # ── 6. WORKSPACES ──
        raw_ws = data.get("workspaces") or []
        if isinstance(raw_ws, list) and raw_ws:
            try:
                from backend.routes.triggers import TRIGGERS_DB, init_db as init_trig_db
                init_trig_db()
                if os.path.exists(TRIGGERS_DB):
                    conn = sqlite3.connect(TRIGGERS_DB, timeout=10)
                    conn.execute("PRAGMA journal_mode=WAL")
                    
                    # Auto-patch missing columns for older databases
                    _ensure_column(conn, "workspaces", "description", "TEXT")
                    _ensure_column(conn, "workspaces", "icon", "TEXT")
                    _ensure_column(conn, "workspaces", "last_used", "TEXT")
                    _ensure_column(conn, "workspaces", "use_count", "INTEGER DEFAULT 0")

                    now_iso = datetime.datetime.now().isoformat()
                    for item in raw_ws:
                        if isinstance(item, dict) and item.get("name"):
                            try:
                                apps_data = item.get("apps") or []
                                apps_str = json.dumps(apps_data if isinstance(apps_data, list) else [])
                                conn.execute(
                                    "INSERT INTO workspaces (name, description, apps, icon, created_at, updated_at) "
                                    "VALUES (?, ?, ?, ?, ?, ?)",
                                    (
                                        str(item.get("name", "")).strip(),
                                        item.get("description"),
                                        apps_str,
                                        item.get("icon"),
                                        item.get("created_at", now_iso),
                                        item.get("updated_at", now_iso)
                                    )
                                )
                                imported["workspaces"] += 1
                            except Exception as wse:
                                print(f"[IMPORT] Single workspace error: {wse}")
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[IMPORT] Workspaces error: {e}")

        total = sum(imported.values())
        return {
            "success": True,
            "imported_facts":         imported["facts"],
            "imported_conversations": imported["conversations"],
            "imported_schedules":     imported["schedules"],
            "imported_tasks":         imported["tasks"],
            "imported_triggers":      imported["triggers"],
            "imported_workspaces":    imported["workspaces"],
            "message": f"Imported {total} items: "
                       f"{imported['facts']} facts, "
                       f"{imported['conversations']} convos, "
                       f"{imported['schedules']} schedules, "
                       f"{imported['tasks']} tasks, "
                       f"{imported['triggers']} triggers, "
                       f"{imported['workspaces']} workspaces"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/memory/stats", summary="Memory statistics",
            description="Returns count of stored conversations and facts, storage size in MB, and current license tier. Uses SQLite fallback if ChromaDB unavailable.")
def get_memory_stats():
    """Get memory statistics including storage size."""
    stats = {"total_conversations": 0, "total_facts": 0, "storage_path": ""}

    # Try live ChromaDB count via singleton first
    try:
        from memory import seven_memory
        stats = seven_memory.get_stats()
    except Exception as e:
        _log.debug(f"[API] Memory stats via ChromaDB using fallback: {type(e).__name__}")
        try:
            import sqlite3 as _sq
            from memory.core import MEMORY_DIR as _mdir
            _db = os.path.join(_mdir, "chroma.sqlite3")
            if os.path.exists(_db):
                _conn = _sq.connect(_db, timeout=5)
                _collections = {}
                for row in _conn.execute(
                    "SELECT id, name FROM collections"
                ).fetchall():
                    _collections[row[0]] = row[1]
                for _cid, _cname in _collections.items():
                    _seg_ids = [r[0] for r in _conn.execute(
                        "SELECT id FROM segments WHERE collection = ? AND scope = 'METADATA'",
                        (_cid,)
                    ).fetchall()]
                    if _seg_ids:
                        _ph = ",".join("?" * len(_seg_ids))
                        _count = _conn.execute(
                            f"SELECT COUNT(*) FROM embeddings WHERE segment_id IN ({_ph})",
                            _seg_ids
                        ).fetchone()[0]
                    else:
                        _count = 0
                    if _cname == "conversations":
                        stats["total_conversations"] = _count
                    elif _cname == "user_facts":
                        stats["total_facts"] = _count
                _conn.close()
                stats["storage_path"] = _mdir
                _log.debug(f"[API] Memory stats via SQLite fallback: {stats}")
        except Exception as _sq_err:
            _log.warning(f"[API] Memory stats SQLite fallback failed: {_sq_err}")

    _appdata    = os.environ.get('APPDATA', os.path.expanduser('~'))
    memory_dir  = os.path.join(_appdata, 'SEVEN', 'seven_data', 'memory')
    storage_bytes = 0
    if os.path.exists(memory_dir):
        for root, dirs, files in os.walk(memory_dir):
            for f in files:
                try:
                    storage_bytes += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass

    stats["storage_mb"] = round(storage_bytes / (1024 * 1024), 2)
    try:
        import config as _cfg
        stats["tier"] = _cfg.KEY.get("license", {}).get("tier", "free")
    except Exception as _e:
        _log.debug(f"Tier read failed, defaulting to free: {_e}")
        stats["tier"] = "free"

    return stats