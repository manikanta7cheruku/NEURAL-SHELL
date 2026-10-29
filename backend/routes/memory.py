"""
backend/routes/memory.py
Handles: all /api/memory/* endpoints
"""

from fastapi import APIRouter, HTTPException, Request
import os
import datetime
import logging
from seven_utils.version import get_version

from memory import facts_store

_log = logging.getLogger('seven.memory')

router = APIRouter()


def _speaker_key(speaker_id=None) -> str:
    """The storage key the brain uses for this speaker (generic ids map to the owner)."""
    from brain_modules import session
    return session.resolve_key(speaker_id or "default")


def _size_mb(path: str) -> float:
    total = 0
    if os.path.isfile(path):
        total = os.path.getsize(path)
    elif os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return round(total / (1024 * 1024), 2)


@router.get("/api/memory/overview", summary="What Seven remembers, from the stores the brain uses",
            description="Fact and conversation counts, categories, activity times, storage size and index status.")
def memory_overview():
    from memory import conversation_store
    facts = facts_store.get_facts(active_only=False, limit=1_000_000)
    active = [f for f in facts if f.get("active")]
    by_category = {}
    for f in active:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1
    try:
        activity = conversation_store.activity()
        conversations = conversation_store.count_conversations()
    except Exception as exc:
        _log.warning(f"[API] conversation stats unavailable: {exc}")
        activity, conversations = {"messages": 0, "from_user": 0, "by_source": {}}, 0
    folder = os.path.dirname(facts_store.get_db_path())
    facts_mb = _size_mb(facts_store.get_db_path())
    conv_mb = _size_mb(conversation_store.get_db_path())
    index_mb = _size_mb(os.path.join(folder, "chroma.sqlite3"))
    for entry in (os.listdir(folder) if os.path.isdir(folder) else []):
        full = os.path.join(folder, entry)
        if os.path.isdir(full):
            index_mb += _size_mb(full)
    return {
        "speaker_key": _speaker_key(),
        "facts": {
            "active": len(active),
            "history": len(facts) - len(active),
            "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
            "last_learned_at": max((f.get("created_at") or "" for f in active), default="") or None,
            "last_updated_at": max((f.get("updated_at") or "" for f in active), default="") or None,
            "indexed": sum(1 for f in active if f.get("indexed")),
        },
        "conversations": {"count": conversations, **activity},
        "storage": {"folder": folder, "facts_mb": facts_mb, "conversations_mb": conv_mb,
                    "index_mb": round(index_mb, 2), "total_mb": round(facts_mb + conv_mb + index_mb, 2)},
    }


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
    """Delete a specific fact. Never returns 500."""
    try:
        from memory import seven_memory
        if seven_memory:
            seven_memory.user_facts.delete(ids=[fact_id])
            return {"success": True, "deleted": fact_id}
        else:
            return {"success": False, "error": "Memory system not initialized"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    """Delete a specific conversation. Never returns 500."""
    try:
        from memory import seven_memory
        if seven_memory:
            seven_memory.conversations.delete(ids=[conv_id])
            return {"success": True, "deleted": conv_id}
        else:
            return {"success": False, "error": "Memory system not initialized"}
    except Exception as e:
        # Return error details instead of crashing
        return {"success": False, "error": str(e)}


@router.get("/api/memory/export", summary="Download a backup of everything that is yours",
            description="Facts and their history, every chat, what Seven learned, reminders, tasks, triggers, workspaces, "
                        "the commands you gave and your settings, as one JSON file (backend/backup.py).")
def export_memory():
    from backend import backup
    return backup.export_all()


@router.delete("/api/memory/clear", summary="Clear all memory",
               description="Permanently deletes every fact, conversation, goal, learned preference and the command history, "
                           "and resets the brain's short-term state. Each store is cleared on its own, so one failing "
                           "never stops the others; the answer says exactly what was and was not cleared.")
def clear_all_memory():
    """Forget everything Seven remembers about you. Never returns 500."""
    cleared, failed = {}, []

    def step(name, fn):
        try:
            cleared[name] = fn()
        except Exception as e:
            _log.error(f"[API] Clear memory ({name}) failed: {e}")
            failed.append(name)

    from memory import conversation_store, fact_service, learning_store
    from memory.command_log import command_log
    step("facts", fact_service.forget_all)
    step("conversations", conversation_store.delete_everything)
    step("learning", learning_store.clear_all)
    step("history", command_log.clear)

    def legacy():
        from memory import seven_memory
        if seven_memory:
            seven_memory.clear_all()
    try:
        legacy()
    except Exception as e:
        _log.warning(f"[API] Legacy memory clear skipped: {e}")

    try:
        import brain
        brain.reset_session()
    except Exception:
        pass

    msg = f"Cleared {cleared.get('facts', 0)} facts and {cleared.get('conversations', 0)} conversations."
    if failed:
        return {"success": False, "cleared": cleared, "failed": failed,
                "error": f"{msg} These could not be cleared: {', '.join(failed)}. Try again."}
    return {"success": True, "cleared": cleared, "message": msg}


@router.post("/api/memory/import", summary="Restore a backup",
             description="Adds a backup (from Download backup) to what is already here: nothing is replaced and anything "
                         "already present is skipped, so it is safe to import the same file twice. Reminders and triggers "
                         "beyond the plan's limit are not switched on.")
async def import_memory(request: Request):
    from backend import backup
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="That file is not a Seven backup.")
    try:
        return backup.import_all(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        _log.error(f"[API] Import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not restore the backup ({e})")


@router.get("/api/memory/facts/structured",
            summary="Get structured facts from SQLite store",
            description="Returns facts from the structured SQLite store with speaker partitioning, category filtering, and correction chain metadata.")
def get_structured_facts(
    speaker_id: str = None,
    category: str = None,
    active_only: bool = True,
    limit: int = 500
):
    """Query the structured facts store with optional filters."""
    try:
        facts = facts_store.get_facts(
            speaker_id=speaker_id,
            category=category,
            active_only=active_only,
            limit=limit
        )
        return {"facts": facts, "total": len(facts)}
    except Exception as e:
        _log.error(f"[API] Structured facts query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/memory/facts/structured/{fact_id}",
              summary="Update or supersede a structured fact",
              description="Updates a fact in place if mode is 'update' (default), or creates a new fact linked to the old one if mode is 'supersede'.")
async def update_structured_fact(fact_id: int, request: Request):
    """Update or supersede a structured fact."""
    try:
        body = await request.json()
        new_value = (body.get("value") or "").strip()
        mode = body.get("mode", "update")

        if not new_value:
            raise HTTPException(status_code=400, detail="Value cannot be empty")

        from memory import fact_service
        live_id = fact_service.edit(fact_id, new_value, "supersede" if mode == "supersede" else "update")
        if live_id is None:
            raise HTTPException(status_code=404, detail="Fact not found or inactive")
        if mode == "supersede":
            return {"success": True, "new_id": live_id, "old_id": fact_id}
        return {"success": True, "id": live_id}
    except HTTPException:
        raise
    except Exception as e:
        _log.error(f"[API] Structured fact update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory/facts/structured/{fact_id}",
               summary="Delete a structured fact",
               description="Hard deletes a structured fact record from the SQLite store.")
def delete_structured_fact(fact_id: int):
    """Delete a structured fact."""
    try:
        from memory import fact_service
        if not fact_service.delete(fact_id):
            return {"success": False, "error": "Fact not found"}
        return {"success": True, "deleted": fact_id}
    except Exception as e:
        _log.error(f"[API] Structured fact delete failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/api/memory/facts/structured",
             summary="Add a new structured fact",
             description="Inserts a new fact into the structured SQLite store with speaker partitioning and category.")
async def add_structured_fact(request: Request):
    """Add a fact directly to the structured store."""
    try:
        body = await request.json()
        value = (body.get("value") or "").strip()
        category = body.get("category", "manual")
        key = body.get("key")

        if not value:
            raise HTTPException(status_code=400, detail="Value cannot be empty")

        # Store under the key the brain recalls with (the owner's name), not "default",
        # or Seven would never bring this fact up.
        from memory import fact_service
        new_id = fact_service.add_manual(_speaker_key(body.get("speaker_id")), value, category, key)
        return {"success": True, "id": new_id, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        _log.error(f"[API] Structured fact add failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/facts/structured/{fact_id}/history",
            summary="Get correction history for a fact",
            description="Traces the full correction chain (superseded_by links) from the given fact through all revisions.")
def get_fact_correction_history(fact_id: int):
    """Return the full correction chain for a fact."""
    try:
        chain = facts_store.get_fact_history(fact_id)
        if not chain:
            raise HTTPException(status_code=404, detail="Fact not found")
        return {"fact_id": fact_id, "chain": chain, "revisions": len(chain)}
    except HTTPException:
        raise
    except Exception as e:
        _log.error(f"[API] Correction history query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/stats", summary="Memory statistics",
            description="Returns count of stored conversations and facts, storage size in MB, and current license tier. Uses SQLite fallback if ChromaDB unavailable.")
def get_memory_stats():
    """Get memory statistics including storage size. Never returns 500."""
    stats = {"total_conversations": 0, "total_facts": 0, "storage_path": ""}

    try:
        from memory import seven_memory
        if seven_memory:
            raw_stats = seven_memory.get_stats()
            if isinstance(raw_stats, dict):
                stats = raw_stats
    except Exception as e:
        _log.debug(f"[API] Memory stats via ChromaDB using fallback: {type(e).__name__}")

    # Ensure stats is always a dict (guards against None from lazy proxy)
    if not isinstance(stats, dict):
        stats = {"total_conversations": 0, "total_facts": 0, "storage_path": ""}

    # SQLite fallback if counts are zero
    if stats.get("total_conversations", 0) == 0 and stats.get("total_facts", 0) == 0:
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
        except Exception as _sq_err:
            _log.debug(f"[API] Memory stats SQLite fallback failed: {_sq_err}")

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
    except Exception:
        stats["tier"] = "free"

    return stats