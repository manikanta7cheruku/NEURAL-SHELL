"""
=============================================================================
PROJECT SEVEN - backend/api_server.py (REST API Bridge)
Version: 1.0

PURPOSE:
    FastAPI REST API that bridges the React dashboard to Python Seven core.
    Runs on localhost:7777 on a separate thread.
    Shares the same brain, memory, hands, scheduler objects as voice pipeline.

ENDPOINTS: 30+ routes covering status, chat, memory, schedules,
           knowledge, config, commands, hardware, license, version.
=============================================================================
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import threading
import time
import os
import json
import datetime

# Telemetry (Phase 2.5)
try:
    import telemetry
except ImportError:
    telemetry = None

# =========================================================================
# APP CREATION
# =========================================================================

app = FastAPI(
    title="Seven API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None
)

# CORS — allow React dev server and Electron to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================================
# SHARED STATE — Set by main.py before server starts
# =========================================================================

_state = {
    "listening": False,
    "speaking": False,
    "thinking": False,
    "start_time": None,
    "current_speaker": "default",
}

_start_time = time.time()


def set_state(key, value):
    """Called by main.py to update shared state."""
    _state[key] = value


def get_state():
    """Get current state dict."""
    return dict(_state)


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================

class ChatRequest(BaseModel):
    text: str
    speaker_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    actions: List[str] = []
    streaming: bool = False


class ConfigUpdate(BaseModel):
    updates: Dict[str, Any]


class ScheduleCreate(BaseModel):
    type: str
    message: str
    time: Optional[str] = None
    duration: Optional[int] = None
    recur: Optional[str] = None
    speaker_id: Optional[str] = "default"


class LicenseVerify(BaseModel):
    key: str


class AppAlias(BaseModel):
    name: str
    target: str


class AppPath(BaseModel):
    name: str
    path: str


# =========================================================================
# PLAN LIMIT ENFORCEMENT
# =========================================================================

def get_current_tier() -> str:
    """Get the current user's license tier. Always safe — returns 'free' on error."""
    try:
        import config
        tier = config.KEY.get("license", {}).get("tier", "free")
        if tier not in ("free", "pro", "ultimate"):
            return "free"
        return tier
    except Exception:
        return "free"


def check_limit(feature: str, current_count: int) -> dict:
    """
    Check if user can create more of a feature based on their plan.

    Args:
        feature:       Key from TIER_FEATURES (e.g. 'facts_limit')
        current_count: How many they already have

    Returns:
        {
            "allowed": bool,
            "current": int,
            "limit": int or -1,
            "tier": str,
            "upgrade_needed": str or None   <- which tier unlocks this
        }
    """
    tier = get_current_tier()
    features = license_module.TIER_FEATURES.get(tier, license_module.TIER_FEATURES["free"])
    limit = features.get(feature, 0)

    if limit == -1:
        # Unlimited
        return {
            "allowed": True,
            "current": current_count,
            "limit": -1,
            "tier": tier,
            "upgrade_needed": None
        }

    allowed = current_count < limit

    # Figure out which tier unlocks more
    upgrade_needed = None
    if not allowed:
        if tier == "free":
            upgrade_needed = "pro"
        elif tier == "pro":
            upgrade_needed = "ultimate"

    return {
        "allowed": allowed,
        "current": current_count,
        "limit": limit,
        "tier": tier,
        "upgrade_needed": upgrade_needed
    }


def plan_limit_error(feature_name: str, limit_check: dict) -> HTTPException:
    """
    Build a clean 403 error when user hits their plan limit.
    Frontend reads this and shows upgrade prompt.
    """
    tier = limit_check["tier"]
    limit = limit_check["limit"]
    current = limit_check["current"]
    upgrade = limit_check.get("upgrade_needed", "pro")

    messages = {
        "facts_limit":           "facts",
        "conversation_history":  "saved conversations",
        "knowledge_files":       "knowledge files",
        "schedules":             "schedules",
        "app_aliases":           "app aliases / URL shortcuts",
        "custom_paths":          "custom app paths",
        "web_searches_per_day":  "web searches today",
    }
    item_name = messages.get(feature_name, feature_name)

    detail = {
        "error": "plan_limit_reached",
        "message": f"You have reached the {tier.upper()} plan limit of {limit} {item_name}. You currently have {current}.",
        "current": current,
        "limit": limit,
        "tier": tier,
        "upgrade_to": upgrade,
        "upgrade_message": f"Upgrade to {upgrade.upper()} to get more {item_name}."
    }

    return HTTPException(status_code=403, detail=detail)


# =========================================================================
# ROOT ENDPOINT
# =========================================================================

@app.get("/")
def root():
    """Root endpoint - API info."""
    return {
        "name": "Seven API",
        "version": "1.0.0",
        "status": "running",
        "docs": "http://127.0.0.1:7777/api/docs",
        "endpoints": {
            "status": "/api/status",
            "chat": "/api/chat",
            "license": "/api/license/status",
            "usage": "/api/usage/stats"
        }
    }

# =========================================================================
# STATUS ENDPOINTS
# =========================================================================

@app.get("/api/status")
def get_status():
    """Get current Seven system status. Bulletproof — never 500s."""
    try:
        try:
            import config
            model = config.KEY.get("brain", {}).get("model_name", "unknown")
            version = config.KEY.get("version", "1.1.3")
        except Exception as e:
            print(f"[API] /status config error: {e}")
            model = "unknown"
            version = "1.1.3"

        try:
            import telemetry as _tel
            _tel.log_activity()
        except Exception as e:
            print(f"[API] /status telemetry error: {e}")

        uptime_secs = int(time.time() - _start_time)
        hours = uptime_secs // 3600
        minutes = (uptime_secs % 3600) // 60

        mood_label = "neutral"
        mood_value = 0.5
        try:
            from memory.mood import mood_engine
            mood_status = mood_engine.get_status()
            mood_label = mood_status.get("label", "neutral")
            mood_value = mood_status.get("mood_value", 0.5)
        except Exception as e:
            print(f"[API] /status mood error: {e}")

        return {
            "listening": _state.get("listening", False),
            "speaking": _state.get("speaking", False),
            "thinking": _state.get("thinking", False),
            "mood": mood_label,
            "mood_value": mood_value,
            "model": model,
            "streaming": False,
            "uptime": f"{hours}h {minutes}m",
            "uptime_seconds": uptime_secs,
            "speaker": _state.get("current_speaker", "default"),
            "version": version
        }
    except Exception as e:
        import traceback
        print(f"[API] /status CATASTROPHIC error: {e}")
        traceback.print_exc()
        return {
            "listening": False,
            "speaking": False,
            "thinking": False,
            "mood": "neutral",
            "mood_value": 0.5,
            "model": "unknown",
            "streaming": False,
            "uptime": "0h 0m",
            "uptime_seconds": 0,
            "speaker": "default",
            "version": "1.1.3",
            "error_debug": str(e)
        }


@app.get("/api/version")
def get_version():
    """Get version info."""
    import config
    return {
        "version": config.KEY.get("version", "1.10"),
        "build_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "name": config.KEY.get("identity", {}).get("name", "Seven")
    }


# =========================================================================
# CHAT ENDPOINT
# =========================================================================

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a text message to Seven's brain."""
    import brain
    import re
    import telemetry
    
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    
    set_state("thinking", True)

    # Track activity for time spent
    try:
        telemetry.log_activity()
    except:
        pass  # Don't fail if telemetry has issues
    
    try:
        response = brain.think(req.text.strip(), speaker_id=req.speaker_id)
        
        # Track activity for telemetry
        try:
            telemetry.log_activity()
        except:
            pass  # Don't fail if telemetry has issues
        
        # Handle streaming response — flatten it for REST API
        is_streaming = isinstance(response, tuple) and len(response) == 2 and response[0] == "__STREAM__"
        
        if is_streaming:
            _, gen = response
            parts = list(gen)  # Consume the generator
            full_response = " ".join(parts)
        else:
            full_response = response if response else "Processing error."
        
        # Extract action tags
        actions = re.findall(r"###(\w+):\s*(.*?)(?=###|$)", full_response)
        action_list = [f"{cmd}:{arg.strip()}" for cmd, arg in actions]
        
        # Clean response (remove tags for display)
        clean_response = re.sub(r"###\w+:\s*[^\n]*", "", full_response).strip()
        if not clean_response:
            clean_response = "Done."
        
        # Execute commands if present
        _execute_actions(action_list, full_response, req.speaker_id)
        
        # Store conversation in memory (enforce plan limit)
        try:
            from memory import seven_memory
            if len(req.text.strip()) > 3 and not full_response.strip().startswith("###"):
                clean_for_memory = re.sub(r'###\w+:\s*\S+', '', full_response).strip()
                if clean_for_memory:
                    # Count current conversations
                    try:
                        all_convos = seven_memory.conversations.get()
                        convo_count = len(all_convos["documents"]) if all_convos and all_convos.get("documents") else 0
                    except Exception:
                        convo_count = 0

                    limit_check = check_limit("conversation_history", convo_count)
                    if limit_check["allowed"]:
                        seven_memory.store_conversation(
                            req.text.strip(), clean_for_memory,
                            user_id=req.speaker_id
                        )
                    else:
                        # Silent limit — chat still works, just not saved
                        # Frontend can show "memory full" from /api/memory/stats
                        print(f"[API] Conversation memory full ({convo_count}/{limit_check['limit']}) — tier: {limit_check['tier']}")
        except Exception:
            pass
        
        return ChatResponse(
            response=clean_response,
            actions=action_list,
            streaming=is_streaming
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        set_state("thinking", False)


def _execute_actions(action_list, full_response, speaker_id):
    """Execute extracted command tags (same logic as main.py)."""
    import re
    import hands.core as core
    import hands.system as system_mod
    import hands.scheduler as scheduler_mod
    
    # Window commands
    window_cmds = re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", full_response)
    for param_str in window_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        if params:
            try:
                import hands.windows as hands_windows
                hands_windows.manage_window(params)
            except Exception:
                pass
    
    # System commands
    sys_cmds = re.findall(r"###SYS:\s*(.*?)(?=###|$)", full_response)
    for param_str in sys_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        if params:
            system_mod.manage_system(params)
    
    # Scheduler commands
    sched_cmds = re.findall(r"###SCHED:\s*(.*?)(?=###|$)", full_response)
    for param_str in sched_cmds:
        params = {}
        for pair in param_str.strip().split():
            if "=" in pair:
                key, val = pair.split("=", 1)
                params[key.strip()] = val.strip()
        params["speaker_id"] = speaker_id
        if params:
            try:
                scheduler_mod.manage_schedule(params)
                if telemetry:
                    telemetry.log_activity()
            except Exception as e:
                print(f"[API] Scheduler error: {e}")

    # App commands
    app_cmds = re.findall(r"###(OPEN|CLOSE):\s*(.*?)(?=###|$)", full_response)
    for cmd_type, arg in app_cmds:
        clean_arg = arg.replace('"', '').replace("'", "").replace(",", "").replace(".", "").strip()
        if not clean_arg:
            continue
        try:
            if cmd_type == "OPEN":
                core.open_app(clean_arg)
            elif cmd_type == "CLOSE":
                core.close_app(clean_arg)
            if telemetry:
                telemetry.log_activity()
        except Exception as e:
            print(f"[API] App command error: {e}")


# =========================================================================
# MEMORY ENDPOINTS
# =========================================================================

@app.post("/api/memory/facts")
def add_manual_fact(data: dict):
    """Manually add a fact. Enforces plan limit."""
    from memory import seven_memory

    text = data.get("text", "").strip()
    category = data.get("category", "manual")

    if not text:
        raise HTTPException(status_code=400, detail="Empty fact text")

    # Count current facts
    try:
        all_facts = seven_memory.user_facts.get()
        current_count = len(all_facts["documents"]) if all_facts and all_facts.get("documents") else 0
    except Exception:
        current_count = 0

    # Check plan limit
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
                "limit": limit_check["limit"],
                "tier": limit_check["tier"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/memory/facts")
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
                "id": all_facts['ids'][i],
                "text": all_facts['documents'][i],
                "category": all_facts['metadatas'][i].get("category", "general"),
                "timestamp": all_facts['metadatas'][i].get("timestamp", ""),
                "speaker": all_facts['metadatas'][i].get("user_id", "default")
            })
        
        return facts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/memory/facts/{fact_id}")
def delete_fact(fact_id: str):
    """Delete a specific fact."""
    from memory import seven_memory
    
    try:
        seven_memory.user_facts.delete(ids=[fact_id])
        return {"success": True, "deleted": fact_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/conversations")
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
                "id": all_convos['ids'][i],
                "text": all_convos['documents'][i],
                "timestamp": all_convos['metadatas'][i].get("timestamp", ""),
                "user_input": all_convos['metadatas'][i].get("user_input", ""),
                "seven_response": all_convos['metadatas'][i].get("seven_response", ""),
                "speaker": all_convos['metadatas'][i].get("user_id", "default")
            })
        
        # Sort by timestamp descending
        convos.sort(key=lambda x: x["timestamp"], reverse=True)
        
        total = len(convos)
        paginated = convos[offset:offset + limit]
        
        return {"conversations": paginated, "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/memory/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a specific conversation."""
    from memory import seven_memory
    
    try:
        seven_memory.conversations.delete(ids=[conv_id])
        return {"success": True, "deleted": conv_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/memory/export")
def export_memory():
    """Export all user data as JSON for backup. Ultimate plan only."""
    import sqlite3
    import config as cfg

    # Check ultimate plan
    tier = get_current_tier()
    features = license_module.TIER_FEATURES.get(tier, license_module.TIER_FEATURES["free"])
    if not features.get("memory_export", False):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "feature_not_available",
                "message": "Memory export is available on Ultimate plan only.",
                "tier": tier,
                "upgrade_to": "ultimate"
            }
        )

    export = {
        "exported_at": datetime.datetime.now().isoformat(),
        "version": "1.1.3",
        "identity": {
            "name":  cfg.KEY.get("identity", {}).get("user_name", ""),
            "email": cfg.KEY.get("email", ""),
        },
        "facts":         [],
        "conversations": [],
        "schedules":     [],
        "usage": {}
    }

    # Facts from ChromaDB
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

    # Conversations from ChromaDB
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
            os.environ.get("APPDATA",""), "SEVEN","data","telemetry.db"
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


@app.post("/api/memory/import")
async def import_memory(request: Request):
    """Import user data from backup JSON. Bypasses plan limits — restoring your own data."""
    try:
        data = await request.json()
        from memory import seven_memory
        from memory.core import SevenMemory
        imported = {"facts": 0, "conversations": 0}

        for fact in data.get("facts", []):
            if fact.get("text"):
                try:
                    # Call ChromaDB directly — bypass plan limit check
                    import datetime as _dt
                    fact_id = f"fact_import_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                    seven_memory.user_facts.add(
                        documents=[fact["text"]],
                        metadatas=[{
                            "category":  fact.get("category", "imported"),
                            "timestamp": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                    import datetime as _dt
                    conv_id = f"conv_import_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                    combined = f"User said: {conv['user']} | Seven replied: {conv['seven']}"
                    seven_memory.conversations.add(
                        documents=[combined],
                        metadatas=[{
                            "user_input":     conv["user"],
                            "seven_response": conv["seven"],
                            "timestamp":      _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user_id":        "default",
                            "type":           "conversation"
                        }],
                        ids=[conv_id]
                    )
                    imported["conversations"] += 1
                except Exception:
                    pass

        return {
            "success":               True,
            "imported_facts":        imported["facts"],
            "imported_conversations": imported["conversations"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/memory/stats")
def get_memory_stats():
    """Get memory statistics."""
    try:
        from memory import seven_memory
        stats = seven_memory.get_stats()
    except Exception as e:
        print(f"[API] Memory stats error: {e}")
        stats = {
            "total_conversations": 0,
            "total_facts": 0,
            "storage_path": ""
        }

    # Calculate storage size
    _appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    memory_dir = os.path.join(_appdata, 'SEVEN', 'seven_data', 'memory')
    storage_bytes = 0
    if os.path.exists(memory_dir):
        for root, dirs, files in os.walk(memory_dir):
            for f in files:
                try:
                    storage_bytes += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass

    stats["storage_mb"] = round(storage_bytes / (1024 * 1024), 2)
    return stats


# =========================================================================
# SCHEDULE ENDPOINTS
# =========================================================================

@app.get("/api/schedules")
def get_schedules():
    """Get all schedules."""
    import hands.scheduler as scheduler_mod
    return scheduler_mod.get_all_schedules()


@app.post("/api/schedules")
def create_schedule(sched: ScheduleCreate):
    """Create a new schedule. Enforces plan limit."""
    import hands.scheduler as scheduler_mod

    # Count current schedules
    try:
        current_schedules = scheduler_mod.get_all_schedules()
        schedule_count = len(current_schedules) if current_schedules else 0
    except Exception:
        schedule_count = 0

    # Check plan limit
    limit_check = check_limit("schedules", schedule_count)
    if not limit_check["allowed"]:
        raise plan_limit_error("schedules", limit_check)

    # Check recurring schedule permission (pro+ only)
    if sched.recur and sched.recur.strip():
        features = license_module.TIER_FEATURES.get(get_current_tier(), {})
        if not features.get("recurring_schedules", False):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_not_available",
                    "message": "Recurring schedules require Pro plan or higher.",
                    "tier": get_current_tier(),
                    "upgrade_to": "pro"
                }
            )

    params = {
        "action": sched.type,
        "message": sched.message,
        "speaker_id": sched.speaker_id
    }

    if sched.time:
        params["time"] = sched.time
    if sched.duration is not None:
        params["duration"] = str(sched.duration)
    if sched.recur:
        params["recur"] = sched.recur

    success, msg = scheduler_mod.manage_schedule(params)

    if success:
        return {
            "success": True,
            "message": msg,
            "usage": {
                "current": schedule_count + 1,
                "limit": limit_check["limit"],
                "tier": limit_check["tier"]
            }
        }
    else:
        raise HTTPException(status_code=400, detail=msg)


@app.delete("/api/schedules/{schedule_id}")
def cancel_schedule(schedule_id: int):
    """Cancel a specific schedule."""
    import hands.scheduler as scheduler_mod
    
    success, msg = scheduler_mod.cancel_schedule(schedule_id=schedule_id)
    if success:
        return {"success": True, "message": msg}
    else:
        raise HTTPException(status_code=404, detail=msg)


# =========================================================================
# KNOWLEDGE ENDPOINTS
# =========================================================================

@app.get("/api/knowledge/stats")
def get_knowledge_stats():
    """Get knowledge base statistics."""
    try:
        from knowledge import get_knowledge_stats as _get_stats
        return _get_stats()
    except ImportError:
        return {"total_chunks": 0, "sources": [], "storage_mb": 0}


# ── Check multipart availability at module load (not at decorator time) ──
def _make_upload_endpoint():
    """
    Registers /api/knowledge/upload only if python-multipart is installed.
    Called once at module load. Avoids import-time crash.
    """
    try:
        import multipart  # python-multipart
        _multipart_ok = True
    except ImportError:
        _multipart_ok = False

    if _multipart_ok:
        from fastapi import UploadFile, File as FastAPIFile

        @app.post("/api/knowledge/upload")
        async def upload_knowledge(file: UploadFile = FastAPIFile(...)):
            """Upload a file to the knowledge base. Enforces plan limit."""
            try:
                # Count current knowledge files
                try:
                    _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
                    _know_dir = os.path.join(_appdata, "SEVEN", "seven_data", "knowledge")
                    if os.path.exists(_know_dir):
                        file_count = len([
                            f for f in os.listdir(_know_dir)
                            if os.path.isfile(os.path.join(_know_dir, f))
                        ])
                    else:
                        file_count = 0
                except Exception:
                    file_count = 0

                # Check plan limit
                limit_check = check_limit("knowledge_files", file_count)
                if not limit_check["allowed"]:
                    raise plan_limit_error("knowledge_files", limit_check)

                from knowledge.indexer import index_file
                _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
                sources_dir = os.path.join(_appdata, "SEVEN", "seven_data", "knowledge")
                os.makedirs(sources_dir, exist_ok=True)
                file_path = os.path.join(sources_dir, file.filename)
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                chunks = index_file(file_path)
                return {
                    "success": True,
                    "filename": file.filename,
                    "chunks_indexed": chunks,
                    "usage": {
                        "current": file_count + 1,
                        "limit": limit_check["limit"],
                        "tier": limit_check["tier"]
                    }
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    else:
        # Register a safe fallback endpoint — no multipart dependency
        @app.post("/api/knowledge/upload")
        async def upload_knowledge_unavailable(request: Request):
            """Fallback when python-multipart not installed."""
            return {
                "success": False,
                "error": "python-multipart not installed. Run setup wizard to install packages."
            }

        print("[API] python-multipart not installed — upload endpoint in fallback mode")


# Register the endpoint (safe at import time regardless of multipart)
_make_upload_endpoint()


@app.get("/api/knowledge/search")
def search_knowledge(q: str):
    """Search the knowledge base."""
    try:
        from knowledge import search_knowledge as _search
        results = _search(q)
        return {"query": q, "results": results if results else "No results found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/knowledge/clear")
def clear_knowledge():
    """Clear the knowledge base."""
    try:
        from knowledge import clear_knowledge as _clear
        success = _clear()
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# CONFIG ENDPOINTS
# =========================================================================

@app.get("/api/config")
def get_config():
    """Get full configuration."""
    import config
    return config.KEY


@app.put("/api/config")
def update_config(req: ConfigUpdate):
    """Partial update of configuration."""
    import config
    
    success = config.update_config(req.updates)
    if success:
        return {"success": True, "config": config.KEY}
    else:
        raise HTTPException(status_code=500, detail="Failed to save config")


@app.get("/api/config/commands")
def get_commands_config():
    """Get all command configurations."""
    import config
    
    commands = config.KEY.get("commands", {})
    return {
        "app_aliases": commands.get("app_aliases", {}),
        "app_paths": commands.get("app_paths", {}),
        "failed_apps": commands.get("failed_apps", [])
    }


@app.put("/api/config/commands")
def update_commands_config(req: ConfigUpdate):
    """Update command configurations."""
    import config
    
    success = config.update_config({"commands": req.updates})
    if success:
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="Failed to save commands config")


# =========================================================================
# COMMAND ENDPOINTS (Apps)
# =========================================================================

@app.get("/api/commands/failed-apps")
def get_failed_apps():
    """Get recent failed app launch attempts."""
    import config
    return config.KEY.get("commands", {}).get("failed_apps", [])


@app.post("/api/commands/app-aliases")
def add_app_alias(alias: AppAlias):
    """Add or update an app alias. Enforces plan limit."""
    import config

    current_aliases = config.KEY.get("commands", {}).get("app_aliases", {})
    alias_key = alias.name.lower().strip()

    # If editing existing alias — not a new one, skip limit check
    is_new = alias_key not in current_aliases

    if is_new:
        limit_check = check_limit("app_aliases", len(current_aliases))
        if not limit_check["allowed"]:
            raise plan_limit_error("app_aliases", limit_check)

    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    if "app_aliases" not in config.KEY["commands"]:
        config.KEY["commands"]["app_aliases"] = {}

    config.KEY["commands"]["app_aliases"][alias_key] = alias.target.lower().strip()
    config.save_config()

    return {
        "success": True,
        "alias": alias.name,
        "target": alias.target,
        "usage": {
            "current": len(config.KEY["commands"]["app_aliases"]),
            "limit":   limit_check["limit"] if is_new else -1,
            "tier":    get_current_tier()
        } if is_new else {}
    }


@app.delete("/api/commands/app-aliases/{alias_name}")
def delete_app_alias(alias_name: str):
    """Delete an app alias."""
    import config
    
    aliases = config.KEY.get("commands", {}).get("app_aliases", {})
    if alias_name in aliases:
        del aliases[alias_name]
        config.save_config()
        return {"success": True, "deleted": alias_name}
    else:
        raise HTTPException(status_code=404, detail=f"Alias '{alias_name}' not found")


@app.post("/api/commands/app-paths")
def add_app_path(app_path: AppPath):
    """Add or update a custom app path. Enforces plan limit."""
    import config

    current_paths = config.KEY.get("commands", {}).get("app_paths", {})
    path_key = app_path.name.lower().strip()

    # Only check limit for new entries
    is_new = path_key not in current_paths

    if is_new:
        limit_check = check_limit("custom_paths", len(current_paths))
        if not limit_check["allowed"]:
            raise plan_limit_error("custom_paths", limit_check)

    # Strip surrounding quotes if user pasted path with quotes
    clean_path = app_path.path.strip().strip('"').strip("'")
    if not os.path.exists(clean_path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {clean_path}")
    app_path = AppPath(name=app_path.name, path=clean_path)

    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    if "app_paths" not in config.KEY["commands"]:
        config.KEY["commands"]["app_paths"] = {}

    config.KEY["commands"]["app_paths"][path_key] = app_path.path
    config.save_config()

    return {
        "success": True,
        "name": app_path.name,
        "path": app_path.path,
        "usage": {
            "current": len(config.KEY["commands"]["app_paths"]),
            "limit":   limit_check["limit"] if is_new else -1,
            "tier":    get_current_tier()
        } if is_new else {}
    }


@app.delete("/api/commands/app-paths/{app_name}")
def delete_app_path(app_name: str):
    """Delete a custom app path."""
    import config
    
    paths = config.KEY.get("commands", {}).get("app_paths", {})
    if app_name in paths:
        del paths[app_name]
        config.save_config()
        return {"success": True, "deleted": app_name}
    else:
        raise HTTPException(status_code=404, detail=f"App path '{app_name}' not found")


# =========================================================================
# HARDWARE & SPEED ENDPOINTS
# =========================================================================

@app.get("/api/hardware")
def get_hardware():
    """Get hardware info and model recommendation."""
    import brain_manager
    
    hw = brain_manager.get_hardware_summary()
    rec_model, tier, reason = brain_manager.recommend_model(hw)
    installed = brain_manager.get_installed_models()
    
    return {
        "gpu": hw["gpu"],
        "ram_gb": hw["ram_gb"],
        "cpu": hw["cpu"],
        "os": hw["os"],
        "recommended_model": rec_model,
        "recommended_tier": tier,
        "recommendation_reason": reason,
        "installed_models": installed
    }


@app.get("/api/speed")
def get_speed():
    """Get latency statistics."""
    import brain_manager
    import config
    
    stats = brain_manager.get_latency_stats()
    stats["model"] = config.KEY.get("brain", {}).get("model_name", "unknown")
    stats["streaming"] = config.KEY.get("brain", {}).get("streaming", False)
    
    return stats


# =========================================================================
# COMMANDS LOG ENDPOINT
# =========================================================================

@app.get("/api/commands/log")
def get_command_log(limit: int = 50):
    """Get recent command execution log."""
    from memory.command_log import command_log
    
    recent = command_log.get_recent(count=limit)
    stats = command_log.get_stats()
    
    return {
        "recent": recent,
        "stats": stats
    }


# =========================================================================
# MOOD ENDPOINT
# =========================================================================

@app.get("/api/mood")
def get_mood():
    """Get current mood status."""
    from memory.mood import mood_engine
    return mood_engine.get_status()


# =========================================================================
# SPEAKERS ENDPOINT
# =========================================================================

@app.get("/api/speakers")
def get_speakers():
    """Get enrolled speakers."""
    try:
        from ears.voice_id import get_enrolled_speakers, is_voice_id_enabled
        
        if not is_voice_id_enabled():
            return {"enabled": False, "speakers": []}
        
        speakers = get_enrolled_speakers()
        return {
            "enabled": True,
            "speakers": [{"name": s, "enrolled": True} for s in speakers]
        }
    except Exception:
        return {"enabled": False, "speakers": []}


# =========================================================================
# LICENSE ENDPOINT (Placeholder — Full implementation in Phase 5)
# =========================================================================

import license as license_module

class LicenseActivate(BaseModel):
    key: str
    email: Optional[str] = None

class LicenseDeactivate(BaseModel):
    key: Optional[str] = None

class TrialStart(BaseModel):
    email: str

class ReferralRegister(BaseModel):
    code: str
    email: str

def get_device_id():
    """Get device ID."""
    try:
        import license as license_module
        return license_module.get_device_id()
    except:
        import telemetry
        return telemetry.get_device_id()


@app.post("/api/license/activate")
def activate_license_endpoint(req: LicenseActivate):
    """Activate a license key."""
    success, message, data = license_module.activate_license(req.key, req.email)
    
    if success:
        return {"success": True, "message": message, "license": data}
    else:
        raise HTTPException(status_code=400, detail=message)


@app.get("/api/license/status")
def get_license_status():
    """Get current license status. Never 500s — always returns safe defaults on error."""
    try:
        validation = license_module.validate_license()
        if not isinstance(validation, dict):
            raise ValueError(f"validate_license returned {type(validation)}, expected dict")

        tier = validation.get("tier", "free")
        features = license_module.get_features(tier)
        device_id = license_module.get_device_id() or "unknown"

        import config
        license_key = config.KEY.get("license", {}).get("key", "")
        is_trial = config.KEY.get("license", {}).get("is_trial", False)

        return {
            "tier": tier,
            "valid": validation.get("valid", True),
            "expires_at": validation.get("expires_at"),
            "days_until_expiry": validation.get("days_until_expiry"),
            "offline_mode": validation.get("offline_mode", False),
            "offline_days": validation.get("offline_days", 0),
            "features": features or {},
            "license_key": license_key,
            "is_trial": is_trial,
            "device_id": (device_id[:8] + "...") if len(device_id) > 8 else device_id
        }
    except Exception as e:
        import traceback
        print(f"[API] /api/license/status error: {e}")
        traceback.print_exc()
        return {
            "tier": "free",
            "valid": True,
            "expires_at": None,
            "days_until_expiry": None,
            "offline_mode": False,
            "offline_days": 0,
            "features": {},
            "license_key": "",
            "is_trial": False,
            "device_id": "unknown",
            "error_debug": str(e)
        }


@app.post("/api/license/validate")
def validate_license_endpoint():
    """Force online validation."""
    validation = license_module.validate_license(online=True)
    return validation


@app.post("/api/license/deactivate")
def deactivate_license_endpoint(req: LicenseDeactivate):
    """Deactivate license on current device."""
    success, message = license_module.deactivate_device(req.key)
    
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)


@app.get("/api/license/features")
def get_license_features():
    """Get feature flags for current tier."""
    features = license_module.get_features()
    return features


@app.post("/api/license/trial")
def start_trial_endpoint(req: TrialStart):
    """Start 14-day Pro trial."""
    success, message = license_module.start_trial(req.email)
    
    if success:
        telemetry.save_email(req.email)  # Save email for updates
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)


@app.get("/api/license/pricing")
def get_pricing():
    """Get pricing information."""
    return {
        "tiers": license_module.TIER_FEATURES,
        "pricing": license_module.PRICING
    }


@app.get("/api/plan/usage")
def get_plan_usage():
    """
    Get current usage vs plan limits for all features.
    Used by Plans page and dashboard to show upgrade prompts.
    """
    tier = get_current_tier()
    features = license_module.TIER_FEATURES.get(tier, license_module.TIER_FEATURES["free"])

    # Count facts
    try:
        from memory import seven_memory
        all_facts = seven_memory.user_facts.get()
        facts_count = len(all_facts["documents"]) if all_facts and all_facts.get("documents") else 0
    except Exception:
        facts_count = 0

    # Count conversations
    try:
        from memory import seven_memory
        all_convos = seven_memory.conversations.get()
        convo_count = len(all_convos["documents"]) if all_convos and all_convos.get("documents") else 0
    except Exception:
        convo_count = 0

    # Count knowledge files
    try:
        _appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        _know_dir = os.path.join(_appdata, "SEVEN", "seven_data", "knowledge")
        file_count = len([
            f for f in os.listdir(_know_dir)
            if os.path.isfile(os.path.join(_know_dir, f))
        ]) if os.path.exists(_know_dir) else 0
    except Exception:
        file_count = 0

    # Count schedules
    try:
        import hands.scheduler as scheduler_mod
        all_schedules = scheduler_mod.get_all_schedules()
        schedule_count = len(all_schedules) if all_schedules else 0
    except Exception:
        schedule_count = 0

    def usage_item(current, limit):
        if limit == -1:
            return {"current": current, "limit": -1, "percent": 0, "full": False}
        percent = int((current / limit) * 100) if limit > 0 else 100
        return {"current": current, "limit": limit, "percent": percent, "full": current >= limit}

    return {
        "tier": tier,
        "features": {
            "facts":         usage_item(facts_count,    features.get("facts_limit", 7)),
            "conversations": usage_item(convo_count,    features.get("conversation_history", 7)),
            "knowledge":     usage_item(file_count,     features.get("knowledge_files", 1)),
            "schedules":     usage_item(schedule_count, features.get("schedules", 7)),
        },
        "capabilities": {
            "memory_export":       features.get("memory_export", False),
            "voice_recognition":   features.get("voice_recognition", False),
            "recurring_schedules": features.get("recurring_schedules", False),
        }
    }


@app.get("/api/referral/stats")
def get_referral_stats_endpoint():
    """Get referral statistics."""
    email = telemetry.get_email()
    
    if not email:
        # Try server
        try:
            import server_sync
            device_id = get_device_id()
            stats = server_sync.get_referral_stats(device_id=device_id)
            if stats:
                return stats
        except:
            pass
        
        return {
            "referral_code": None,
            "completed_referrals": 0,
            "pending_referrals": 0
        }
    
    # Try local first
    try:
        import license as license_module
        stats = license_module.get_referral_stats(email)
        if stats:
            return stats
    except:
        pass
    
    # Try server
    try:
        import server_sync
        stats = server_sync.get_referral_stats(email=email)
        if stats:
            return stats
    except:
        pass
    
    return {
        "referral_code": None,
        "completed_referrals": 0,
        "pending_referrals": 0
    }


@app.post("/api/referral/create")
def create_referral_endpoint(data: dict):
    """Create a referral code."""
    email = data.get("email") or telemetry.get_email()
    
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    # Save email locally
    telemetry.save_email(email)
    
    # Create on server
    try:
        import server_sync
        device_id = get_device_id()
        result = server_sync.create_referral(device_id, email)
        
        if result:
            return {
                "success": True,
                "referral_code": result["referral_code"],
                "referral_link": result["referral_link"]
            }
    except Exception as e:
        print(f"[API] Server referral creation failed: {e}")
    
    # Fallback to local
    try:
        import license as license_module
        code = license_module.create_referral_code(email)
        return {
            "success": True,
            "referral_code": code,
            "referral_link": f"https://seven.app/ref/{code}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# WEBSOCKET ENDPOINT — Sends status every 500ms
# =========================================================================
from fastapi import WebSocket
import asyncio

@app.websocket("/ws/status")
async def status_websocket(websocket: WebSocket):
    """Real-time status updates via WebSocket"""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "listening": _state.get("listening", False),
                "thinking": _state.get("thinking", False),
                "speaking": _state.get("speaking", False)
            })
            await asyncio.sleep(0.5)  # Send every 500ms
    except:
        pass  # Client disconnected


# =========================================================================
# EMAIL COLLECTION ENDPOINT (Phase 2.5)
# =========================================================================

@app.post("/api/email/save")
def save_user_email(data: dict):
    """Save user email for updates."""
    import telemetry
    
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    
    telemetry.save_email(email)
    return {"success": True, "email": email}


@app.get("/api/email/check")
def check_email_saved():
    """Check if user has saved email."""
    import telemetry
    email = telemetry.get_email()
    return {"saved": email is not None, "email": email}

# =========================================================================
# USAGE STATS ENDPOINTS (FIXED)
# =========================================================================

@app.get("/api/usage/stats")
@app.get("/api/usage/stats")
def get_usage_stats_fixed():
    """Get current user's total usage time."""
    import sqlite3

    try:
        import telemetry as tel
        device_id = tel.get_device_id()
        email     = tel.get_email()
        tel_db    = tel.TELEMETRY_DB
    except Exception as e:
        print(f"[API] Telemetry import error: {e}")
        return {
            "total_hours": 0, "total_minutes": 0,
            "display": "0 min", "email": None,
            "device_id": None, "last_seen": None
        }

    total_hours = 0
    last_seen   = None

    if os.path.exists(tel_db):
        try:
            conn = sqlite3.connect(tel_db)
            c    = conn.cursor()
            c.execute(
                "SELECT active_hours, last_seen, email FROM stats WHERE device_id = ?",
                (device_id,)
            )
            row = c.fetchone()
            if not row:
                c.execute(
                    "SELECT active_hours, last_seen, email FROM stats ORDER BY last_seen DESC LIMIT 1"
                )
                row = c.fetchone()
            if row:
                total_hours = row[0] or 0
                last_seen   = row[1]
                if not email and row[2]:
                    email = row[2]
            conn.close()
        except Exception as e:
            print(f"[API] telemetry.db read error: {e}")

    try:
        import telemetry as tel
        total_hours += tel.get_active_hours()
    except Exception:
        pass

    total_minutes = int(total_hours * 60)
    if total_minutes < 1:
        time_str = "0 min"
    elif total_minutes < 60:
        time_str = f"{total_minutes} min"
    else:
        hrs  = total_minutes // 60
        mins = total_minutes % 60
        time_str = f"{hrs} hr {mins} min" if mins else f"{hrs} hr"

    return {
        "total_hours":   round(total_hours, 4),
        "total_minutes": total_minutes,
        "display":       time_str,
        "email":         email,
        "device_id":     device_id,
        "last_seen":     last_seen
    }


@app.get("/api/usage/history")
def get_usage_history_fixed():
    """Get actual daily usage for last 7 days."""
    import sqlite3
    from datetime import datetime, timedelta

    try:
        import telemetry as tel
        device_id = tel.get_device_id()
        tel_db    = tel.TELEMETRY_DB
    except Exception:
        device_id = None
        tel_db    = None

    history = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        history.append({
            "date":    date.strftime("%Y-%m-%d"),
            "day":     date.strftime("%a"),
            "hours":   0.0,
            "minutes": 0
        })

    if tel_db and os.path.exists(tel_db) and device_id:
        try:
            conn = sqlite3.connect(tel_db)
            c    = conn.cursor()
            seven_days_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
            c.execute("""
                SELECT date, hours FROM daily_usage
                WHERE device_id = ? AND date >= ?
                ORDER BY date ASC
            """, (device_id, seven_days_ago))
            actual = {row[0]: row[1] for row in c.fetchall()}
            conn.close()
            for day in history:
                if day["date"] in actual:
                    day["hours"]   = round(actual[day["date"]], 3)
                    day["minutes"] = int(actual[day["date"]] * 60)
        except Exception as e:
            print(f"[API] Usage history error: {e}")

    return {
        "history":     history,
        "total_hours": round(sum(d["hours"] for d in history), 3)
    }


@app.get("/api/voice-control/words")
def get_voice_control_words():
    """Get current wake/pause/shutdown words."""
    import config
    
    identity = config.KEY.get("identity", {})
    tier = config.KEY.get("license", {}).get("tier", "free")
    
    return {
        "wake_words": identity.get("wake_words", ["seven"]),
        "pause_words": identity.get("pause_words", ["hold on"]),
        "resume_words": identity.get("resume_words", ["wake up"]),
        "shutdown_words": identity.get("shutdown_words", ["go to sleep"]),
        "tier": tier,
        "can_edit": tier in ["pro", "ultimate"]
    }


@app.put("/api/voice-control/words")
def update_voice_control_words(data: dict):
    """Update wake/pause/shutdown words (Pro only)."""
    import config
    
    tier = config.KEY.get("license", {}).get("tier", "free")
    
    if tier not in ["pro", "ultimate"]:
        raise HTTPException(status_code=403, detail="Pro plan required to customize voice commands")
    
    updates = {}
    
    if "wake_words" in data:
        updates["identity.wake_words"] = [w.lower().strip() for w in data["wake_words"] if w.strip()]
    
    if "pause_words" in data:
        updates["identity.pause_words"] = [w.lower().strip() for w in data["pause_words"] if w.strip()]
    
    if "resume_words" in data:
        updates["identity.resume_words"] = [w.lower().strip() for w in data["resume_words"] if w.strip()]
    
    if "shutdown_words" in data:
        updates["identity.shutdown_words"] = [w.lower().strip() for w in data["shutdown_words"] if w.strip()]
    
    # Update each field
    for key, value in updates.items():
        parts = key.split(".")
        if len(parts) == 2:
            if parts[0] not in config.KEY:
                config.KEY[parts[0]] = {}
            config.KEY[parts[0]][parts[1]] = value
    
    config.save_config()
    
    return {"success": True, "message": "Voice commands updated"}

# =========================================================================
# REFERRAL COMPLETION CHECK
# =========================================================================

@app.get("/api/referral/completed-pending")
def get_completed_pending_referrals():
    """
    Get list of referrals that just completed 7 hours.
    Admin endpoint to know when to send license keys.
    """
    import license as license_module
    import sqlite3
    
    license_module.init_db()
    
    conn = sqlite3.connect(license_module.LICENSE_DB)
    c = conn.cursor()
    
    # Get recently completed referrals (within last 7 days)
    c.execute("""
        SELECT r.referred_email, r.referrer_email, r.completed_at, r.usage_hours
        FROM referrals r
        WHERE r.is_complete = 1 
        AND r.completed_at > datetime('now', '-7 days')
        ORDER BY r.completed_at DESC
    """)
    
    completed = []
    for row in c.fetchall():
        completed.append({
            "referred_email": row[0],
            "referrer_email": row[1],
            "completed_at": row[2],
            "usage_hours": round(row[3], 1)
        })
    
    # Get referrals close to completion (>5 hours)
    c.execute("""
        SELECT r.referred_email, r.referrer_email, r.usage_hours, r.created_at
        FROM referrals r
        WHERE r.is_complete = 0 
        AND r.usage_hours >= 5
        ORDER BY r.usage_hours DESC
    """)
    
    almost_complete = []
    for row in c.fetchall():
        almost_complete.append({
            "referred_email": row[0],
            "referrer_email": row[1],
            "usage_hours": round(row[2], 1),
            "hours_left": round(7 - row[2], 1),
            "created_at": row[3]
        })
    
    conn.close()
    
    return {
        "completed_recently": completed,
        "almost_complete": almost_complete
    }


# =========================================================================
# SETUP WIZARD ENDPOINTS (Phase 5)
# =========================================================================

class SetupCompleteRequest(BaseModel):
    name: str
    email: str
    referral_code: Optional[str] = ""
    wake_word: Optional[str] = "seven"
    voice_index: Optional[int] = 0
    model_name: Optional[str] = ""

class VoicePreviewRequest(BaseModel):
    voice_index: Optional[int] = 0


@app.get("/api/setup/existing-identity")
def get_existing_identity():
    """
    Check if this device has previously registered identity on server.
    Called on wizard Step 1 mount — auto-fills name and email if found.
    """
    try:
        import telemetry as tel
        import requests as _req

        device_id = tel.get_device_id()

        # Ask server if this device is known
        SERVER_URL = "https://seven-server-u2rp.onrender.com"
        r = _req.get(
            f"{SERVER_URL}/api/device/{device_id}",
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "found": True,
                "name":  data.get("name"),
                "email": data.get("email"),
            }
        return {"found": False}
    except Exception:
        return {"found": False}


@app.post("/api/setup/complete")
def complete_setup(req: SetupCompleteRequest):
    """
    Called when user finishes setup wizard.
    Saves all preferences + marks setup_complete: true.
    Also syncs name + email to Railway admin dashboard.
    """
    import config

    # Validate required fields
    name = req.name.strip()
    email = req.email.strip()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    # Build config updates
    wake = req.wake_word.lower().strip() if req.wake_word else "seven"

    updates = {
        "setup_complete": True,
        "email": email,
        "identity": {
            **config.KEY.get("identity", {}),
            "user_name": name,
            "wake_words": [wake, f"hey {wake}"],
        },
        "voice": {
            "voice_index": req.voice_index,
        },
    }

    if req.model_name:
        updates["brain"] = {
            **config.KEY.get("brain", {}),
            "model_name": req.model_name,
        }

    success = config.update_config(updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save configuration")

    # Save email to telemetry (data/email.txt)
    try:
        import telemetry
        telemetry.save_email(email)
    except Exception:
        pass

    # Sync name + email to Railway admin dashboard
    try:
        import server_sync
        import license as license_module
        device_id = license_module.get_device_id()

        # Register/update device on server with name + email
        server_sync.register_device(
            device_id=device_id,
            email=email,
            name=name,                         # sent to server
            referral_code=req.referral_code or None
        )
    except Exception as e:
        print(f"[SETUP] Server sync warning: {e}")
        # Don't fail setup if server is unreachable

    # Register referral on server if code provided
    if req.referral_code and req.referral_code.strip():
        try:
            import server_sync
            import telemetry as tel
            device_id = tel.get_device_id()
            # Register device on server WITH referral code
            # Server links this device to the referrer
            server_sync._post("/api/register", {
                "device_id":      device_id,
                "email":          email,
                "name":           name,
                "country":        None,
                "referral_code":  req.referral_code.strip()
            })
            print(f"[SETUP] Referral code registered: {req.referral_code}")
        except Exception as e:
            print(f"[SETUP] Referral register warning: {e}")

    return {
        "success": True,
        "message": f"Welcome to Seven, {name}.",
    }


@app.post("/api/setup/preview-voice")
def preview_voice(req: VoicePreviewRequest):
    """
    Plays a short TTS sample using selected voice index.
    Runs in a daemon thread — API returns immediately.
    """
    import threading

    def _speak():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            if voices and req.voice_index < len(voices):
                engine.setProperty('voice', voices[req.voice_index].id)
            engine.setProperty('rate', 185)
            engine.setProperty('volume', 1.0)
            engine.say("Hello. I am Seven. Your private AI assistant.")
            engine.runAndWait()
        except Exception as e:
            print(f"[SETUP] Voice preview error: {e}")

    threading.Thread(target=_speak, daemon=True).start()
    return {"success": True}


@app.get("/api/setup/voices")
def get_available_voices():
    """
    Returns all available Windows TTS voices.
    Called on Step 3 (Personalize) mount.
    """
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')

        result = []
        for i, v in enumerate(voices):
            raw = v.name or f"Voice {i}"
            # Strip Microsoft prefix and Desktop suffix
            # "Microsoft Zira Desktop - English (United States)" → "Zira"
            clean = raw.replace("Microsoft ", "")
            clean = clean.split(" Desktop")[0].split(" -")[0].strip()

            # Detect gender by common name patterns
            female_names = ["zira", "hazel", "helena", "linda", "susan", "eva",
                            "aria", "jenny", "michelle", "emma"]
            gender = "Female" if any(n in clean.lower() for n in female_names) else "Male"

            # Detect language
            lang = "English"
            if "(" in raw and ")" in raw:
                lang_raw = raw.split("(")[-1].split(")")[0]
                lang = lang_raw.strip()

            result.append({
                "index": i,
                "name": clean,
                "full_name": raw,
                "gender": gender,
                "language": lang,
            })

        engine.stop()
        return {"voices": result, "count": len(result)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# =========================================================================
# UPDATE SYSTEM ENDPOINTS (Phase 6)
# =========================================================================

@app.get("/api/update/status")
def get_update_status():
    """
    Current update state — polled by React frontend every 3 seconds
    when update panel is open or download is in progress.
    """
    try:
        try:
            from backend.updater import get_state, _read_current_version
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from updater import get_state, _read_current_version
        state = get_state()
        return {
            **state,
            "current_version": _read_current_version(),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "update_available": False,
            "checking": False,
            "downloading": False,
            "download_progress": 0,
            "download_path": None,
            "error": str(e),
            "info": None,
            "current_version": "1.1.3"
        }


@app.post("/api/update/check")
def trigger_update_check():
    """Force an immediate update check (user clicked 'Check Now')."""
    try:
        try:
            from backend.updater import check_for_updates
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from updater import check_for_updates
        check_for_updates(force=True)
        return {"success": True, "message": "Check started"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/update/download")
def trigger_download():
    """
    Start downloading the update in background.
    Only valid when update_available is True and download_mode is 'manual'.
    """
    try:
        try:
            from backend import updater
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import updater

        state = updater.get_state()

        if not state["update_available"]:
            raise HTTPException(status_code=400, detail="No update available")
        if state["downloading"]:
            raise HTTPException(status_code=400, detail="Download already in progress")

        updater.start_download_thread()
        return {"success": True, "message": "Download started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update/install")
def trigger_install():
    """
    Signal Electron to run the downloaded installer and quit the app.
    Only valid when download_path exists.
    """
    try:
        try:
            from backend import updater
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import updater

        state = updater.get_state()
        path = state.get("download_path")
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=400, detail="Installer not downloaded yet")

        return {"success": True, "installer_path": path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================================================================
# BOOTSTRAP ENDPOINTS (Phase 7 — First Launch Setup)
# =========================================================================

@app.get("/api/bootstrap/status")
def get_bootstrap_status():
    """
    Poll this endpoint to get live environment setup progress.
    React wizard Step 4 polls this every 500ms.
    """
    try:
        try:
            from backend.bootstrap import get_state
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from bootstrap import get_state
        return get_state()
    except Exception as e:
        return {"error": str(e), "overall_ready": False}


@app.post("/api/bootstrap/start")
def start_bootstrap():
    """
    Start the environment setup sequence.
    Runs: pip install → Ollama download → Ollama start
    Returns immediately. Poll /api/bootstrap/status for progress.
    """
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import bootstrap
        bootstrap.run_environment_setup()
        return {"success": True, "message": "Bootstrap started"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/bootstrap/pull-model")
def pull_model_endpoint(data: dict):
    """
    Start pulling an Ollama model.
    Body: {"model": "llama3"}
    Poll /api/bootstrap/status for progress under model_pull key.
    """
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import bootstrap
        model = data.get("model", "").strip()
        if not model:
            raise HTTPException(status_code=400, detail="model name required")
        bootstrap.run_model_pull(model)
        return {"success": True, "model": model, "message": "Pull started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bootstrap/check")
def check_environment():
    """
    Quick environment health check.
    Returns what is installed and what is missing.
    Called when wizard Step 4 mounts to see if setup is needed.
    """
    try:
        try:
            from backend.bootstrap import (
                check_packages_installed, is_ollama_installed, is_ollama_running
            )
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from bootstrap import (
                check_packages_installed, is_ollama_installed, is_ollama_running
            )

        packages_ok = check_packages_installed()
        ollama_installed = is_ollama_installed()
        ollama_running = is_ollama_running()

        return {
            "packages_installed": packages_ok,
            "ollama_installed": ollama_installed,
            "ollama_running": ollama_running,
            "needs_setup": not (packages_ok and ollama_installed)
        }
    except Exception as e:
        return {
            "packages_installed": False,
            "ollama_installed": False,
            "ollama_running": False,
            "needs_setup": True,
            "error": str(e)
        }


@app.post("/api/bootstrap/start-ollama")
def start_ollama_endpoint():
    """Start Ollama service if not already running."""
    try:
        try:
            from backend import bootstrap
        except ModuleNotFoundError:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import bootstrap
        import threading

        def _start():
            bootstrap.start_ollama()

        threading.Thread(target=_start, daemon=True).start()
        return {"success": True, "message": "Starting Ollama"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    
# =========================================================================
# SERVER LAUNCHER — Called from main.py
# =========================================================================

def start_api_server(host="127.0.0.1", port=7777):
    """
    Start the FastAPI server on a background thread.
    Called from main.py AFTER all modules are initialized.
    """
    import uvicorn
    
    def _run():
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False
        )
    
    thread = threading.Thread(target=_run, daemon=True, name="SevenAPI")
    thread.start()
    print(f"[API] Seven API server started on http://{host}:{port}")
    print(f"[API] Dashboard docs: http://{host}:{port}/api/docs")
    return thread