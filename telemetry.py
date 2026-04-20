"""
=============================================================================
PROJECT SEVEN - telemetry.py (Usage Time Tracking)
Version: 1.3 - With server sync
=============================================================================
"""

import os
import uuid
import time
import sqlite3
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = "data"
DEVICE_ID_FILE = os.path.join(DATA_DIR, "device_id.txt")
EMAIL_FILE = os.path.join(DATA_DIR, "email.txt")
TELEMETRY_DB = os.path.join(DATA_DIR, "telemetry.db")
LICENSE_DB = os.path.join(DATA_DIR, "license.db")

PING_INTERVAL = 3600  # Background ping every hour

# Session tracking
_session = {
    "start_time": None,
    "last_activity": None,
    "accumulated_seconds": 0,
    "last_save_time": None
}

SESSION_TIMEOUT = 600  # 10 minutes idle = session ends
SAVE_INTERVAL = 30     # Save every 30 seconds (for testing; use 300 for production)

# =============================================================================
# DEVICE ID MANAGEMENT
# =============================================================================

def get_device_id():
    """Get or create unique device ID."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    if os.path.exists(DEVICE_ID_FILE):
        with open(DEVICE_ID_FILE, "r") as f:
            return f.read().strip()
    else:
        device_id = str(uuid.uuid4())
        with open(DEVICE_ID_FILE, "w") as f:
            f.write(device_id)
        return device_id

# =============================================================================
# EMAIL MANAGEMENT
# =============================================================================

def save_email(email):
    """Save user email."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    email = email.strip().lower()
    
    with open(EMAIL_FILE, "w") as f:
        f.write(email)
    
    # Update databases with email
    device_id = get_device_id()
    
    # Update telemetry.db
    try:
        init_db()
        conn = sqlite3.connect(TELEMETRY_DB)
        c = conn.cursor()
        c.execute("UPDATE stats SET email = ? WHERE device_id = ?", (email, device_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TELEMETRY] Warning: Could not update telemetry.db email: {e}")
    
    # Update license.db
    try:
        if os.path.exists(LICENSE_DB):
            conn = sqlite3.connect(LICENSE_DB)
            c = conn.cursor()
            
            # Try to add email column if it doesn't exist
            try:
                c.execute("ALTER TABLE activations ADD COLUMN email TEXT")
            except:
                pass
            
            c.execute("UPDATE activations SET email = ? WHERE device_id = ?", (email, device_id))
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"[TELEMETRY] Warning: Could not update license.db email: {e}")
    
    print(f"[TELEMETRY] ✓ Email saved: {email}")


def get_email():
    """Get saved email or None."""
    if os.path.exists(EMAIL_FILE):
        with open(EMAIL_FILE, "r") as f:
            email = f.read().strip()
            return email if email else None
    return None

# =============================================================================
# COUNTRY DETECTION
# =============================================================================

def get_country_from_ip():
    """Detect country from IP address."""
    try:
        import requests
        response = requests.get("https://ipapi.co/json/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("country_name", "Unknown")
    except:
        pass
    return "Unknown"

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_db():
    """Initialize telemetry database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    # Main stats table
    c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            device_id TEXT PRIMARY KEY,
            country TEXT,
            email TEXT,
            install_date TEXT,
            last_seen TEXT,
            active_hours REAL DEFAULT 0,
            app_version TEXT,
            license_tier TEXT DEFAULT 'free'
        )
    """)
    
    # Daily usage table (NEW - tracks per day)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            date TEXT,
            hours REAL DEFAULT 0,
            UNIQUE(device_id, date)
        )
    """)
    
    conn.commit()
    conn.close()


def init_license_db():
    """Ensure license.db has proper schema."""
    if not os.path.exists(LICENSE_DB):
        return
    
    conn = sqlite3.connect(LICENSE_DB)
    c = conn.cursor()
    
    # Check if activations table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activations'")
    if c.fetchone():
        # Try to add email column
        try:
            c.execute("ALTER TABLE activations ADD COLUMN email TEXT")
            conn.commit()
        except:
            pass
    
    conn.close()

# =============================================================================
# USAGE TIME TRACKING (CORE LOGIC)
# =============================================================================

def log_activity():
    """
    Call this whenever user does something.
    Tracks time between activities and saves periodically.
    """
    now = time.time()
    
    # First activity ever
    if _session["last_activity"] is None:
        _session["start_time"] = now
        _session["last_activity"] = now
        _session["last_save_time"] = now
        _session["accumulated_seconds"] = 0
        print(f"[TELEMETRY] Session started")
        return
    
    # Calculate time since last activity
    elapsed = now - _session["last_activity"]
    
    # If idle too long, start new session
    if elapsed > SESSION_TIMEOUT:
        # Save previous session first
        if _session["accumulated_seconds"] > 10:
            _save_usage_time(_session["accumulated_seconds"])
        
        # Start new session
        _session["start_time"] = now
        _session["last_activity"] = now
        _session["last_save_time"] = now
        _session["accumulated_seconds"] = 0
        print(f"[TELEMETRY] New session started (was idle)")
        return
    
    # Accumulate active time
    if elapsed > 0 and elapsed < SESSION_TIMEOUT:
        _session["accumulated_seconds"] += elapsed
    
    _session["last_activity"] = now
    
    # Save periodically
    time_since_save = now - (_session["last_save_time"] or now)
    
    if time_since_save >= SAVE_INTERVAL and _session["accumulated_seconds"] > 0:
        _save_usage_time(_session["accumulated_seconds"])
        _session["accumulated_seconds"] = 0
        _session["last_save_time"] = now


def _save_usage_time(seconds):
    """Save accumulated usage time to databases."""
    if seconds < 5:  # Ignore tiny amounts
        return
    
    hours = seconds / 3600.0
    device_id = get_device_id()
    email = get_email()
    now_iso = datetime.now().isoformat()
    
    print(f"[TELEMETRY] Saving {round(seconds, 1)} seconds ({round(hours * 60, 2)} min) for {email or device_id[:8]}")
    
        # 1. Save to TELEMETRY database
    try:
        init_db()
        conn = sqlite3.connect(TELEMETRY_DB)
        c = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Update total stats
        c.execute("""
            INSERT INTO stats (device_id, email, install_date, last_seen, active_hours, app_version, license_tier)
            VALUES (?, ?, ?, ?, ?, '1.10', 'free')
            ON CONFLICT(device_id) DO UPDATE SET
                email = COALESCE(?, email),
                last_seen = ?,
                active_hours = active_hours + ?
        """, (device_id, email, now_iso, now_iso, hours, email, now_iso, hours))
        
        # Update DAILY stats (NEW)
        c.execute("""
            INSERT INTO daily_usage (device_id, date, hours)
            VALUES (?, ?, ?)
            ON CONFLICT(device_id, date) DO UPDATE SET
                hours = hours + ?
        """, (device_id, today, hours, hours))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TELEMETRY] ✗ telemetry.db error: {e}")
    
    # 2. Save to LICENSE database (for referral tracking)
    try:
        if os.path.exists(LICENSE_DB):
            init_license_db()
            conn = sqlite3.connect(LICENSE_DB)
            c = conn.cursor()
            
            # Upsert activations
            c.execute("""
                INSERT INTO activations (device_id, license_key, activated_at, last_validated, usage_hours, email)
                VALUES (?, 'FREE_USER', ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    usage_hours = usage_hours + ?,
                    last_validated = ?,
                    email = COALESCE(?, email)
            """, (device_id, now_iso, now_iso, hours, email, hours, now_iso, email))
            
            # Update referral progress if applicable
            if email:
                c.execute("""
                    UPDATE referrals 
                    SET usage_hours = usage_hours + ?,
                        is_complete = CASE 
                            WHEN usage_hours + ? >= 7 THEN 1 
                            ELSE 0 
                        END,
                        completed_at = CASE 
                            WHEN usage_hours + ? >= 7 AND is_complete = 0 THEN ?
                            ELSE completed_at
                        END
                    WHERE referred_email = ? AND is_complete = 0
                """, (hours, hours, hours, now_iso, email))
            
            conn.commit()
            conn.close()
            
            print(f"[TELEMETRY] ✓ Saved {round(seconds/60, 1)} min to databases")
    except Exception as e:
        print(f"[TELEMETRY] ✗ license.db error: {e}")
    
    # 3. Sync to server (privacy-safe analytics)
    try:
        import server_sync
        server_sync.send_usage_ping(device_id, hours, email)
    except Exception as e:
        # Server offline or not configured - that's OK, local data already saved
        pass


def get_active_hours():
    """Get current session's accumulated hours (not yet saved)."""
    return _session["accumulated_seconds"] / 3600.0

# =============================================================================
# BACKGROUND TELEMETRY
# =============================================================================

def send_ping():
    """Periodic background save."""
    if _session["accumulated_seconds"] > 0:
        _save_usage_time(_session["accumulated_seconds"])
        _session["accumulated_seconds"] = 0
        _session["last_save_time"] = time.time()


def start_telemetry():
    """Start background telemetry thread."""
    import threading
    
    # Initialize
    init_db()
    init_license_db()
    
    device_id = get_device_id()
    email = get_email()
    
    # Register device immediately
    try:
        conn = sqlite3.connect(TELEMETRY_DB)
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO stats 
            (device_id, email, install_date, last_seen, active_hours, app_version, license_tier)
            VALUES (?, ?, ?, ?, 0, '1.10', 'free')
        """, (device_id, email, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass
    
    # Try to register on server (if available)
    try:
        import server_sync
        country = get_country_from_ip()
        server_sync.register_device(device_id, email, country)
    except:
        pass  # Server not available, that's OK
    
    print(f"[TELEMETRY] ✓ Device: {device_id[:8]}... | Email: {email or 'Not set'}")
    
    def _ping_loop():
        while True:
            time.sleep(PING_INTERVAL)
            send_ping()
    
    thread = threading.Thread(target=_ping_loop, daemon=True, name="Telemetry")
    thread.start()
    print(f"[TELEMETRY] Started (saves every {SAVE_INTERVAL}s, background ping every {PING_INTERVAL//60}min)")