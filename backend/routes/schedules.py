"""
backend/routes/schedules.py
Handles: /api/schedules/*, /api/schedule/alert/*, /api/system/battery-alert
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import json as _json_alert

router = APIRouter()

# ── Alert file path ──
_ALERT_FILE = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'SEVEN', 'schedule_alert.json'
)

# ── In-memory alert state ──
_schedule_alert_container = [{"active": False, "message": "", "type": "", "id": None}]


class ScheduleCreate(BaseModel):
    type:       str
    message:    str
    time:       Optional[str] = None
    duration:   Optional[int] = None
    recur:      Optional[str] = None
    speaker_id: Optional[str] = "default"


# ── Internal helpers (also imported by main.py / brain.py) ──

def _write_alert_file(data: dict):
    try:
        with open(_ALERT_FILE, 'w') as f:
            _json_alert.dump(data, f)
    except Exception:
        pass


def _read_alert_file() -> dict:
    try:
        if os.path.exists(_ALERT_FILE):
            with open(_ALERT_FILE, 'r') as f:
                return _json_alert.load(f)
    except Exception:
        pass
    return {"active": False, "message": "", "type": "", "id": None}


def set_schedule_alert(message: str, stype: str, schedule_id=None):
    """Called by voice pipeline when a schedule fires."""
    data = {"active": True, "message": message, "type": stype, "id": schedule_id}
    _schedule_alert_container[0] = data
    _write_alert_file(data)
    print(f"[API] Schedule alert set: {stype} - {message[:50]}")


def dismiss_schedule_alert_sync():
    """Synchronous dismiss — called from brain.py without async context."""
    empty = {"active": False, "message": "", "type": "", "id": None}
    _schedule_alert_container[0] = empty
    _write_alert_file(empty)


# ── Endpoints ──

@router.get("/api/schedules")
def get_schedules():
    """Get all schedules."""
    import hands.scheduler as scheduler_mod
    return scheduler_mod.get_all_schedules()


@router.post("/api/schedules")
def create_schedule(sched: ScheduleCreate):
    """Create a new schedule. Enforces plan limit."""
    import hands.scheduler as scheduler_mod
    import license as license_module
    from backend.api_server import check_limit, plan_limit_error, get_current_tier

    try:
        all_schedules    = scheduler_mod.get_all_schedules()
        current_schedules = [s for s in (all_schedules or []) if s.get("status") == "active"]
        schedule_count   = len(current_schedules)
    except Exception:
        schedule_count = 0

    limit_check = check_limit("schedules", schedule_count)
    if not limit_check["allowed"]:
        raise plan_limit_error("schedules", limit_check)

    if sched.recur and sched.recur.strip():
        features = license_module.TIER_FEATURES.get(get_current_tier(), {})
        if not features.get("recurring_schedules", False):
            raise HTTPException(
                status_code=403,
                detail={
                    "error":      "feature_not_available",
                    "message":    "Recurring schedules require Pro plan or higher.",
                    "tier":       get_current_tier(),
                    "upgrade_to": "pro"
                }
            )

    params = {
        "action":     sched.type,
        "message":    sched.message,
        "speaker_id": sched.speaker_id
    }
    if sched.time:
        params["time"]     = sched.time
    if sched.duration is not None:
        params["duration"] = str(sched.duration)
    if sched.recur:
        params["recur"]    = sched.recur

    success, msg = scheduler_mod.manage_schedule(params)

    if success:
        return {
            "success": True,
            "message": msg,
            "usage": {
                "current": schedule_count + 1,
                "limit":   limit_check["limit"],
                "tier":    limit_check["tier"]
            }
        }
    else:
        raise HTTPException(status_code=400, detail=msg)


@router.delete("/api/schedules/{schedule_id}")
def cancel_schedule(schedule_id: int):
    """Cancel a specific schedule."""
    import hands.scheduler as scheduler_mod

    success, msg = scheduler_mod.cancel_schedule(schedule_id=schedule_id)
    if success:
        return {"success": True, "message": msg}
    else:
        raise HTTPException(status_code=404, detail=msg)


@router.get("/api/schedule/alert")
async def get_schedule_alert():
    """Get current schedule alert state."""
    return _read_alert_file()


@router.post("/api/schedule/alert/dismiss")
async def dismiss_schedule_alert():
    """Dismiss current schedule alert."""
    empty = {"active": False, "message": "", "type": "", "id": None}
    _schedule_alert_container[0] = empty
    _write_alert_file(empty)
    return {"ok": True}


@router.post("/api/schedule/alert/snooze")
async def snooze_schedule_alert(minutes: int = 5):
    """Snooze current alert by creating a new schedule."""
    if _schedule_alert_container[0].get("active"):
        try:
            from hands.scheduler import add_schedule
            add_schedule(
                stype="reminder",
                message=_schedule_alert_container[0]["message"],
                time_str=f"in {minutes} minutes",
                speaker_id="default"
            )
        except Exception as e:
            print(f"[API] Snooze reschedule failed: {e}")
    empty = {"active": False, "message": "", "type": "", "id": None}
    _schedule_alert_container[0] = empty
    _write_alert_file(empty)
    return {"ok": True}


@router.post("/api/system/battery-alert")
async def battery_alert(request: Request):
    """Daemon calls this when battery is low — Seven speaks it."""
    from backend.api_server import set_state
    try:
        body = await request.json()
        message = body.get("message", "Battery low")
    except Exception:
        message = "Battery low"
    try:
        set_state("battery_alert_msg", message)
        set_state("battery_alert_pending", True)
    except Exception:
        pass
    return {"ok": True}