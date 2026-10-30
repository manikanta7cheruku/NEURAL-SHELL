"""
backend/routes/companion.py
Seven's own chat thread: the friend side of Seven (the companion/ package).

    GET  /api/companion/state    the thread's id, unread count, the person's settings, today's count, any snooze
    POST /api/companion/read     the thread was opened: everything in it counts as read
    POST /api/companion/snooze   {"minutes": 60}: no messages for a while (0 ends it)
    POST /api/companion/nudge    "Ask me something": one message now, written into the thread

The settings themselves are ordinary config ("companion", saved with PUT /api/config) and are normalised by
companion/settings.py. Seven's messages and the person's replies are normal conversation messages, read through the
conversation routes.
"""
import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class Snooze(BaseModel):
    minutes: int = Field(60, ge=0, le=24 * 60)


@router.get("/api/companion/state", summary="Seven's thread: unread, settings, today")
def state():
    from companion import engine, settings, store
    now = datetime.datetime.now()
    cfg = settings.get()
    until = store.get_state("snooze_until")
    return {
        "conversation_id": engine.conversation_id(),
        "unread": store.unread_count(),
        "settings": cfg,
        "snoozed_until": until if engine.snoozed(now) else None,
        "quiet_now": settings.in_quiet_hours(cfg, now),
        "today": {"sent": store.sent_today(now.date()), "target": settings.daily_target(cfg, now.date())},
    }


@router.post("/api/companion/read", summary="The thread was opened")
def mark_read():
    from companion import engine, store
    n = store.mark_read_all()
    engine._publish_unread()
    return {"read": n}


@router.post("/api/companion/snooze", summary="No messages for a while")
def snooze(req: Snooze):
    from companion import store
    until = (datetime.datetime.now() + datetime.timedelta(minutes=req.minutes)).strftime(store.FMT) if req.minutes else None
    store.set_state("snooze_until", until)
    return {"snoozed_until": until}


@router.post("/api/companion/nudge", summary="Ask me something")
def nudge():
    from companion import engine
    msg_id = engine.nudge()
    if msg_id is None:
        raise HTTPException(status_code=409, detail="Seven has nothing new to ask right now.")
    return {"message_id": msg_id}
