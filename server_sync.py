"""
PROJECT SEVEN - server_sync.py
Communicates with analytics server (privacy-safe)
"""

import requests
import threading

# =============================================================================
# CONFIGURATION - UPDATE THIS AFTER DEPLOYING TO RAILWAY
# =============================================================================

# To switch servers in future: change only this line
SERVER_URL = "https://seven-server-u2rp.onrender.com"

ENABLED = True
TIMEOUT = 5

# =============================================================================
# FUNCTIONS
# =============================================================================

def _post(endpoint, data):
    """POST request to server."""
    if not ENABLED:
        return None
    try:
        r = requests.post(f"{SERVER_URL}{endpoint}", json=data, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else None
    except:
        return None


def _async_post(endpoint, data):
    """Non-blocking POST."""
    threading.Thread(target=_post, args=(endpoint, data), daemon=True).start()


def register_device(device_id, email=None, name=None, country=None, referral_code=None):
    """Register or update device on server. Includes name for admin dashboard."""
    _async_post("/api/register", {
        "device_id": device_id,
        "email": email,
        "name": name,
        "country": country,
        "referral_code": referral_code
    })


def send_usage_ping(device_id, minutes_delta, email=None, total_minutes=None):
    """Send usage time to server. Sends total for server self-correction."""
    payload = {
        "device_id":     device_id,
        "minutes_delta": minutes_delta,
        "email":         email,
    }
    if total_minutes is not None:
        payload["total_minutes"] = total_minutes

    result = _post("/api/usage/ping", payload)

    if result and result.get("referral_completed"):
        print("[SERVER] Referral completed!")

    return result


def create_referral(device_id, email):
    """Get referral code."""
    return _post("/api/referral/create", {"device_id": device_id, "email": email})


def keep_alive():
    """Ping server to prevent Render free tier sleep."""
    try:
        import requests
        requests.get(f"{SERVER_URL}/ping", timeout=5)
    except Exception:
        pass


def get_or_create_referral_code(device_id, email):
    """
    Get existing referral code or create new one.
    Called on startup so user always has a code to share.
    Returns referral code string or None.
    """
    if not email:
        return None
    result = _post("/api/referral/create", {
        "device_id": device_id,
        "email":     email
    })
    if result:
        return result.get("referral_code")
    return None


def get_referral_stats(email=None, device_id=None):
    """Get referral stats."""
    try:
        r = requests.get(f"{SERVER_URL}/api/referral/stats", 
                        params={"email": email, "device_id": device_id}, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else None
    except:
        return None