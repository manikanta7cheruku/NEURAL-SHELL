"""
=============================================================================
LAYER 4.5d: BATTERY FAST PATH

Catches "battery", "how much charge", "is it charging" etc.
Skips full system command parser — routes directly to ###SYS: action=battery.
=============================================================================
"""

import random
from brain_modules.layer_result import LayerResult


_BATTERY_PHRASES = [
    "battery", "how much charge", "battery level",
    "battery percentage", "is it charging", "plugged in"
]


def process(ctx, deps):
    _has_battery = any(p in ctx.clean_in for p in _BATTERY_PHRASES)
    if not _has_battery or ctx.is_command:
        return LayerResult.pass_through()

    _ack = random.choice(["Checking.", "On it.", "One moment."])
    return LayerResult.stop(f"{_ack} ###SYS: action=battery")