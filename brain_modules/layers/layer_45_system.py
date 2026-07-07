"""
=============================================================================
LAYER 4.5e: SYSTEM COMMAND DETECTION

Catches system control commands:
    volume, mute, brightness, wifi, bluetooth, media,
    dark mode, night light, DND, airplane mode.

Handles context pronouns: "make it louder" (uses last domain).

Emits ###SYS: tag with TARS-style speech response.

Uses existing brain_modules/command_router.py _build_system_tag() and
last-domain tracker.
=============================================================================
"""

import re
import random
from brain_modules.layer_result import LayerResult
from brain_modules.command_router import (
    _build_system_tag,
    get_last_system_domain,
    set_last_system_domain,
)


SYSTEM_TRIGGER_WORDS = [
    "volume", "mute", "unmute", "louder", "quieter", "softer",
    "brightness", "brighter", "dimmer", "dim", "battery", "charging",
    "plugged", "wifi", "bluetooth", "play", "pause", "skip",
    "next track", "next song", "previous track", "previous song",
    "stop music", "stop playing", "resume music", "dark mode",
    "light mode", "dark theme", "light theme", "night light",
    "blue light", "night mode", "do not disturb", "dnd",
    "focus assist", "airplane mode", "flight mode",
]

_POLITENESS_PREFIXES = [
    "can you ", "could you ", "please ", "would you ",
    "will you ", "can you please ", "could you please ",
]


def process(ctx, deps):
    clean_in = ctx.clean_in

    _has_sys = any(t in clean_in for t in SYSTEM_TRIGGER_WORDS)

    _has_context_ref = (
        get_last_system_domain() is not None
        and (
            (any(w in clean_in for w in ["it", "that", "this"])
             and bool(re.search(r'\d+', clean_in)))
            or clean_in in ["more", "less", "higher", "lower",
                            "increase", "decrease"]
        )
    )

    # Strip polite prefixes and re-check
    _is_app_cmd_only = ctx.first_word in ["open", "close", "start", "kill", "launch"]
    _clean_for_sys = clean_in
    for _pfx in _POLITENESS_PREFIXES:
        if _clean_for_sys.startswith(_pfx):
            _clean_for_sys = _clean_for_sys[len(_pfx):]
            break
    _has_sys_clean = any(t in _clean_for_sys for t in SYSTEM_TRIGGER_WORDS)

    _should_handle = (
        (_has_sys and not _is_app_cmd_only)
        or _has_context_ref
        or (_has_sys_clean and not _is_app_cmd_only)
    )

    if not _should_handle:
        return LayerResult.pass_through()

    sys_tag = _build_system_tag(clean_in)
    if not sys_tag:
        return LayerResult.pass_through()

    ctx.is_command = True

    # Track domain for pronoun resolution
    if "volume" in sys_tag:
        set_last_system_domain("volume")
    elif "brightness" in sys_tag:
        set_last_system_domain("brightness")

    # Parse tag for context-aware speech
    _parts = {}
    for _p in sys_tag.split():
        if "=" in _p:
            _k, _v = _p.split("=", 1)
            _parts[_k] = _v
    _action = _parts.get("action", "")
    _value  = _parts.get("value", "")

    speech_map = _speech_map(_value)
    speech_fn  = speech_map.get(_action)
    speech     = speech_fn() if speech_fn else "On it."

    if speech:
        return LayerResult.stop(f"{speech} ###SYS: {sys_tag}")
    return LayerResult.stop(f"###SYS: {sys_tag}")


def _speech_map(value):
    """TARS-style speech for each system action."""
    return {
        "volume_up":         lambda: random.choice(["Turning it up.", "Louder.", "Volume up."]),
        "volume_down":       lambda: random.choice(["Turning it down.", "Quieter.", "Volume down."]),
        "volume_set":        lambda: f"{value}%.",
        "volume_mute":       lambda: random.choice(["Muted.", "Going silent.", "Sound off."]),
        "volume_unmute":     lambda: random.choice(["Unmuted.", "Sound on.", "You are live."]),
        "volume_get":        lambda: "",
        "brightness_up":     lambda: random.choice(["Brightening up.", "More brightness.", "Screen brighter."]),
        "brightness_down":   lambda: random.choice(["Dimming.", "Less brightness.", "Screen dimmer."]),
        "brightness_set":    lambda: f"Brightness to {value}%.",
        "brightness_get":    lambda: "",
        "battery":           lambda: "",
        "wifi_on":           lambda: "Enabling WiFi.",
        "wifi_off":          lambda: "Disabling WiFi.",
        "wifi_status":       lambda: "",
        "bluetooth_on":      lambda: "Enabling Bluetooth.",
        "bluetooth_off":     lambda: "Disabling Bluetooth.",
        "bluetooth_status":  lambda: "",
        "media_play_pause":  lambda: random.choice(["Toggled.", "Done.", ""]),
        "media_next":        lambda: random.choice(["Next track.", "Skipping.", "Next."]),
        "media_prev":        lambda: random.choice(["Previous track.", "Going back.", "Previous."]),
        "media_stop":        lambda: "Stopping playback.",
        "dark_mode_on":      lambda: random.choice(["Going dark.", "Dark mode.", "Switching to dark."]),
        "dark_mode_off":     lambda: random.choice(["Going light.", "Light mode.", "Switching to light."]),
        "night_light_on":    lambda: random.choice(["Night light on.", "Easy on the eyes.", "Warming the screen."]),
        "night_light_off":   lambda: "Night light off.",
        "dnd_on":            lambda: random.choice(["Do not disturb.", "Going quiet.", "Notifications silenced."]),
        "dnd_off":           lambda: "Notifications back on.",
        "airplane_on":       lambda: random.choice(["Airplane mode on.", "Going offline.", "All radios off."]),
        "airplane_off":      lambda: random.choice(["Airplane mode off.", "Back online.", "Radios on."]),
    }