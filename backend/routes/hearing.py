"""
backend/routes/hearing.py
Why isn't Seven hearing me? Answered inside the app (ears/doctor.py).

    GET /api/hearing   {issues: [{id, level, title, detail, fix}], live: {...numbers for the meter}, events: [...], log: [...]}

Settings, System, Hearing polls this about twice a second to draw a live microphone meter next to the list of problems; the home
screen's strip reads the same list through /api/attention. Every change in the list is also written to logs\\hearing_debug.log.
"""
import sys

from fastapi import APIRouter

router = APIRouter()


def snapshot():
    """(issues, stats, state): what the ears are doing and what is wrong with it. Never raises: a broken probe is a missing number."""
    try:
        from backend.api_server import _state
        state = dict(_state)
    except Exception:
        state = {}
    stats = None
    ears = sys.modules.get("ears.core")
    try:
        stats = ears.hearing_stats() if ears is not None and hasattr(ears, "hearing_stats") else None
    except Exception:
        stats = None
    from ears import doctor
    issues = doctor.assess(stats, state)
    doctor.record(issues, stats)
    return issues, stats, state


@router.get("/api/hearing", summary="Why isn't Seven hearing me?")
def hearing():
    from ears import doctor
    issues, stats, state = snapshot()
    ears = sys.modules.get("ears.core")
    recent = list(getattr(ears, "RECENT", []))[-12:] if ears is not None else []
    return {"issues": issues, "live": doctor.live(stats, state),
            "events": [{"at": t, "outcome": o} for t, o in recent], "log": doctor.recent_log(5)}
