"""
=============================================================================
LAYER 4.5f: WINDOW COMMAND DETECTION

Catches window management commands:
    minimize, maximize, snap, focus, tile, layout, transparent, pin, etc.

Emits ###WINDOW: tag with TARS-style speech response.

Uses existing brain_modules/command_router.py _build_window_tag().
=============================================================================
"""

import random
from brain_modules.layer_result import LayerResult
from brain_modules.command_router import _build_window_tag


_WINDOW_VERBS = [
    "minimize", "maximise", "maximize", "restore", "snap",
    "switch to", "focus", "bring up", "center", "centre",
    "pin", "unpin", "fullscreen", "full screen", "swap"
]

_LAYOUT_TRIGGERS = [
    "side by side", "split screen", "split view",
    "stack", "quad", "tile", "arrange"
]

_DESKTOP_PHRASES = [
    "show desktop", "hide all windows", "minimize everything",
    "minimize all", "minimize all windows", "clear desktop",
    "hide everything", "show all windows", "restore all",
    "restore all windows", "view desktop", "show my desktop",
    "clear screen", "clear all windows", "go to desktop",
    "desktop", "hide windows"
]

_NOTARGET_PHRASES = [
    "undo that", "undo last", "undo window", "put it back",
    "revert that", "undo", "whats open", "what is open",
    "what windows are open", "list windows", "show windows",
    "what's running", "whats running"
]

_SWITCH_VERBS = [
    "switch to", "bring up", "go to", "focus on", "focus",
    "show me", "pull up", "jump to", "open up"
]


def process(ctx, deps):
    clean_in = ctx.clean_in

    put_pattern = "put " in clean_in and any(
        p in clean_in for p in [
            "on the left", "on the right", "on left", "on right",
            "top left", "top right", "bottom left", "bottom right"
        ]
    )
    is_layout       = any(t in clean_in for t in _LAYOUT_TRIGGERS)
    is_desktop_cmd  = clean_in in _DESKTOP_PHRASES
    is_notarget_cmd = (clean_in in _NOTARGET_PHRASES
                       or any(p in clean_in for p in _NOTARGET_PHRASES))
    is_switch       = any(sv in clean_in for sv in _SWITCH_VERBS)
    is_move_monitor = "move" in clean_in and "monitor" in clean_in
    is_swap         = "swap" in clean_in and ("and" in clean_in or "," in clean_in)
    is_window_close = ("close this" in clean_in or "close the window" in clean_in
                       or "close active" in clean_in)
    is_transparent  = ("transparent" in clean_in or "see through" in clean_in
                       or "translucent" in clean_in)
    is_solid        = ("solid" in clean_in or "opaque" in clean_in
                       or "not transparent" in clean_in)
    is_pin          = ("pin " in clean_in
                       or ("keep" in clean_in and "on top" in clean_in)
                       or "always on top" in clean_in)
    is_unpin        = ("unpin" in clean_in or "remove from top" in clean_in
                       or "not on top" in clean_in)
    is_window_verb  = any(wv in clean_in for wv in _WINDOW_VERBS)

    is_any_window = (
        is_desktop_cmd or is_notarget_cmd or is_layout or put_pattern
        or is_window_verb or is_switch or is_move_monitor or is_swap
        or is_window_close or is_transparent or is_solid
        or is_pin or is_unpin
    )

    if not is_any_window:
        return LayerResult.pass_through()

    ctx.is_command = True
    tag_params = _build_window_tag(
        clean_in, is_desktop_cmd, is_notarget_cmd, is_layout, put_pattern,
        is_switch, is_move_monitor, is_swap, is_window_close,
        is_transparent, is_solid, is_pin, is_unpin
    )

    if not tag_params:
        return LayerResult.pass_through()

    _parts = {}
    for _p in tag_params.split():
        if "=" in _p:
            _k, _v = _p.split("=", 1)
            _parts[_k] = _v

    _action   = _parts.get("action", "")
    _target   = _parts.get("target", "").replace(",", " and ")
    _position = _parts.get("position", "")
    _mode     = _parts.get("mode", "")

    speech = _get_speech(_action, _target, _position, _mode, _parts)

    if speech:
        return LayerResult.stop(f"{speech} ###WINDOW: {tag_params}")
    return LayerResult.stop(f"###WINDOW: {tag_params}")


def _get_speech(action, target, position, mode, parts):
    """TARS-style speech for each window action."""
    speech_map = {
        "focus":         lambda: random.choice([
            f"Switching to {target}.",
            f"Bringing up {target}.",
            f"{target}, coming up."
        ]),
        "minimize":      lambda: random.choice([
            f"Minimizing {target}.",
            f"Putting {target} away.",
            f"{target}, out of sight."
        ]),
        "maximize":      lambda: random.choice([
            f"Maximizing {target}.",
            f"Full size on {target}.",
            f"{target}, going big."
        ]),
        "restore":       lambda: random.choice([
            f"Restoring {target}.",
            f"Bringing {target} back."
        ]),
        "snap":          lambda: random.choice([
            f"Snapping {target} to the {position}.",
            f"{target}, {position} side."
        ]),
        "center":        lambda: f"Centering {target}.",
        "layout":        lambda: (
            f"Putting {target} side by side." if mode == "split"
            else f"Stacking {target}." if mode == "stack"
            else f"Four corners, {target}." if mode == "quad"
            else f"Arranging {target}."
        ),
        "minimize_all":  lambda: random.choice([
            "Clearing the deck.", "Everything down.", "Desktop, clear."
        ]),
        "show_desktop":  lambda: random.choice([
            "Showing desktop.", "All clear.", "Desktop."
        ]),
        "swap":          lambda: random.choice([
            f"Swapping {target}.", f"{target}, switching places."
        ]),
        "pin":           lambda: random.choice([
            f"Pinning {target} on top.", f"{target} stays on top now."
        ]),
        "unpin":         lambda: random.choice([
            f"Unpinning {target}.", f"{target}, back to normal."
        ]),
        "fullscreen":    lambda: random.choice([
            f"Fullscreen on {target}.", f"{target}, going fullscreen."
        ]),
        "solid":         lambda: random.choice([
            f"Making {target} solid again.", f"{target}, back to full opacity."
        ]),
        "close_window":  lambda: "Closing this window.",
        "undo":          lambda: random.choice([
            "Undoing that.", "Putting it back.", "Reverting."
        ]),
        "list":          lambda: "",
    }

    if action == "transparent":
        _opacity = parts.get("opacity", "0.8")
        if _opacity == "more":
            return random.choice([
                f"Making {target} more transparent.",
                f"{target}, a bit more see-through."
            ])
        elif _opacity == "less":
            return random.choice([
                f"Making {target} less transparent.",
                f"Brightening {target} up."
            ])
        try:
            pct = int(float(_opacity) * 100)
            if pct >= 90:
                return f"Making {target} slightly transparent."
            elif pct <= 40:
                return f"Making {target} very transparent."
            return f"Setting {target} to {pct}% opacity."
        except Exception:
            return f"Making {target} transparent."

    speech_fn = speech_map.get(action)
    return speech_fn() if speech_fn else "On it."