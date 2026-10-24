"""
brain_modules/followups.py

Short follow-ups to the last adjustable action: "set brightness to 60" then "make it 0", "70", "a bit more", "lower".
"make seven 50% transparent" then "make it 70".

brain.think() calls remember() with every reply that carried an action tag; layer_45_system calls resolve() before
anything else. A follow-up only counts for a few turns after the action, so "make it 0" much later is not misread.
"""

import re
from typing import Optional

_TTL_TURNS = 4

_NUMBER = re.compile(r"^(?:(?:please )?(?:make|set|change|put|turn|bring|keep|drop|raise)(?: it| that| this)?"
                     r"(?: (?:up|down))?(?: to| at)? )?(\d{1,3})\s*(?:%|percent)?$")
_MORE = re.compile(r"^(?:a (?:bit|little|tad) )?(?:more|higher|up|louder|brighter|increase it|turn it up|"
                   r"(?:make it )?(?:a bit |a little )?(?:louder|brighter|higher|more))$")
_LESS = re.compile(r"^(?:a (?:bit|little|tad) )?(?:less|lower|down|quieter|softer|dimmer|decrease it|turn it down|"
                   r"(?:make it )?(?:a bit |a little )?(?:quieter|dimmer|lower|less|softer))$")
_SET_ACTIONS = {"volume": "volume_set", "brightness": "brightness_set"}


def _params(tag_body: str) -> dict:
    return dict(p.split("=", 1) for p in tag_body.split() if "=" in p)


def remember(state, reply: str) -> None:
    """Keep the last action a number can adjust."""
    if state is None or not reply:
        return
    for kind, body in re.findall(r"###(SYS|WINDOW):\s*([^#]+)", reply):
        p = _params(body.strip())
        action = p.get("action", "")
        domain = next((d for d in _SET_ACTIONS if action.startswith(d)), None)
        if kind == "SYS" and domain:
            state.last_adjustable = {"kind": "SYS", "domain": domain, "turn": state.turn}
        elif kind == "WINDOW" and action in ("transparent", "solid"):
            state.last_adjustable = {"kind": "WINDOW", "domain": "opacity", "target": p.get("target", "this"),
                                     "turn": state.turn}


def resolve(state, text: str) -> Optional[str]:
    """The reply with its action tag for a follow-up, or None when the text is not one."""
    last = getattr(state, "last_adjustable", None)
    if not last or state.turn - last["turn"] > _TTL_TURNS:
        return None
    t = (text or "").lower().strip(" .!?")
    number = _NUMBER.match(t)
    more, less = bool(_MORE.match(t)), bool(_LESS.match(t))
    if not (number or more or less):
        return None

    if last["kind"] == "SYS":
        domain = last["domain"]
        if number:
            value = max(0, min(100, int(number.group(1))))
            return f"{domain.title()} to {value}%. ###SYS: action={_SET_ACTIONS[domain]} value={value}"
        step = "up" if more else "down"
        return f"{domain.title()} {step}. ###SYS: action={domain}_{step} value=10"

    target = last.get("target", "this")
    if number:
        value = max(10, min(100, int(number.group(1))))
        return f"{target.title()} at {value}% opacity. ###WINDOW: action=transparent target={target} opacity={value / 100:.2f}"
    return (f"{'More' if more else 'Less'} see-through. "
            f"###WINDOW: action=transparent target={target} opacity={'more' if more else 'less'}")
