"""
=============================================================================
PROJECT SEVEN - license.py (License Management System)
Version: 1.0

PURPOSE:
    Manage license tiers, activation, validation, and feature gating.
    100% offline-first with 30-day grace period.
    
TIERS:
    Free:     ₹0 (limited features)
    Pro:      ₹99/mo, ₹699/yr, ₹1299 lifetime
    Ultimate: ₹199/mo, ₹999/yr, ₹1999 lifetime
=============================================================================
"""

import os
import sqlite3
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

def _get_data_dir():
    """Always use %APPDATA%\SEVEN\data — works in dev and packaged."""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    d = os.path.join(appdata, 'SEVEN', 'data')
    os.makedirs(d, exist_ok=True)
    return d

DATA_DIR       = _get_data_dir()
LICENSE_DB     = os.path.join(DATA_DIR, "license.db")
CACHE_FILE     = os.path.join(DATA_DIR, "license_cache.json")
DEVICE_ID_FILE = os.path.join(DATA_DIR, "device_id.txt")

OFFLINE_GRACE_DAYS = 30

# Feature limits by tier
TIER_FEATURES = {
    "free": {
        "conversation_history": 7,
        "facts_limit": 7,
        "knowledge_files": 1,
        "schedules": 7,
        "web_searches_per_day": 7,
        "url_shortcuts": 3,
        "app_aliases": 3,
        "custom_commands": 1,
        "custom_paths": 1,
        "voice_recognition": False,
        "window_control": "basic",
        "memory_export": False,
        "recurring_schedules": False,
        "max_devices": 1
    },
    "pro": {
        "conversation_history": 77,
        "facts_limit": 77,
        "knowledge_files": 7,
        "schedules": 17,
        "web_searches_per_day": 77,
        "url_shortcuts": 7,
        "app_aliases": 7,
        "custom_commands": 7,
        "custom_paths": 7,
        "voice_recognition": False,  # Removed as requested
        "window_control": "advanced",
        "memory_export": False,
        "recurring_schedules": False,
        "max_devices": 1
    },
    "ultimate": {
        "conversation_history": -1,  # unlimited
        "facts_limit": -1,
        "knowledge_files": -1,
        "schedules": -1,
        "web_searches_per_day": -1,
        "url_shortcuts": -1,
        "app_aliases": -1,
        "custom_commands": -1,
        "custom_paths": -1,
        "voice_recognition": True,
        "window_control": "full",
        "memory_export": True,
        "recurring_schedules": True,
        "max_devices": 3
    }
}

# Pricing (for display/validation)
PRICING = {
    "pro": {"monthly": 99, "yearly": 699, "lifetime": 1299},
    "ultimate": {"monthly": 199, "yearly": 999, "lifetime": 1999}
}

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_db():
    """Initialize license database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Licenses table
    c.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            tier TEXT DEFAULT 'free',
            plan_type TEXT,
            device_ids TEXT,
            max_devices INTEGER DEFAULT 1,
            created_at TEXT,
            expires_at TEXT,
            is_active INTEGER DEFAULT 1,
            is_trial INTEGER DEFAULT 0
        )
    """)
    
    # Activations table
    c.execute("""
    CREATE TABLE IF NOT EXISTS activations (
        device_id TEXT PRIMARY KEY,
        license_key TEXT,
        activated_at TEXT,
        last_validated TEXT,
        usage_hours REAL DEFAULT 0,
        email TEXT,
        FOREIGN KEY (license_key) REFERENCES licenses(license_key)
    )
""")
    
    # Referrals table
    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_code TEXT,
            referrer_email TEXT,
            referred_email TEXT,
            referred_device_id TEXT,
            usage_hours REAL DEFAULT 0,
            is_complete INTEGER DEFAULT 0,
            created_at TEXT,
            completed_at TEXT
        )
    """)
    
    # Credits table
    c.execute("""
        CREATE TABLE IF NOT EXISTS credits (
            email TEXT PRIMARY KEY,
            total_credits REAL DEFAULT 0,
            referrals_count INTEGER DEFAULT 0,
            last_updated TEXT
        )
    """)
    
    conn.commit()
    conn.close()

# =============================================================================
# DEVICE ID
# =============================================================================

def get_device_id() -> str:
    """Get device ID — delegates to telemetry for consistency."""
    try:
        import telemetry as _tel
        return _tel.get_device_id()
    except Exception:
        # Fallback
        if os.path.exists(DEVICE_ID_FILE):
            with open(DEVICE_ID_FILE, "r") as f:
                return f.read().strip()
        device_id = str(uuid.uuid4())
        with open(DEVICE_ID_FILE, "w") as f:
            f.write(device_id)
        return device_id

def get_device_fingerprint() -> str:
    """Generate hardware fingerprint."""
    import platform
    import subprocess
    
    try:
        # Get CPU serial (Windows)
        if platform.system() == "Windows":
            cpu = subprocess.check_output("wmic cpu get processorid", shell=True).decode().split("\n")[1].strip()
        else:
            cpu = "unknown"
        
        # Combine with device_id
        raw = f"{cpu}_{get_device_id()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    except:
        return get_device_id()[:16]

# =============================================================================
# LICENSE KEY GENERATION
# =============================================================================

def generate_license_key(tier: str = "pro", custom: str = None) -> str:
    """
    Generate a license key.
    
    Auto format:   VII-XXXX-XXXX-XXXX
    Custom format: VII-LAUNCH-2025
                   VII-BETA-FRIEND
                   VII-VIP-MANIKANTA
                   VII-EARLYBIRD
    
    Rules for custom:
      - Must start with VII-
      - Only A-Z, 0-9, hyphens
      - Max 30 characters total
    """
    if custom:
        # Clean and format custom key
        clean = custom.upper().strip()
        # Remove VII- prefix if user already included it
        if clean.startswith("VII-"):
            return clean
        return f"VII-{clean}"
    
    # Auto generate
    segment1 = uuid.uuid4().hex[:4].upper()
    segment2 = uuid.uuid4().hex[:4].upper()
    segment3 = uuid.uuid4().hex[:4].upper()
    return f"VII-{segment1}-{segment2}-{segment3}"


def validate_key_format(key: str) -> bool:
    """
    Accept both auto-generated and custom key formats.
    Only rule: must start with VII- and be alphanumeric + hyphens.
    """
    import re
    key = key.upper().strip()
    # Must start with VII-
    if not key.startswith("VII-"):
        return False
    # Rest must be alphanumeric + hyphens, min 4 chars after VII-
    rest = key[4:]
    if len(rest) < 4:
        return False
    pattern = r'^[A-Z0-9\-]+$'
    return bool(re.match(pattern, rest))

# =============================================================================
# LICENSE ACTIVATION
# =============================================================================

SERVER_URL = "https://seven-server-u2rp.onrender.com"


def activate_license(license_key: str, email: str = None) -> Tuple[bool, str, Optional[Dict]]:
    """
    Activate a license key on this device.

    Flow:
      1. Try server validation first (works on any machine)
      2. Fall back to local license.db (developer machine only)
      3. Save tier to config.json + local cache

    Returns:
        (success, message, license_data)
    """
    if not validate_key_format(license_key):
        return False, "Invalid license key format. Must start with VII-", None

    license_key = license_key.upper().strip()
    device_id   = get_device_id()

    # ── STEP 1: Try server validation ──────────────────────────────
    try:
        import urllib.request
        import urllib.error

        payload = json.dumps({
            "license_key": license_key,
            "device_id":   device_id
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{SERVER_URL}/api/license/validate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("valid"):
            tier       = data["tier"]
            expires_at = data.get("expires_at")

            # Save locally
            _save_local_activation(license_key, tier, expires_at, device_id)
            _update_cache(tier, expires_at, license_key)

            import config
            config.update_config({
                "license": {
                    "key":          license_key,
                    "tier":         tier,
                    "verified":     True,
                    "activated_at": datetime.now().isoformat(),
                    "expires_at":   expires_at
                }
            })

            days_left = data.get("days_until_expiry")
            if days_left is None:
                expiry_msg = "Lifetime"
            else:
                expiry_msg = f"{days_left} days remaining"

            print("[LICENSE] Activated: " + tier.upper() + " (" + expiry_msg + ")")

            # Tell server to update license_tier in users table
            try:
                _sync_tier_to_server(device_id, tier, license_key)
            except Exception as _e:
                print("[LICENSE] Tier sync warning: " + str(_e))

            return True, "License activated successfully (" + tier.upper() + ")", {
                "tier":       tier,
                "expires_at": expires_at,
                "source":     "server"
            }

    except urllib.error.HTTPError as e:
        # 404 = key not found on server, 400 = expired/revoked
        body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(body)
            reason = err.get("detail", str(e))
        except Exception:
            reason = str(e)
        print(f"[LICENSE] Server rejected key: {reason}")
        # Don't fall back to local for these — key genuinely invalid
        if e.code in (400, 404):
            # Still try local as last resort (developer machine)
            pass

    except Exception as e:
        print(f"[LICENSE] Server unreachable, trying local: {e}")

    # ── STEP 2: Fall back to local license.db ──────────────────────
    init_db()

    # Use full path from config
    import config as _config
    _appdata  = os.environ.get("APPDATA", os.path.expanduser("~"))
    _data_dir = os.path.join(_appdata, "SEVEN", "data")
    _lic_db   = os.path.join(_data_dir, "license.db")

    conn = sqlite3.connect(_lic_db)
    c    = conn.cursor()

    c.execute("""
        SELECT tier, device_ids, max_devices, is_active, expires_at
        FROM licenses WHERE license_key = ?
    """, (license_key,))
    row = c.fetchone()

    if not row:
        conn.close()
        return False, "License key not found. Make sure you are connected to the internet.", None

    tier, device_ids_json, max_devices, is_active, expires_at = row

    if not is_active:
        conn.close()
        return False, "This license has been deactivated.", None

    if expires_at:
        expiry = datetime.fromisoformat(expires_at)
        if datetime.now() > expiry:
            conn.close()
            return False, "This license has expired.", None

    device_ids = json.loads(device_ids_json) if device_ids_json else []

    if device_id not in device_ids:
        if len(device_ids) >= max_devices:
            conn.close()
            return False, f"Device limit reached ({max_devices} devices).", None
        device_ids.append(device_id)
        c.execute("UPDATE licenses SET device_ids = ? WHERE license_key = ?",
                  (json.dumps(device_ids), license_key))

    c.execute("""
        INSERT OR REPLACE INTO activations
            (license_key, device_id, activated_at, last_validated)
        VALUES (?, ?, ?, ?)
    """, (license_key, device_id, datetime.now().isoformat(), datetime.now().isoformat()))

    conn.commit()
    conn.close()

    _update_cache(tier, expires_at, license_key)

    import config
    config.update_config({
        "license": {
            "key":          license_key,
            "tier":         tier,
            "verified":     True,
            "activated_at": datetime.now().isoformat(),
            "expires_at":   expires_at
        }
    })

    print("[LICENSE] Local validated: " + tier.upper())

    # Tell server to update license_tier in users table
    try:
        _sync_tier_to_server(device_id, tier, license_key)
    except Exception as _e:
        print("[LICENSE] Tier sync warning: " + str(_e))

    return True, "License activated successfully (" + tier.upper() + ")", {
        "tier":       tier,
        "expires_at": expires_at,
        "source":     "local"
    }


def _sync_tier_to_server(device_id, tier, license_key):
    """
    Update license_tier in server users table after activation.
    This makes admin dashboard show correct tier.
    """
    try:
        import urllib.request
        payload = json.dumps({
            "device_id":     device_id,
            "license_key":   license_key,
            "license_tier":  tier
        }).encode("utf-8")

        req = urllib.request.Request(
            SERVER_URL + "/api/license/sync-tier",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
            print("[LICENSE] Tier synced to server: " + tier)
            return result
    except Exception as e:
        print("[LICENSE] Tier sync failed (ok): " + str(e))
        return None


def _save_local_activation(license_key, tier, expires_at, device_id):
    """Save server-validated license to local DB for offline use."""
    try:
        _appdata  = os.environ.get("APPDATA", os.path.expanduser("~"))
        _data_dir = os.path.join(_appdata, "SEVEN", "data")
        _lic_db   = os.path.join(_data_dir, "license.db")

        os.makedirs(_data_dir, exist_ok=True)
        init_db()

        conn = sqlite3.connect(_lic_db)
        c    = conn.cursor()

        # Upsert license
        c.execute("""
            INSERT OR REPLACE INTO licenses
                (license_key, email, tier, plan_type, device_ids,
                 max_devices, created_at, expires_at, is_active, is_trial)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
        """, (license_key, "server-validated@seven.app", tier, "server",
              json.dumps([device_id]), 3,
              datetime.now().isoformat(), expires_at))

        # Upsert activation
        c.execute("""
            INSERT OR REPLACE INTO activations
                (license_key, device_id, activated_at, last_validated)
            VALUES (?, ?, ?, ?)
        """, (license_key, device_id,
              datetime.now().isoformat(), datetime.now().isoformat()))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[LICENSE] Local save warning: {e}")

# =============================================================================
# LICENSE VALIDATION
# =============================================================================

def validate_license(online: bool = True) -> Dict:
    """
    Validate current license (online or offline).
    
    Returns:
        {
            "tier": "free"|"pro"|"ultimate",
            "valid": bool,
            "expires_at": str|None,
            "days_until_expiry": int|None,
            "offline_mode": bool
        }
    """
    device_id = get_device_id()
    
    # Try online validation first
    if online:
        try:
            init_db()
            conn = sqlite3.connect(LICENSE_DB)
            c = conn.cursor()
            
            c.execute("""
                SELECT l.tier, l.expires_at, l.license_key 
                FROM activations a 
                JOIN licenses l ON a.license_key = l.license_key 
                WHERE a.device_id = ? AND l.is_active = 1
            """, (device_id,))
            
            row = c.fetchone()
            
            if row:
                tier, expires_at, license_key = row
                
                # Check expiry
                if expires_at:
                    expiry = datetime.fromisoformat(expires_at)
                    if datetime.now() > expiry:
                        conn.close()
                        return {"tier": "free", "valid": False, "expires_at": expires_at, 
                                "days_until_expiry": 0, "offline_mode": False}
                    
                    days_left = (expiry - datetime.now()).days
                else:
                    days_left = None
                
                # Update last validation
                c.execute("UPDATE activations SET last_validated = ? WHERE device_id = ?",
                          (datetime.now().isoformat(), device_id))
                conn.commit()
                conn.close()
                
                # Update cache
                _update_cache(tier, expires_at, license_key)
                
                return {
                    "tier": tier,
                    "valid": True,
                    "expires_at": expires_at,
                    "days_until_expiry": days_left,
                    "offline_mode": False
                }
            
            conn.close()
        except Exception as e:
            print(f"[LICENSE] Online validation failed: {e}")
    
    # Fallback to offline cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            
            last_validated = datetime.fromisoformat(cache["last_validated"])
            days_offline = (datetime.now() - last_validated).days
            
            if days_offline < OFFLINE_GRACE_DAYS:
                # Still within grace period
                expires_at = cache.get("expires_at")
                if expires_at:
                    expiry = datetime.fromisoformat(expires_at)
                    if datetime.now() > expiry:
                        return {"tier": "free", "valid": False, "expires_at": expires_at,
                                "days_until_expiry": 0, "offline_mode": True}
                    days_left = (expiry - datetime.now()).days
                else:
                    days_left = None
                
                return {
                    "tier": cache["tier"],
                    "valid": True,
                    "expires_at": expires_at,
                    "days_until_expiry": days_left,
                    "offline_mode": True,
                    "offline_days": days_offline
                }
            else:
                # Grace period expired — downgrade to free
                return {"tier": "free", "valid": False, "offline_mode": True,
                        "offline_days": days_offline}
        except:
            pass
    
    # No license found — check config.json as fallback
    # Also check if a lower tier key is still valid (Pro after Ultimate expires)
    try:
        import config as _cfg
        cfg_tier    = _cfg.KEY.get("license", {}).get("tier", "free")
        cfg_key     = _cfg.KEY.get("license", {}).get("key", "")
        cfg_exp     = _cfg.KEY.get("license", {}).get("expires_at", None)
        cfg_ver     = _cfg.KEY.get("license", {}).get("verified", False)

        if cfg_tier != "free" and cfg_ver and cfg_key:
            # Check if expired
            if cfg_exp:
                try:
                    expiry = datetime.fromisoformat(cfg_exp)
                    if datetime.now() > expiry:
                        # This plan expired — check if there's another active key
                        # Look in license.db for any other active activation
                        try:
                            _appdata  = os.environ.get("APPDATA", os.path.expanduser("~"))
                            _db       = os.path.join(_appdata, "SEVEN", "data", "license.db")
                            _conn     = sqlite3.connect(_db)
                            _c        = _conn.cursor()
                            _c.execute("""
                                SELECT l.tier, l.expires_at, l.license_key
                                FROM activations a
                                JOIN licenses l ON a.license_key = l.license_key
                                WHERE a.device_id = ? AND l.is_active = 1
                                AND (l.expires_at IS NULL OR l.expires_at > ?)
                                ORDER BY CASE l.tier
                                    WHEN 'ultimate' THEN 1
                                    WHEN 'pro' THEN 2
                                    ELSE 3 END ASC
                                LIMIT 1
                            """, (device_id, datetime.now().isoformat()))
                            fallback = _c.fetchone()
                            _conn.close()
                            if fallback:
                                fb_tier, fb_exp, fb_key = fallback
                                days = (datetime.fromisoformat(fb_exp) - datetime.now()).days if fb_exp else None
                                _update_cache(fb_tier, fb_exp, fb_key)
                                return {
                                    "tier": fb_tier,
                                    "valid": True,
                                    "expires_at": fb_exp,
                                    "days_until_expiry": days,
                                    "offline_mode": False
                                }
                        except Exception:
                            pass
                        # No fallback found — return free
                        return {"tier": "free", "valid": False,
                                "expires_at": cfg_exp, "days_until_expiry": 0,
                                "offline_mode": False}
                except Exception:
                    pass

            days_left = None
            if cfg_exp:
                try:
                    expiry = datetime.fromisoformat(cfg_exp)
                    if datetime.now() > expiry:
                        return {"tier": "free", "valid": False,
                                "expires_at": cfg_exp, "days_until_expiry": 0,
                                "offline_mode": False}
                    days_left = (expiry - datetime.now()).days
                except Exception:
                    pass

            _update_cache(cfg_tier, cfg_exp, cfg_key)
            return {
                "tier":              cfg_tier,
                "valid":             True,
                "expires_at":        cfg_exp,
                "days_until_expiry": days_left,
                "offline_mode":      False
            }
    except Exception as _e:
        print("[LICENSE] Config fallback error: " + str(_e))

    return {"tier": "free", "valid": True, "expires_at": None,
            "days_until_expiry": None, "offline_mode": False}

def _update_cache(tier: str, expires_at: Optional[str], license_key: str):
    """Update offline cache."""
    cache = {
        "tier": tier,
        "last_validated": datetime.now().isoformat(),
        "expires_at": expires_at,
        "license_key": license_key,
        "features": TIER_FEATURES[tier]
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

# =============================================================================
# LICENSE DEACTIVATION
# =============================================================================

def deactivate_device(license_key: str = None) -> Tuple[bool, str]:
    """
    Deactivate license on current device.
    If license_key is None, deactivate whatever is active.
    """
    device_id = get_device_id()
    
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    if license_key:
        # Specific license
        c.execute("SELECT device_ids FROM licenses WHERE license_key = ?", (license_key,))
        row = c.fetchone()
        if not row:
            conn.close()
            return False, "License not found"
        
        device_ids = json.loads(row[0]) if row[0] else []
        if device_id not in device_ids:
            conn.close()
            return False, "Device not activated on this license"
        
        device_ids.remove(device_id)
        c.execute("UPDATE licenses SET device_ids = ? WHERE license_key = ?",
                  (json.dumps(device_ids), license_key))
        
        c.execute("DELETE FROM activations WHERE license_key = ? AND device_id = ?",
                  (license_key, device_id))
    else:
        # Any license on this device
        c.execute("SELECT license_key FROM activations WHERE device_id = ?", (device_id,))
        rows = c.fetchall()
        
        for (lic_key,) in rows:
            c.execute("SELECT device_ids FROM licenses WHERE license_key = ?", (lic_key,))
            row = c.fetchone()
            if row:
                device_ids = json.loads(row[0]) if row[0] else []
                if device_id in device_ids:
                    device_ids.remove(device_id)
                    c.execute("UPDATE licenses SET device_ids = ? WHERE license_key = ?",
                              (json.dumps(device_ids), lic_key))
        
        c.execute("DELETE FROM activations WHERE device_id = ?", (device_id,))
    
    conn.commit()
    conn.close()
    
    # Clear cache
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    
    # Update config
    import config
    config.update_config({
        "license": {
            "key": "",
            "tier": "free",
            "verified": False
        }
    })
    
    return True, "Device deactivated successfully"

# =============================================================================
# FEATURE GATING
# =============================================================================

def get_features(tier: str = None) -> Dict:
    """Get feature limits for a tier."""
    if tier is None:
        validation = validate_license()
        tier = validation["tier"]
    
    return TIER_FEATURES.get(tier, TIER_FEATURES["free"])

def check_feature(feature: str, current_value: int = 0) -> Tuple[bool, int]:
    """
    Check if feature is available and get limit.
    
    Returns:
        (allowed, limit)
        limit = -1 means unlimited
    """
    features = get_features()
    limit = features.get(feature, 0)
    
    if limit == -1:
        return True, -1
    
    return current_value < limit, limit

# =============================================================================
# TRIAL SYSTEM
# =============================================================================

def start_trial(email: str) -> Tuple[bool, str]:
    """Start a 14-day Pro trial."""
    device_id = get_device_id()
    
    # Check if already has active license
    validation = validate_license()
    if validation["tier"] != "free":
        return False, "Already have an active license"
    
    # Generate trial key
    trial_key = generate_license_key("pro")
    
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Check if email already used trial
    c.execute("SELECT COUNT(*) FROM licenses WHERE email = ? AND is_trial = 1", (email,))
    if c.fetchone()[0] > 0:
        conn.close()
        return False, "Trial already used for this email"
    
    expires_at = (datetime.now() + timedelta(days=14)).isoformat()
    
    # Create trial license
    c.execute("""
        INSERT INTO licenses (license_key, email, tier, plan_type, device_ids, max_devices, 
                              created_at, expires_at, is_active, is_trial)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (trial_key, email, "pro", "trial", json.dumps([device_id]), 1,
          datetime.now().isoformat(), expires_at, 1, 1))
    
    # Create activation
    c.execute("INSERT INTO activations (license_key, device_id, activated_at, last_validated) VALUES (?, ?, ?, ?)",
              (trial_key, device_id, datetime.now().isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    # Update cache
    _update_cache("pro", expires_at, trial_key)
    
    # Update config
    import config
    config.update_config({
        "license": {
            "key": trial_key,
            "tier": "pro",
            "verified": True,
            "is_trial": True,
            "activated_at": datetime.now().isoformat()
        }
    })
    
    return True, f"14-day Pro trial activated (expires {expires_at[:10]})"

# =============================================================================
# REFERRAL SYSTEM
# =============================================================================

def generate_referral_code(email: str) -> str:
    """Generate referral code from email."""
    hash_val = hashlib.md5(email.encode()).hexdigest()[:4].upper()
    return f"SEVEN-{hash_val}"

def track_referral_usage(device_id: str, hours: float):
    """
    Track usage hours for ALL users (not just referrals).
    - Updates activation record
    - Creates record if doesn't exist
    - Checks referral completion
    """
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Check if activation record exists
    c.execute("SELECT usage_hours FROM activations WHERE device_id = ?", (device_id,))
    row = c.fetchone()
    
    if row:
        # Update existing
        new_total = row[0] + hours
        c.execute("UPDATE activations SET usage_hours = ?, last_validated = ? WHERE device_id = ?",
                  (new_total, datetime.now().isoformat(), device_id))
    else:
        # Create new activation record for tracking
        c.execute("""
            INSERT INTO activations (license_key, device_id, activated_at, last_validated, usage_hours)
            VALUES (?, ?, ?, ?, ?)
        """, ("FREE_USER", device_id, datetime.now().isoformat(), datetime.now().isoformat(), hours))
    
    # Check if this user was referred
    c.execute("""
        SELECT id, referrer_email, referred_email, usage_hours, is_complete 
        FROM referrals 
        WHERE referred_device_id = ? AND is_complete = 0
    """, (device_id,))
    
    ref_row = c.fetchone()
    if ref_row:
        ref_id, referrer_email, referred_email, current_hours, is_complete = ref_row
        new_hours = current_hours + hours
        
        c.execute("UPDATE referrals SET usage_hours = ? WHERE id = ?", (new_hours, ref_id))
        
        # Check if reached 7 hours
        if new_hours >= 7 and not is_complete:
            c.execute("UPDATE referrals SET is_complete = 1, completed_at = ? WHERE id = ?",
                      (datetime.now().isoformat(), ref_id))
            
            # Update referrer's count
            c.execute("SELECT referrals_count FROM credits WHERE email = ?", (referrer_email,))
            credit_row = c.fetchone()
            
            if credit_row:
                c.execute("UPDATE credits SET referrals_count = referrals_count + 1, last_updated = ? WHERE email = ?",
                          (datetime.now().isoformat(), referrer_email))
            else:
                c.execute("INSERT INTO credits (email, total_credits, referrals_count, last_updated) VALUES (?, ?, ?, ?)",
                          (referrer_email, 0, 1, datetime.now().isoformat()))
            
            print(f"[REFERRAL] ✅ Completed! {referred_email} used 7 hours")
            print(f"[REFERRAL] → Referrer {referrer_email} gets Ultimate 1 month")
            print(f"[REFERRAL] → Referred {referred_email} gets Pro 1 month")
    
    conn.commit()
    conn.close()

def get_referral_stats(email: str) -> Dict:
    """Get referral statistics for user."""
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Get credits
    c.execute("SELECT total_credits, referrals_count FROM credits WHERE email = ?", (email,))
    credit_row = c.fetchone()
    
    if credit_row:
        total_credits, referrals_count = credit_row
    else:
        total_credits, referrals_count = 0, 0
    
    # Get pending referrals with time details
    c.execute("""
        SELECT referred_email, usage_hours, created_at
        FROM referrals 
        WHERE referrer_email = ? AND is_complete = 0
        ORDER BY created_at DESC
    """, (email,))
    
    pending = []
    for row in c.fetchall():
        ref_email, hours, created = row
        
        # Format time remaining
        hours_left = max(0, 7 - hours)
        
        # Format usage time
        if hours < 1:
            usage_display = f"{int(hours * 60)} min"
        elif hours < 24:
            usage_display = f"{int(hours)} hr"
        else:
            days = int(hours / 24)
            usage_display = f"{days} days"
        
        pending.append({
            "email": ref_email,
            "usage_hours": round(hours, 1),
            "usage_display": usage_display,
            "hours_left": round(hours_left, 1),
            "progress_percent": min(100, int((hours / 7) * 100)),
            "created_at": created[:10]
        })
    
    # Get completed referrals (no time shown for privacy)
    c.execute("""
        SELECT referred_email, completed_at
        FROM referrals 
        WHERE referrer_email = ? AND is_complete = 1
        ORDER BY completed_at DESC
    """, (email,))
    
    completed = []
    for row in c.fetchall():
        ref_email, completed_date = row
        completed.append({
            "email": ref_email,
            "completed_at": completed_date[:10]
        })
    
    conn.close()
    
    # Calculate next milestone
    next_milestone = None
    milestone_reward = None
    
    if referrals_count < 5:
        next_milestone = 5
        milestone_reward = "₹100 bonus"
    elif referrals_count < 10:
        next_milestone = 10
        milestone_reward = "₹200 bonus"
    elif referrals_count < 25:
        next_milestone = 25
        milestone_reward = "₹500 bonus + Legend badge"
    
    return {
        "referral_code": generate_referral_code(email),
        "total_credits": total_credits,
        "completed_referrals": referrals_count,
        "pending_referrals": len(pending),
        "next_milestone": next_milestone,
        "milestone_reward": milestone_reward,
        "pending_details": pending,
        "completed_details": completed
    }

def auto_register_referral_from_installer(referred_email: str, installer_code: str = None):
    """
    Auto-register referral when user installs Seven.
    Called during first launch if installer has referral code embedded.
    
    Args:
        referred_email: New user's email
        installer_code: Referrer's code (from installer filename or registry)
    
    Returns:
        (success, message)
    """
    if not installer_code:
        return False, "No referral code"
    
    device_id = get_device_id()
    
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Check if already referred
    c.execute("SELECT COUNT(*) FROM referrals WHERE referred_device_id = ?", (device_id,))
    if c.fetchone()[0] > 0:
        conn.close()
        return False, "Already used a referral"
    
    # Find referrer by code
    # Referral code format: SEVEN-ABCD (last 4 chars of email hash)
    code_suffix = installer_code.split('-')[-1]
    
    c.execute("SELECT email FROM licenses WHERE license_key LIKE ? LIMIT 1", (f"%{code_suffix}%",))
    row = c.fetchone()
    
    if not row:
        # Try to find in credits table
        c.execute("SELECT email FROM credits LIMIT 1")  # TODO: Better matching
        row = c.fetchone()
    
    if not row:
        conn.close()
        return False, "Invalid referral code"
    
    referrer_email = row[0]
    
    # Create referral record
    c.execute("""
        INSERT INTO referrals (referrer_code, referrer_email, referred_email, referred_device_id, created_at, usage_hours)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (installer_code, referrer_email, referred_email, device_id, datetime.now().isoformat(), 0))
    
    conn.commit()
    conn.close()
    
    return True, f"Referral registered! {referrer_email} will get ₹100 credit after you use Seven for 77 hours"

def register_referral(referral_code: str, referred_email: str, referred_device_id: str) -> Tuple[bool, str]:
    """Register a new referral."""
    if not referral_code.startswith("SEVEN-"):
        return False, "Invalid referral code format"
    
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Find referrer by code
    c.execute("SELECT email FROM licenses WHERE license_key LIKE ? LIMIT 1", (f"%{referral_code[-4:]}%",))
    row = c.fetchone()
    
    if not row:
        # Try to find by credits table (referrer might not have license yet)
        # For now, return error
        conn.close()
        return False, "Referral code not found"
    
    referrer_email = row[0]
    
    # Check if already referred
    c.execute("SELECT COUNT(*) FROM referrals WHERE referred_device_id = ?", (referred_device_id,))
    if c.fetchone()[0] > 0:
        conn.close()
        return False, "Device already used a referral code"
    
    # Create referral record
    c.execute("""
        INSERT INTO referrals (referrer_code, referrer_email, referred_email, referred_device_id, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (referral_code, referrer_email, referred_email, referred_device_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return True, f"Referral registered! {referrer_email} will get ₹100 credit after you use Seven for 77 hours"

# =============================================================================
# ADMIN FUNCTIONS (For generating licenses)
# =============================================================================

def create_license(email: str, tier: str, plan_type: str,
                   custom_key: str = None) -> str:
    """
    Create a new license (admin function).
    
    Args:
        email:      User email
        tier:       "pro" or "ultimate"
        plan_type:  "monthly", "yearly", or "lifetime"
        custom_key: Optional custom key like "LAUNCH-2025"
                    Will become "VII-LAUNCH-2025"
    
    Returns:
        license_key
    """
    license_key = generate_license_key(tier, custom=custom_key)
    
    # Calculate expiry
    if plan_type == "monthly":
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    elif plan_type == "yearly":
        expires_at = (datetime.now() + timedelta(days=365)).isoformat()
    else:  # lifetime
        expires_at = None
    
    max_devices = TIER_FEATURES[tier]["max_devices"]
    
    init_db()
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO licenses (license_key, email, tier, plan_type, device_ids, max_devices,
                              created_at, expires_at, is_active, is_trial)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (license_key, email, tier, plan_type, "[]", max_devices,
          datetime.now().isoformat(), expires_at, 1, 0))
    
    conn.commit()
    conn.close()
    
    return license_key

# =============================================================================
# INITIALIZATION
# =============================================================================

# Initialize database on import
init_db()

# Validate current license on startup
current_status = validate_license()
print(f"[LICENSE] Current tier: {current_status['tier'].upper()}")
if current_status.get("offline_mode"):
    print(f"[LICENSE] Offline mode: {current_status.get('offline_days', 0)} days")