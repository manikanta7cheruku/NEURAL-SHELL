"""
=============================================================================
PROJECT SEVEN - backend/api_server.py (Orchestrator)
Version: 1.2.7

PURPOSE:
    FastAPI app creation + shared state + plan limit helpers.
    Registers all route modules via APIRouter.
    Starts the uvicorn server on a background thread.

    All endpoint logic lives in backend/routes/*.py
    This file is the entry point and shared state owner.

ARCHITECTURE:
    Modular Monolith — Intra-module decomposition (APIRouter pattern)
    One process. One port (7777). 12 route modules.
=============================================================================
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import threading
import time
import os

# Telemetry
try:
    import telemetry
except ImportError:
    telemetry = None

# =========================================================================
# SHARED STATE — Updated by main.py via set_state()
# =========================================================================

_state = {
    "listening":          False,
    "thinking":           False,
    "speaking":           False,
    "user_text":          "",
    "seven_text":         "",
    "status_text":        "SYSTEM ONLINE",
    "status_color":       "#00ff00",
    "file_search_results": None,   # set by brain.py Layer 4.3 when file search runs
}

_start_time = time.time()


def set_state(key, value):
    """Called by main.py to update shared state."""
    _state[key] = value


def get_state():
    """Get current state dict."""
    return dict(_state)


# =========================================================================
# PLAN LIMIT HELPERS — Imported by all route modules
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
    Returns dict with: allowed, current, limit, tier, upgrade_needed
    """
    import license as license_module

    tier     = get_current_tier()
    features = license_module.TIER_FEATURES.get(tier, license_module.TIER_FEATURES["free"])
    limit    = features.get(feature, 0)

    if limit == -1:
        return {"allowed": True, "current": current_count, "limit": -1, "tier": tier, "upgrade_needed": None}

    allowed        = current_count < limit
    upgrade_needed = None
    if not allowed:
        upgrade_needed = "pro" if tier == "free" else ("ultimate" if tier == "pro" else None)

    return {
        "allowed":        allowed,
        "current":        current_count,
        "limit":          limit,
        "tier":           tier,
        "upgrade_needed": upgrade_needed
    }


def plan_limit_error(feature_name: str, limit_check: dict) -> HTTPException:
    """Build a clean 403 error when user hits their plan limit."""
    tier    = limit_check["tier"]
    limit   = limit_check["limit"]
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

    return HTTPException(status_code=403, detail={
        "error":           "plan_limit_reached",
        "message":         f"You have reached the {tier.upper()} plan limit of {limit} {item_name}. You currently have {current}.",
        "current":         current,
        "limit":           limit,
        "tier":            tier,
        "upgrade_to":      upgrade,
        "upgrade_message": f"Upgrade to {upgrade.upper()} to get more {item_name}."
    })


# =========================================================================
# APP CREATION
# =========================================================================

app = FastAPI(
    title="Seven API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================================
# ROOT ENDPOINT
# =========================================================================

@app.get("/")
def root():
    """Root endpoint — API info."""
    return {
        "name":    "Seven API",
        "version": "1.0.0",
        "status":  "running",
        "docs":    "http://127.0.0.1:7777/api/docs",
        "endpoints": {
            "status":  "/api/status",
            "chat":    "/api/chat",
            "license": "/api/license/status",
            "usage":   "/api/usage/stats"
        }
    }


# =========================================================================
# REGISTER ALL ROUTE MODULES
# =========================================================================

from backend.routes import status as status_routes
from backend.routes import chat as chat_routes
from backend.routes import memory as memory_routes
from backend.routes import schedules as schedules_routes
from backend.routes import knowledge as knowledge_routes
from backend.routes import config_routes
from backend.routes import license_routes
from backend.routes import setup as setup_routes
from backend.routes import usage as usage_routes
from backend.routes import hardware as hardware_routes
from backend.routes import updates as updates_routes
from backend.routes import voice_gates as voice_gates_routes

app.include_router(status_routes.router)
app.include_router(chat_routes.router)
app.include_router(memory_routes.router)
app.include_router(schedules_routes.router)
app.include_router(knowledge_routes.router)
app.include_router(config_routes.router)
app.include_router(license_routes.router)
app.include_router(setup_routes.router)
app.include_router(usage_routes.router)
app.include_router(hardware_routes.router)
app.include_router(updates_routes.router)
app.include_router(voice_gates_routes.router)

# Register knowledge upload (needs special handling for optional multipart)
from backend.routes.knowledge import _register_upload_endpoint
_register_upload_endpoint(app)


# =========================================================================
# BACKWARD COMPATIBILITY EXPORTS
# These are called by main.py and brain.py directly.
# They must stay in this file.
# =========================================================================

# set_schedule_alert is called by voice pipeline when schedule fires
from backend.routes.schedules import set_schedule_alert, dismiss_schedule_alert_sync

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

    # Start background update checker — runs 15s after startup
    try:
        try:
            from backend.updater import start_auto_check
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from updater import start_auto_check
        start_auto_check()
        print("[API] Update auto-check scheduled")
    except Exception as e:
        print(f"[API] Update auto-check failed to start: {e}")

    return thread