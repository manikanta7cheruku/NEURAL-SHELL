"""
seven_overlay/animations.py
Physics-based animation engine.

Easing functions inspired by Apple's Core Animation.
All animations feel natural — no linear movements.

Spring physics for that "pulled by a string" feel
when notification goes back up.
"""

import math


def ease_out_expo(t):
    """
    Exponential ease-out. Fast start, smooth deceleration.
    Used for: notification sliding INTO view.
    Feels like something being placed gently.
    """
    if t >= 1.0:
        return 1.0
    return 1.0 - math.pow(2, -10 * t)


def ease_in_back(t):
    """
    Ease-in with slight overshoot.
    Used for: notification sliding OUT of view.
    Feels like being pulled backward by a rubber band.
    The "black hole pull" effect.
    """
    c1 = 1.70158
    c3 = c1 + 1
    return c3 * t * t * t - c1 * t * t


def ease_out_back(t):
    """
    Ease-out with slight overshoot.
    Used for: elements popping into place.
    Slight bounce at the end.
    """
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * math.pow(t - 1, 3) + c1 * math.pow(t - 1, 2)


def ease_in_expo(t):
    """
    Exponential ease-in. Slow start, fast end.
    Used for: notification being sucked away.
    Accelerates as it disappears — feels like gravity pulling it.
    """
    if t <= 0:
        return 0
    return math.pow(2, 10 * (t - 1))


def spring(t, damping=0.6, frequency=3.5):
    """
    Damped spring animation.
    Used for: subtle bounce after notification lands.
    Apple uses this for sheet presentations.
    """
    if t >= 1.0:
        return 1.0
    decay = math.exp(-damping * frequency * t)
    oscillation = math.cos(frequency * math.sqrt(1 - damping * damping) * t)
    return 1.0 - decay * oscillation


def interpolate(start, end, progress, easing_fn):
    """Interpolate between start and end values using an easing function."""
    eased = easing_fn(max(0, min(1, progress)))
    return start + (end - start) * eased