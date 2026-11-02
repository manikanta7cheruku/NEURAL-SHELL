"""
backend/routes/diagnostics.py
A report of what works and what does not on this PC (backend/diagnostics.py), and the way out of safe mode.

    GET  /api/diagnostics/report   the report as plain text: open it in a browser, copy it, send it to the Seven team
    GET  /api/diagnostics          the same as data
    POST /api/safe-mode/retry      leave safe mode and start Seven again
"""
import os
import threading

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/api/diagnostics/report", response_class=PlainTextResponse, summary="Health report as text")
def report_text():
    from backend import diagnostics
    return PlainTextResponse(diagnostics.report_text(), headers={"Cache-Control": "no-store"})


@router.get("/api/diagnostics", summary="Health report as data")
def report_data():
    from backend import diagnostics
    return diagnostics.collect()


@router.post("/api/safe-mode/retry", summary="Leave safe mode and start again")
def retry_safe_mode():
    """Forget the failed starts and restart the backend (the app starts it again by itself)."""
    from main_modules.startup import safe_mode
    safe_mode.clear(os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SEVEN", "safe_mode.flag"))
    threading.Timer(0.6, lambda: os._exit(0)).start()
    return {"ok": True, "restarting": True}
