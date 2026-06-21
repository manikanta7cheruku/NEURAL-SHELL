"""
backend/routes/memory.py
Handles: all /api/memory/* endpoints
"""

from fastapi import APIRouter, HTTPException, Request
import os
import datetime

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory/facts/{fact_id}")
def delete_fact(fact_id: str):
    """Delete a specific fact."""
    from memory import seven_memory
    try:
        seven_memory.user_facts.delete(ids=[fact_id])
        return {"success": True, "deleted": fact_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory/conversations")
def get_conversations(limit: int = 50, offset: int = 0):
    """Get stored conversations (paginated)."""
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
                "speaker":        all_convos['metadatas'][i].get("user_id", "default")
            })

        convos.sort(key=lambda x: x["timestamp"], reverse=True)
        total     = len(convos)
        paginated = convos[offset:offset + limit]

        return {"conversations": paginated, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """Export all user data as JSON for backup."""
    import sqlite3
    import config as cfg

    export = {
        "exported_at": datetime.datetime.now().isoformat(),
        "version":     "1.1.4",
        "identity": {
            "name":  cfg.KEY.get("identity", {}).get("user_name", ""),
            "email": cfg.KEY.get("email", ""),
        },
        "facts":         [],
        "conversations": [],
        "schedules":     [],
        "usage":         {}
    }

    # Facts
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

    # Conversations
    try:
        from memory import seven_memory
        all_convos = seven_memory.conversations.get()
        if all_convos and all_convos.get('documents'):
            for i, doc in enumerate(all_convos['documents']):
                meta = all_convos['metadatas'][i] if all_convos.get('metadatas') else {}
                export["conversations"].append({
                    "user":  meta.get("user_input", ""),
                    "seven": doc
                })
    except Exception as e:
        export["conversations_error"] = str(e)

    # Schedules
    try:
        import hands.scheduler as sched
        export["schedules"] = sched.get_all_schedules()
    except Exception:
        pass

    # Usage stats
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


@router.post("/api/memory/import")
async def import_memory(request: Request):
    """Import user data from backup JSON. Bypasses plan limits."""
    try:
        data = await request.json()
        from memory import seven_memory
        imported = {"facts": 0, "conversations": 0}

        for fact in data.get("facts", []):
            if fact.get("text"):
                try:
                    fact_id = f"fact_import_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                    seven_memory.user_facts.add(
                        documents=[fact["text"]],
                        metadatas=[{
                            "category":  fact.get("category", "imported"),
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user_id":   "default",
                            "type":      "fact"
                        }],
                        ids=[fact_id]
                    )
                    imported["facts"] += 1
                except Exception:
                    pass

        for conv in data.get("conversations", []):
            if conv.get("user") and conv.get("seven"):
                try:
                    conv_id  = f"conv_import_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                    combined = f"User said: {conv['user']} | Seven replied: {conv['seven']}"
                    seven_memory.conversations.add(
                        documents=[combined],
                        metadatas=[{
                            "user_input":     conv["user"],
                            "seven_response": conv["seven"],
                            "timestamp":      datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user_id":        "default",
                            "type":           "conversation"
                        }],
                        ids=[conv_id]
                    )
                    imported["conversations"] += 1
                except Exception:
                    pass

        return {
            "success":                True,
            "imported_facts":         imported["facts"],
            "imported_conversations": imported["conversations"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/memory/stats")
def get_memory_stats():
    """Get memory statistics including storage size."""
    try:
        from memory import seven_memory
        stats = seven_memory.get_stats()
    except Exception as e:
        print(f"[API] Memory stats error: {e}")
        stats = {"total_conversations": 0, "total_facts": 0, "storage_path": ""}

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