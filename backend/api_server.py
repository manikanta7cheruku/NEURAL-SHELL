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

from fastapi import FastAPI, HTTPException, UploadFile, File
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
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:7777", "app://.", "file://"],
    allow_credentials=True,
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
    """Get current Seven system status."""
    import config
    from memory.mood import mood_engine

    # Track activity (dashboard polling = user is active)
    try:
        import telemetry
        telemetry.log_activity()
    except:
        pass
    
    uptime_secs = int(time.time() - _start_time)
    hours = uptime_secs // 3600
    minutes = (uptime_secs % 3600) // 60
    
    mood_status = mood_engine.get_status()
    
    return {
        "listening": _state.get("listening", False),
        "speaking": _state.get("speaking", False),
        "thinking": _state.get("thinking", False),
        "mood": mood_status["label"],
        "mood_value": mood_status["mood_value"],
        "model": config.KEY.get("brain", {}).get("model_name", "unknown"),
        "streaming": config.KEY.get("brain", {}).get("streaming", False),
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": uptime_secs,
        "speaker": _state.get("current_speaker", "default"),
        "version": config.KEY.get("version", "1.10")
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
        
        # Store conversation in memory
        try:
            from memory import seven_memory
            if len(req.text.strip()) > 3 and not full_response.strip().startswith("###"):
                clean_for_memory = re.sub(r'###\w+:\s*\S+', '', full_response).strip()
                if clean_for_memory:
                    seven_memory.store_conversation(req.text.strip(), clean_for_memory,
                                                     user_id=req.speaker_id)
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
                    scheduler_mod.manage_schedule(params)
                    telemetry.log_activity()  # Track schedule creation
    
    # App commands
    app_cmds = re.findall(r"###(OPEN|CLOSE):\s*(.*?)(?=###|$)", full_response)
    for cmd_type, arg in app_cmds:
        clean_arg = arg.replace('"', '').replace("'", "").replace(",", "").replace(".", "").strip()
        if not clean_arg:
            continue
        if cmd_type == "OPEN":
            core.open_app(clean_arg)
            telemetry.log_activity()  # Track app open
        elif cmd_type == "CLOSE":
            core.close_app(clean_arg)
            telemetry.log_activity()  # Track app close


# =========================================================================
# MEMORY ENDPOINTS
# =========================================================================

@app.post("/api/memory/facts")
def add_manual_fact(data: dict):
    """Manually add a fact."""
    from memory import seven_memory
    
    text = data.get("text", "").strip()
    category = data.get("category", "manual")
    
    if not text:
        raise HTTPException(status_code=400, detail="Empty fact text")
    
    try:
        seven_memory.store_fact(text, category=category)
        return {"success": True, "fact": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/api/memory/facts")
def get_facts():
    """Get all stored facts."""
    from memory import seven_memory
    
    try:
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
    from memory import seven_memory
    
    try:
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


@app.get("/api/memory/stats")
def get_memory_stats():
    """Get memory statistics."""
    from memory import seven_memory
    
    stats = seven_memory.get_stats()
    
    # Calculate storage size
    memory_dir = "./seven_data/memory"
    storage_bytes = 0
    if os.path.exists(memory_dir):
        for root, dirs, files in os.walk(memory_dir):
            for f in files:
                storage_bytes += os.path.getsize(os.path.join(root, f))
    
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
    """Create a new schedule."""
    import hands.scheduler as scheduler_mod
    
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
        return {"success": True, "message": msg}
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


@app.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = File(...)):
    """Upload a file to the knowledge base."""
    try:
        from knowledge.indexer import index_file
        
        # Save uploaded file to knowledge sources directory
        sources_dir = "seven_data/knowledge"
        os.makedirs(sources_dir, exist_ok=True)
        
        file_path = os.path.join(sources_dir, file.filename)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Index the file
        chunks = index_file(file_path)
        
        return {
            "success": True,
            "filename": file.filename,
            "chunks_indexed": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """Add or update an app alias."""
    import config
    
    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    if "app_aliases" not in config.KEY["commands"]:
        config.KEY["commands"]["app_aliases"] = {}
    
    config.KEY["commands"]["app_aliases"][alias.name.lower().strip()] = alias.target.lower().strip()
    config.save_config()
    
    return {"success": True, "alias": alias.name, "target": alias.target}


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
    """Add or update a custom app path."""
    import config
    
    if "commands" not in config.KEY:
        config.KEY["commands"] = {}
    if "app_paths" not in config.KEY["commands"]:
        config.KEY["commands"]["app_paths"] = {}
    
    # Validate path exists
    if not os.path.exists(app_path.path):
        raise HTTPException(status_code=400, detail=f"Path does not exist: {app_path.path}")
    
    config.KEY["commands"]["app_paths"][app_path.name.lower().strip()] = app_path.path
    config.save_config()
    
    return {"success": True, "name": app_path.name, "path": app_path.path}


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
    """Get current license status."""
    validation = license_module.validate_license()
    features = license_module.get_features(validation["tier"])
    
    device_id = license_module.get_device_id()
    
    # Get license key from config
    import config
    license_key = config.KEY.get("license", {}).get("key", "")
    is_trial = config.KEY.get("license", {}).get("is_trial", False)
    
    return {
        "tier": validation["tier"],
        "valid": validation["valid"],
        "expires_at": validation.get("expires_at"),
        "days_until_expiry": validation.get("days_until_expiry"),
        "offline_mode": validation.get("offline_mode", False),
        "offline_days": validation.get("offline_days", 0),
        "features": features,
        "license_key": license_key,
        "is_trial": is_trial,
        "device_id": device_id[:8] + "..."
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
def get_usage_stats_fixed():
    """Get current user's total usage time - reads from BOTH databases."""
    import sqlite3
    
    # Get device_id
    device_id = None
    try:
        import license as license_module
        device_id = license_module.get_device_id()
    except Exception as e:
        print(f"[API] Could not get device_id: {e}")
    
    # Get email
    email = None
    try:
        import telemetry as telemetry_module
        email = telemetry_module.get_email()
    except Exception as e:
        print(f"[API] Could not get email: {e}")
    
    total_hours = 0
    last_seen = None
    
    # 1. Check telemetry.db (primary source)
    telemetry_db = "data/telemetry.db"
    if os.path.exists(telemetry_db):
        try:
            conn = sqlite3.connect(telemetry_db)
            c = conn.cursor()
            
            if device_id:
                c.execute("SELECT active_hours, last_seen, email FROM stats WHERE device_id = ?", (device_id,))
            else:
                c.execute("SELECT active_hours, last_seen, email FROM stats ORDER BY last_seen DESC LIMIT 1")
            
            row = c.fetchone()
            if row:
                total_hours = row[0] or 0
                last_seen = row[1]
                if not email and row[2]:
                    email = row[2]
            
            conn.close()
        except Exception as e:
            print(f"[API] Usage stats telemetry.db error: {e}")
    
    # 2. Also check license.db (backup source)
    license_db = "data/license.db"
    if os.path.exists(license_db) and device_id:
        try:
            conn = sqlite3.connect(license_db)
            c = conn.cursor()
            
            c.execute("SELECT usage_hours, last_validated FROM activations WHERE device_id = ?", (device_id,))
            row = c.fetchone()
            if row:
                license_hours = row[0] or 0
                # Use the higher value
                if license_hours > total_hours:
                    total_hours = license_hours
                    last_seen = row[1]
            
            conn.close()
        except Exception as e:
            print(f"[API] Usage stats license.db error: {e}")
    
    # 3. Add current session time (not yet saved to DB)
    try:
        import telemetry as telemetry_module
        session_hours = telemetry_module.get_active_hours()
        total_hours += session_hours
    except Exception as e:
        print(f"[API] Could not get session hours: {e}")
    
    # Convert to human readable
    total_minutes = int(total_hours * 60)
    
    if total_minutes < 1:
        time_str = "0 min"
    elif total_minutes < 60:
        time_str = f"{total_minutes} min"
    else:
        hrs = total_minutes // 60
        mins = total_minutes % 60
        if mins == 0:
            time_str = f"{hrs} hr"
        else:
            time_str = f"{hrs} hr {mins} min"
    
    return {
        "total_hours": round(total_hours, 4),
        "total_minutes": total_minutes,
        "display": time_str,
        "email": email,
        "device_id": device_id[:8] + "..." if device_id else None,
        "last_seen": last_seen
    }


@app.get("/api/usage/history")
def get_usage_history_fixed():
    """Get actual daily usage for last 7 days."""
    import sqlite3
    from datetime import datetime, timedelta
    
    device_id = None
    try:
        import license as license_module
        device_id = license_module.get_device_id()
    except:
        pass
    
    # Build last 7 days list
    history = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i))
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "day": date.strftime("%a"),
            "hours": 0.0,
            "minutes": 0
        })
    
    # Get actual data from daily_usage table
    telemetry_db = "data/telemetry.db"
    if os.path.exists(telemetry_db) and device_id:
        try:
            conn = sqlite3.connect(telemetry_db)
            c = conn.cursor()
            
            # Get last 7 days of daily usage
            seven_days_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
            
            c.execute("""
                SELECT date, hours FROM daily_usage
                WHERE device_id = ? AND date >= ?
                ORDER BY date ASC
            """, (device_id, seven_days_ago))
            
            # Map actual data to history
            actual_data = {row[0]: row[1] for row in c.fetchall()}
            conn.close()
            
            # Fill in actual hours
            for day in history:
                if day["date"] in actual_data:
                    day["hours"] = round(actual_data[day["date"]], 3)
                    day["minutes"] = int(actual_data[day["date"]] * 60)
        
        except Exception as e:
            print(f"[API] Usage history error: {e}")
    
    total_hours = sum(d["hours"] for d in history)
    
    return {
        "history": history,
        "total_hours": round(total_hours, 3)
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

    # Register referral if provided
    if req.referral_code and req.referral_code.strip():
        try:
            import server_sync
            import license as license_module
            device_id = license_module.get_device_id()
            server_sync.register_referral(
                device_id=device_id,
                referral_code=req.referral_code.strip(),
                email=email
            )
        except Exception:
            pass

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
    from backend.updater import get_state, _read_current_version
    state = get_state()
    return {
        **state,
        "current_version": _read_current_version(),
    }


@app.post("/api/update/check")
def trigger_update_check():
    """Force an immediate update check (user clicked 'Check Now')."""
    from backend.updater import check_for_updates
    check_for_updates(force=True)
    return {"success": True, "message": "Check started"}


@app.post("/api/update/download")
def trigger_download():
    """
    Start downloading the update in background.
    Only valid when update_available is True and download_mode is 'manual'.
    """
    from backend import updater
    state = updater.get_state()

    if not state["update_available"]:
        raise HTTPException(status_code=400, detail="No update available")
    if state["downloading"]:
        raise HTTPException(status_code=400, detail="Download already in progress")

    updater.start_download_thread()
    return {"success": True, "message": "Download started"}


@app.post("/api/update/install")
def trigger_install():
    """
    Signal Electron to run the downloaded installer and quit the app.
    Only valid when download_path exists.
    """
    from backend import updater
    state = updater.get_state()

    path = state.get("download_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Installer not downloaded yet")

    # We return the path — Electron picks it up via IPC
    # The React frontend calls window.electron.runInstaller(path)
    return {"success": True, "installer_path": path}

# =========================================================================
# BOOTSTRAP ENDPOINTS (Phase 7 — First Launch Setup)
# =========================================================================

@app.get("/api/bootstrap/status")
def get_bootstrap_status():
    """
    Poll this endpoint to get live environment setup progress.
    React wizard Step 4 polls this every 500ms.
    """
    from backend.bootstrap import get_state
    return get_state()


@app.post("/api/bootstrap/start")
def start_bootstrap():
    """
    Start the environment setup sequence.
    Runs: pip install → Ollama download → Ollama start
    Returns immediately. Poll /api/bootstrap/status for progress.
    """
    from backend import bootstrap
    bootstrap.run_environment_setup()
    return {"success": True, "message": "Bootstrap started"}


@app.post("/api/bootstrap/pull-model")
def pull_model_endpoint(data: dict):
    """
    Start pulling an Ollama model.
    Body: {"model": "llama3"}
    Poll /api/bootstrap/status for progress under model_pull key.
    """
    from backend import bootstrap
    model = data.get("model", "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model name required")

    bootstrap.run_model_pull(model)
    return {"success": True, "model": model, "message": "Pull started"}


@app.get("/api/bootstrap/check")
def check_environment():
    """
    Quick environment health check.
    Returns what is installed and what is missing.
    Called when wizard Step 4 mounts to see if setup is needed.
    """
    from backend.bootstrap import (
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


@app.post("/api/bootstrap/start-ollama")
def start_ollama_endpoint():
    """Start Ollama service if not already running."""
    from backend import bootstrap
    import threading

    def _start():
        bootstrap.start_ollama()

    threading.Thread(target=_start, daemon=True).start()
    return {"success": True, "message": "Starting Ollama"}
    
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