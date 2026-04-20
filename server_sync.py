"""
PROJECT SEVEN - server_sync.py
Communicates with analytics server (privacy-safe)
"""

import requests
import threading

# =============================================================================
# CONFIGURATION - UPDATE THIS AFTER DEPLOYING TO RAILWAY
# =============================================================================

SERVER_URL = "https://vii-server-production.up.railway.app"  # Change to Railway URL after deployment
# SERVER_URL = "https://your-app.railway.app"  # Uncomment after deployment

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


def send_usage_ping(device_id, hours_delta, email=None):
    """Send usage time to server."""
    result = _post("/api/usage/ping", {
        "device_id": device_id,
        "hours_delta": hours_delta,
        "email": email
    })
    
    if result and result.get("referral_completed"):
        print("[SERVER] 🎉 Referral completed! Check admin dashboard.")
    
    return result


def create_referral(device_id, email):
    """Get referral code."""
    return _post("/api/referral/create", {"device_id": device_id, "email": email})


def get_referral_stats(email=None, device_id=None):
    """Get referral stats."""
    try:
        r = requests.get(f"{SERVER_URL}/api/referral/stats", 
                        params={"email": email, "device_id": device_id}, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else None
    except:
        return None