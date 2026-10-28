"""
backend/routes/welcome.py
The first-run welcome: the spoken tour, and the welcome card's hint.

    GET  /api/welcome              {tour_done, hint_dismissed, first_command}
    POST /api/welcome/hint/hide    stop showing the "getting started" hint
    POST /api/welcome/hint/show    show it again
    POST /api/tour/skip            stop the spoken tour and go straight to the card
    POST /api/tour/ack             the screen opened the card
    POST /api/tour/replay          run the tour again
"""
from fastapi import APIRouter, HTTPException

from main_modules.startup import greeting, tour

router = APIRouter()


@router.get("/api/welcome", summary="First-run welcome state")
def get_welcome():
    return greeting.welcome_state()


@router.post("/api/welcome/hint/hide", summary="Hide the getting-started hint")
def hide_hint():
    return greeting.update_welcome(hint_dismissed=True)


@router.post("/api/welcome/hint/show", summary="Show the getting-started hint again")
def show_hint():
    return greeting.update_welcome(hint_dismissed=False)


@router.post("/api/tour/skip", summary="Skip the spoken tour")
def skip_tour():
    return {"ok": tour.skip()}


@router.post("/api/tour/ack", summary="The welcome card is open")
def ack_tour():
    tour.acknowledge()
    return {"ok": True}


@router.post("/api/tour/replay", summary="Replay the welcome tour")
def replay_tour():
    if not tour.replay():
        raise HTTPException(status_code=409, detail="Seven isn't ready to give the tour yet.")
    return {"ok": True}
