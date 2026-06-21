"""
backend/routes/usage.py
Handles: /api/usage/stats, /api/usage/history, /api/email/*
"""

from fastapi import APIRouter, HTTPException
import os
import sqlite3
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/api/usage/stats")
def get_usage_stats():
    """Get current user's total usage time."""
    try:
        import telemetry as tel
        device_id = tel.get_device_id()
        email     = tel.get_email()
        tel_db    = tel.TELEMETRY_DB
    except Exception as e:
        print(f"[API] Telemetry import error: {e}")
        return {
            "total_hours": 0, "total_minutes": 0,
            "display": "0 min", "email": None,
            "device_id": None, "last_seen": None
        }

    total_hours = 0
    last_seen   = None

    if os.path.exists(tel_db):
        try:
            conn = sqlite3.connect(tel_db)
            c    = conn.cursor()
            c.execute(
                "SELECT active_hours, last_seen, email FROM stats WHERE device_id = ?",
                (device_id,)
            )
            row = c.fetchone()
            if not row:
                c.execute(
                    "SELECT active_hours, last_seen, email FROM stats ORDER BY last_seen DESC LIMIT 1"
                )
                row = c.fetchone()
            if row:
                total_hours = row[0] or 0
                last_seen   = row[1]
                if not email and row[2]:
                    email = row[2]
            conn.close()
        except Exception as e:
            print(f"[API] telemetry.db read error: {e}")

    try:
        import telemetry as tel
        total_hours += tel.get_active_hours()
    except Exception:
        pass

    total_minutes = int(total_hours * 60)
    if total_minutes < 1:
        time_str = "0 min"
    elif total_minutes < 60:
        time_str = f"{total_minutes} min"
    else:
        hrs  = total_minutes // 60
        mins = total_minutes % 60
        time_str = f"{hrs} hr {mins} min" if mins else f"{hrs} hr"

    return {
        "total_hours":   round(total_hours, 4),
        "total_minutes": total_minutes,
        "display":       time_str,
        "email":         email,
        "device_id":     device_id,
        "last_seen":     last_seen
    }


@router.get("/api/usage/history")
def get_usage_history():
    """Get actual daily usage for last 7 days."""
    try:
        import telemetry as tel
        device_id = tel.get_device_id()
        tel_db    = tel.TELEMETRY_DB
    except Exception:
        device_id = None
        tel_db    = None

    history = []
    for i in range(6, -1, -1):
        date = datetime.now() - timedelta(days=i)
        history.append({
            "date":    date.strftime("%Y-%m-%d"),
            "day":     date.strftime("%a"),
            "hours":   0.0,
            "minutes": 0
        })

    if tel_db and os.path.exists(tel_db) and device_id:
        try:
            conn           = sqlite3.connect(tel_db)
            c              = conn.cursor()
            seven_days_ago = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
            c.execute("""
                SELECT date, hours FROM daily_usage
                WHERE device_id = ? AND date >= ?
                ORDER BY date ASC
            """, (device_id, seven_days_ago))
            actual = {row[0]: row[1] for row in c.fetchall()}
            conn.close()
            for day in history:
                if day["date"] in actual:
                    day["hours"]   = round(actual[day["date"]], 3)
                    day["minutes"] = int(actual[day["date"]] * 60)
        except Exception as e:
            print(f"[API] Usage history error: {e}")

    return {
        "history":     history,
        "total_hours": round(sum(d["hours"] for d in history), 3)
    }


@router.post("/api/email/save")
def save_user_email(data: dict):
    """Save user email for updates."""
    import telemetry
    email = data.get("email", "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    telemetry.save_email(email)
    return {"success": True, "email": email}


@router.get("/api/email/check")
def check_email_saved():
    """Check if user has saved email."""
    import telemetry
    email = telemetry.get_email()
    return {"saved": email is not None, "email": email}