"""
backend/routes/license_routes.py
Handles: /api/license/*, /api/plan/usage, /api/referral/*
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class LicenseActivate(BaseModel):
    key:   str
    email: Optional[str] = None


class LicenseDeactivate(BaseModel):
    key: Optional[str] = None


class TrialStart(BaseModel):
    email: str


@router.post("/api/license/activate")
def activate_license_endpoint(req: LicenseActivate):
    """Activate a license key."""
    import license as license_module
    success, message, data = license_module.activate_license(req.key, req.email)
    if success:
        return {"success": True, "message": message, "license": data}
    else:
        raise HTTPException(status_code=400, detail=message)


@router.get("/api/license/status")
def get_license_status():
    """Get current license status. Never 500s."""
    try:
        import license as license_module
        import config

        validation  = license_module.validate_license()
        if not isinstance(validation, dict):
            raise ValueError(f"validate_license returned {type(validation)}, expected dict")

        tier        = validation.get("tier", "free")
        features    = license_module.get_features(tier)
        device_id   = license_module.get_device_id() or "unknown"
        license_key = config.KEY.get("license", {}).get("key", "")
        is_trial    = config.KEY.get("license", {}).get("is_trial", False)

        return {
            "tier":              tier,
            "valid":             validation.get("valid", True),
            "expires_at":        validation.get("expires_at"),
            "days_until_expiry": validation.get("days_until_expiry"),
            "offline_mode":      validation.get("offline_mode", False),
            "offline_days":      validation.get("offline_days", 0),
            "features":          features or {},
            "license_key":       license_key,
            "is_trial":          is_trial,
            "device_id":         (device_id[:8] + "...") if len(device_id) > 8 else device_id
        }
    except Exception as e:
        import traceback
        print(f"[API] /api/license/status error: {e}")
        traceback.print_exc()
        return {
            "tier":              "free",
            "valid":             True,
            "expires_at":        None,
            "days_until_expiry": None,
            "offline_mode":      False,
            "offline_days":      0,
            "features":          {},
            "license_key":       "",
            "is_trial":          False,
            "device_id":         "unknown",
            "error_debug":       str(e)
        }


@router.post("/api/license/validate")
def validate_license_endpoint():
    """Force online validation."""
    import license as license_module
    return license_module.validate_license(online=True)


@router.post("/api/license/deactivate")
def deactivate_license_endpoint(req: LicenseDeactivate):
    """Deactivate license on current device."""
    import license as license_module
    success, message = license_module.deactivate_device(req.key)
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)


@router.get("/api/license/features")
def get_license_features():
    """Get feature flags for current tier."""
    import license as license_module
    return license_module.get_features()


@router.post("/api/license/trial")
def start_trial_endpoint(req: TrialStart):
    """Start 14-day Pro trial."""
    import license as license_module
    import telemetry
    success, message = license_module.start_trial(req.email)
    if success:
        telemetry.save_email(req.email)
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=400, detail=message)


@router.get("/api/license/pricing")
def get_pricing():
    """Get pricing information."""
    import license as license_module
    return {
        "tiers":   license_module.TIER_FEATURES,
        "pricing": license_module.PRICING
    }


@router.get("/api/plan/usage")
def get_plan_usage():
    """Get current usage vs plan limits for all features."""
    import license as license_module
    from backend.api_server import get_current_tier, check_limit
    import os

    tier     = get_current_tier()
    features = license_module.TIER_FEATURES.get(tier, license_module.TIER_FEATURES["free"])

    try:
        from memory import seven_memory
        all_facts   = seven_memory.user_facts.get()
        facts_count = len(all_facts["documents"]) if all_facts and all_facts.get("documents") else 0
    except Exception:
        facts_count = 0

    try:
        from memory import seven_memory
        all_convos  = seven_memory.conversations.get()
        convo_count = len(all_convos["documents"]) if all_convos and all_convos.get("documents") else 0
    except Exception:
        convo_count = 0

    try:
        _appdata  = os.environ.get("APPDATA", os.path.expanduser("~"))
        _know_dir = os.path.join(_appdata, "SEVEN", "seven_data", "knowledge")
        file_count = len([
            f for f in os.listdir(_know_dir)
            if os.path.isfile(os.path.join(_know_dir, f))
        ]) if os.path.exists(_know_dir) else 0
    except Exception:
        file_count = 0

    try:
        import hands.scheduler as scheduler_mod
        all_schedules  = scheduler_mod.get_all_schedules()
        schedule_count = len(all_schedules) if all_schedules else 0
    except Exception:
        schedule_count = 0

    def usage_item(current, limit):
        if limit == -1:
            return {"current": current, "limit": -1, "percent": 0, "full": False}
        percent = int((current / limit) * 100) if limit > 0 else 100
        return {"current": current, "limit": limit, "percent": percent, "full": current >= limit}

    return {
        "tier": tier,
        "features": {
            "facts":         usage_item(facts_count,    features.get("facts_limit",          7)),
            "conversations": usage_item(convo_count,    features.get("conversation_history",  7)),
            "knowledge":     usage_item(file_count,     features.get("knowledge_files",        1)),
            "schedules":     usage_item(schedule_count, features.get("schedules",              7)),
        },
        "capabilities": {
            "memory_export":       features.get("memory_export",       False),
            "voice_recognition":   features.get("voice_recognition",   False),
            "recurring_schedules": features.get("recurring_schedules", False),
        }
    }


@router.get("/api/referral/stats")
def get_referral_stats_endpoint():
    """Get referral statistics."""
    import telemetry

    email = telemetry.get_email()

    if not email:
        try:
            import server_sync
            import license as license_module
            device_id = license_module.get_device_id()
            stats     = server_sync.get_referral_stats(device_id=device_id)
            if stats:
                return stats
        except Exception:
            pass
        return {"referral_code": None, "completed_referrals": 0, "pending_referrals": 0}

    try:
        import license as license_module
        stats = license_module.get_referral_stats(email)
        if stats:
            return stats
    except Exception:
        pass

    try:
        import server_sync
        stats = server_sync.get_referral_stats(email=email)
        if stats:
            return stats
    except Exception:
        pass

    return {"referral_code": None, "completed_referrals": 0, "pending_referrals": 0}


@router.post("/api/referral/create")
def create_referral_endpoint(data: dict):
    """Create a referral code."""
    import telemetry
    import license as license_module

    email = data.get("email") or telemetry.get_email()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")

    telemetry.save_email(email)

    try:
        import server_sync
        device_id = license_module.get_device_id()
        result    = server_sync.create_referral(device_id, email)
        if result:
            return {
                "success":       True,
                "referral_code": result["referral_code"],
                "referral_link": result["referral_link"]
            }
    except Exception as e:
        print(f"[API] Server referral creation failed: {e}")

    try:
        code = license_module.create_referral_code(email)
        return {
            "success":       True,
            "referral_code": code,
            "referral_link": f"https://seven.app/ref/{code}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/referral/completed-pending")
def get_completed_pending_referrals():
    """Get referrals that just completed 7 hours."""
    import license as license_module
    import sqlite3

    license_module.init_db()
    conn = sqlite3.connect(license_module.LICENSE_DB)
    c    = conn.cursor()

    c.execute("""
        SELECT r.referred_email, r.referrer_email, r.completed_at, r.usage_hours
        FROM referrals r
        WHERE r.is_complete = 1
        AND r.completed_at > datetime('now', '-7 days')
        ORDER BY r.completed_at DESC
    """)
    completed = [
        {"referred_email": row[0], "referrer_email": row[1],
         "completed_at": row[2], "usage_hours": round(row[3], 1)}
        for row in c.fetchall()
    ]

    c.execute("""
        SELECT r.referred_email, r.referrer_email, r.usage_hours, r.created_at
        FROM referrals r
        WHERE r.is_complete = 0 AND r.usage_hours >= 5
        ORDER BY r.usage_hours DESC
    """)
    almost_complete = [
        {"referred_email": row[0], "referrer_email": row[1],
         "usage_hours": round(row[2], 1), "hours_left": round(7 - row[2], 1),
         "created_at": row[3]}
        for row in c.fetchall()
    ]

    conn.close()
    return {"completed_recently": completed, "almost_complete": almost_complete}