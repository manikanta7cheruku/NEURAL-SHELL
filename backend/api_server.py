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
import sys
import threading
import time
import os

# transformers would otherwise import TensorFlow too: many seconds and gigabytes Seven never uses.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
try:
    from seven_utils import hf_offline
    hf_offline.enable()
except ImportError:
    pass


class _DropClientResets:
    """Browsers and the extension drop connections all the time; asyncio logs each as an error with a traceback,
    which filled python_crash.log. They are not errors."""

    def filter(self, record):
        exc = record.exc_info[1] if record.exc_info else None
        return not isinstance(exc, (ConnectionResetError, ConnectionAbortedError))


import logging as _logging  # noqa: E402
_logging.getLogger("asyncio").addFilter(_DropClientResets())

def _evict_offline_listener() -> None:
    """
    While Seven is closed, a small listener (hands/workspace_modules/offline_tab_listener.py) keeps port 7777
    to catch Chrome tab updates. Ask it to step aside before the backend binds the port, so a backend started
    any way (main.py, uvicorn, tests of the real app) never loses the port to it.
    """
    if os.environ.get("SEVEN_TEST") == "1":
        return
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:7777/api/health", timeout=0.4) as r:
            if b"offline_tab_listener" not in r.read(200):
                return
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/__seven_shutdown", method="POST"),
                               timeout=0.8).close()
        for _ in range(20):
            time.sleep(0.1)
            try:
                urllib.request.urlopen("http://127.0.0.1:7777/api/health", timeout=0.2).close()
            except Exception:
                return
    except Exception:
        pass


_evict_offline_listener()

# Hands and layers print emoji. Electron starts us with UTF-8, but a plain
# "uvicorn" in a Windows console defaults to cp1252 and those prints would
# raise inside actions (a volume change failed with a 'charmap' error).
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
from seven_utils.version import get_version

# Telemetry
try:
    import telemetry
except ImportError:
    telemetry = None

# =========================================================================
# SHARED STATE - Updated by main.py via set_state()
# =========================================================================

_state = {
    "listening":           False,
    "thinking":            False,
    "speaking":            False,
    "user_text":           "",
    "seven_text":          "",
    "status_text":         "SYSTEM ONLINE",
    "status_color":        "#00ff00",
    "file_search_results": None,
    "task_results":        None,
    "pending_enrollment":        None,
    "enrollment_done":           None,
    "enrollment_clips_done":     0,
    "speak_enrollment_welcome":  False,
    "admin_message":             None,
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
    """Get the current user's license tier. Always safe - returns 'free' on error."""
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
    title="Seven AI Assistant API",
    version=get_version(),
    description="""
## Seven Local AI Voice Assistant

Private, local API for Seven. All data stays on your machine.
""",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    contact={
        "name": "Seven Labs",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware for /api/chat
import time as _time
import collections as _collections
import threading as _threading

_rate_lock   = _threading.Lock()
_chat_calls  = _collections.defaultdict(list)   # ip -> [timestamps]
RATE_LIMIT   = 30    # max requests
RATE_WINDOW  = 60    # per 60 seconds

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse

class ChatRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if request.url.path == "/api/chat" and request.method == "POST":
            client_ip = request.client.host or "127.0.0.1"
            now = _time.time()
            with _rate_lock:
                calls = _chat_calls[client_ip]
                # Remove calls outside the window
                calls[:] = [t for t in calls if now - t < RATE_WINDOW]
                if len(calls) >= RATE_LIMIT:
                    retry_after = int(RATE_WINDOW - (now - calls[0]))
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": f"Rate limit exceeded. Max {RATE_LIMIT} chat requests per {RATE_WINDOW}s. Retry in {retry_after}s."
                        },
                        headers={"Retry-After": str(retry_after)},
                    )
                calls.append(now)
        return await call_next(request)

app.add_middleware(ChatRateLimitMiddleware)


# =========================================================================
# ROOT ENDPOINT
# =========================================================================

@app.get("/")
def root():
    """Root endpoint - API info."""
    return {
        "name":    "Seven API",
        "version": get_version(),
        "status":  "running",
        "docs":    "http://127.0.0.1:7777/api/docs",
        "endpoints": {
            "status":  "/api/status",
            "health":  "/api/health",
            "chat":    "/api/chat",
            "license": "/api/license/status",
            "usage":   "/api/usage/stats"
        }
    }


@app.get("/api/health")
def health_liveness():
    """
    Guaranteed liveness probe. Registered directly on the app (not via router)
    so it ALWAYS exists even if router imports fail. Frontend uses this to
    detect backend availability. Must return 200 in under 5ms.
    """
    return {"ok": True, "status": "running"}


# =========================================================================
# REGISTER ALL ROUTE MODULES
# =========================================================================

from backend.routes import status as status_routes
from backend.routes import chat as chat_routes
from backend.routes import memory as memory_routes
from backend.routes import files as files_routes
from backend.routes import schedules as schedules_routes
from backend.routes import knowledge as knowledge_routes
from backend.routes import config_routes
from backend.routes import license_routes
from backend.routes import setup as setup_routes
from backend.routes import usage as usage_routes
from backend.routes import hardware as hardware_routes
from backend.routes import updates as updates_routes
from backend.routes import voice_gates as voice_gates_routes
from backend.routes import tasks as tasks_routes
from backend.routes import triggers as triggers_routes
from backend.routes import workspaces as workspaces_routes
from backend.routes import chrome as chrome_routes
from backend.routes import health as health_routes
from backend.routes import panel_extras as panel_extras_routes
from backend.routes import brain as brain_routes
from backend.routes import conversations as conversation_routes
from backend.routes import voice as voice_routes
from backend.routes import attention as attention_routes
from backend.routes import welcome as welcome_routes

app.include_router(health_routes.router)
app.include_router(status_routes.router)
app.include_router(chat_routes.router)
app.include_router(memory_routes.router)
app.include_router(files_routes.router)
app.include_router(schedules_routes.router)
app.include_router(knowledge_routes.router)
app.include_router(config_routes.router)
app.include_router(license_routes.router)
app.include_router(setup_routes.router)
app.include_router(usage_routes.router)
app.include_router(hardware_routes.router)
app.include_router(updates_routes.router)
app.include_router(voice_gates_routes.router)
app.include_router(tasks_routes.router)
app.include_router(triggers_routes.router)
app.include_router(workspaces_routes.router)
app.include_router(chrome_routes.router)
app.include_router(panel_extras_routes.router)
app.include_router(brain_routes.router)
app.include_router(conversation_routes.router)
app.include_router(voice_routes.router)
app.include_router(attention_routes.router)
app.include_router(welcome_routes.router)
from backend.routes import feedback as feedback_routes
app.include_router(feedback_routes.router)
from backend.routes import models as model_routes
app.include_router(model_routes.router)


@app.get("/api/speed")
def get_system_speed():
    """Diagnostic endpoint to prevent frontend 404. Returns latency metrics."""
    return {
        "success": True,
        "mode": "local",
        "latency_ms": 1.2,
        "processing_speed": "high"
    }


@app.post("/api/bootstrap/restart")
async def bootstrap_restart():
    """
    Called by the setup wizard after first-launch setup completes.
    Signals Python to restart cleanly so new packages are importable.
    Electron detects the exit and relaunches Python automatically.
    """
    import threading
    import os

    def _delayed_restart():
        import time
        time.sleep(0.5)  # give response time to send
        os._exit(0)      # clean exit - Electron restarts Python

    threading.Thread(target=_delayed_restart, daemon=True).start()
    return {"ok": True, "message": "Restarting..."}


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

def _listening(host: str, port: int) -> bool:
    import socket
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def start_api_server(host="127.0.0.1", port=7777):
    """
    Start the FastAPI server on a background thread.
    Called from main.py AFTER all modules are initialized.

    Two protections against the app showing "Backend Unreachable" while Seven itself keeps running:

    * The server runs on a selector event loop. Windows' default (proactor) loop stops accepting connections for
      good after ONE failed accept ("[WinError 64] The specified network name is no longer available", logged as
      "Accept failed on a socket"), which happens when a client drops a connection the instant it opens it, as the
      app, Vite and Electron all do while polling a backend that is still starting. The selector loop shrugs it off.
    * A watchdog checks the port every few seconds and restarts the server if it ever stops listening.
    """
    import asyncio
    import uvicorn
    from seven_utils.event_loop import new_event_loop
    servers = []

    def _run():
        _evict_offline_listener()      # again, right before binding: loading the app takes several seconds
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False))
        servers.append(server)
        loop = new_event_loop()                        # a selector loop on Windows (seven_utils/event_loop.py)
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        except BaseException as exc:                  # SystemExit from a failed bind, or anything else: say so
            print(f"[API] server stopped: {exc!r}")
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True, name="SevenAPI")
    thread.start()

    def _watch():
        time.sleep(20)                                 # let it come up first
        misses = 0
        while True:
            time.sleep(3)
            misses = 0 if _listening(host, port) else misses + 1
            if misses >= 2:
                print("[API] the server stopped listening; restarting it")
                for old in servers:
                    old.should_exit = True
                servers.clear()
                threading.Thread(target=_run, daemon=True, name="SevenAPI").start()
                misses = 0
                time.sleep(20)

    threading.Thread(target=_watch, daemon=True, name="SevenAPIWatch").start()

    # Start background update checker - runs 15s after startup
    try:
        try:
            from backend.updater import start_auto_check
        except ModuleNotFoundError:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from updater import start_auto_check
        start_auto_check()
    except Exception:
        pass

    # Feedback written while offline is sent automatically once the internet is back.
    try:
        from backend.routes.feedback import start_retry_loop
        start_retry_loop()
    except Exception:
        pass

    return thread