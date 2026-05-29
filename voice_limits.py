"""
voice_limits.py — Plan limit enforcement for voice pipeline.
Same limits as api_server.py but for main.py voice path.
Both doors now check the same rules.
"""

import os
import json

# ── Tier feature limits (must match license.py TIER_FEATURES exactly) ──
TIER_LIMITS = {
    "free": {
        "facts_limit":          7,
        "conversation_history": 7,
        "schedules":            7,
        "recurring_schedules":  False,
    },
    "pro": {
        "facts_limit":          77,
        "conversation_history": 77,
        "schedules":            17,
        "recurring_schedules":  False,
    },
    "ultimate": {
        "facts_limit":          -1,
        "conversation_history": -1,
        "schedules":            -1,
        "recurring_schedules":  True,
    }
}

# ── Verbal messages Seven speaks when limit hit ──
LIMIT_MESSAGES = {
    "facts_limit": {
        "free":     "You've reached the free plan limit of 7 facts. "
                    "Upgrade to Pro for up to 77 facts.",
        "pro":      "You've reached the Pro limit of 77 facts. "
                    "Upgrade to Ultimate for unlimited memory.",
        "ultimate": ""
    },
    "conversation_history": {
        "free":     "Your free plan memory is full at 7 conversations. "
                    "Upgrade to Pro to remember more.",
        "pro":      "Your Pro memory is full at 77 conversations. "
                    "Upgrade to Ultimate for unlimited history.",
        "ultimate": ""
    },
    "schedules": {
        "free":     "You've reached the free plan limit of 7 schedules. "
                    "Upgrade to Pro for up to 17.",
        "pro":      "You've reached the Pro limit of 17 schedules. "
                    "Upgrade to Ultimate for unlimited schedules.",
        "ultimate": ""
    },
    "recurring_schedules": {
        "free":     "Recurring schedules require Pro plan or higher. "
                    "Go to Plans in the dashboard to upgrade.",
        "pro":      "Recurring schedules require Pro plan or higher. "
                    "Go to Plans in the dashboard to upgrade.",
        "ultimate": ""
    }
}


def get_tier() -> str:
    """Read current tier from config.json. Always safe."""
    try:
        appdata     = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_path = os.path.join(appdata, "SEVEN", "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
            tier = cfg.get("license", {}).get("tier", "free")
            if tier in TIER_LIMITS:
                return tier
    except Exception:
        pass
    return "free"


def get_limit(feature: str) -> int:
    """Get numeric limit for feature on current tier. -1 = unlimited."""
    tier = get_tier()
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(feature, 0)


def get_bool_feature(feature: str) -> bool:
    """Get boolean feature flag for current tier."""
    tier = get_tier()
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(feature, False)


def check(feature: str, current_count: int) -> tuple:
    """
    Check if action is allowed.

    Returns:
        (allowed: bool, verbal_message: str)
        verbal_message is empty string if allowed.
    """
    tier  = get_tier()
    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(feature, 0)

    if limit == -1:
        return True, ""

    if current_count < limit:
        return True, ""

    msg = LIMIT_MESSAGES.get(feature, {}).get(tier, "You've reached your plan limit.")
    return False, msg


def check_bool(feature: str) -> tuple:
    """
    Check if a boolean feature is available.

    Returns:
        (allowed: bool, verbal_message: str)
    """
    tier    = get_tier()
    allowed = TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(feature, False)
    if allowed:
        return True, ""
    msg = LIMIT_MESSAGES.get(feature, {}).get(tier, "This feature requires a higher plan.")
    return False, msg