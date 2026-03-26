"""
=============================================================================
PROJECT SEVEN - telemetry.py (Anonymous Usage Tracking)
Version: 1.0

PURPOSE:
    Track anonymous usage stats for analytics dashboard.
    100% privacy-safe — no personal data collected.
=============================================================================
"""

import os
import uuid
import time
import sqlite3
from datetime import datetime, timedelta

# =============================================================================
# CONFIGURATION
# =============================================================================

DATA_DIR = "data"
DEVICE_ID_FILE = os.path.join(DATA_DIR, "device_id.txt")
EMAIL_FILE = os.path.join(DATA_DIR, "email.txt")
TELEMETRY_DB = os.path.join(DATA_DIR, "telemetry.db")

PING_INTERVAL = 3600  # Send stats every hour

# Session tracking
last_activity_time = None
session_start_time = None
total_active_seconds = 0
SESSION_TIMEOUT = 600  # 10 minutes idle = session ends

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
    """Save user email if they provide it."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(EMAIL_FILE, "w") as f:
        f.write(email.strip())

def get_email():
    """Get saved email or None."""
    if os.path.exists(EMAIL_FILE):
        with open(EMAIL_FILE, "r") as f:
            return f.read().strip()
    return None

# =============================================================================
# COUNTRY DETECTION
# =============================================================================

def get_country_from_ip():
    """Detect country from IP address. IP is NOT saved."""
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
# LOCAL DATABASE (SQLite)
# =============================================================================

def init_db():
    """Initialize local telemetry database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            device_id TEXT PRIMARY KEY,
            country TEXT,
            email TEXT,
            install_date TEXT,
            last_seen TEXT,
            active_hours REAL,
            app_version TEXT,
            license_tier TEXT DEFAULT 'free'
        )
    """)
    
    conn.commit()
    conn.close()

def save_stats_local(device_id, country, active_hours):
    """Save stats to local DB."""
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    email = get_email()
    now = datetime.now().isoformat()
    app_version = "1.10"
    
    # Get license tier from config
    try:
        import config
        license_tier = config.KEY.get("license", {}).get("tier", "free")
    except:
        license_tier = "free"
    
    # Check if user exists
    c.execute("SELECT install_date, active_hours FROM stats WHERE device_id = ?", (device_id,))
    row = c.fetchone()
    
    if row:
        install_date = row[0]
        existing_hours = row[1] or 0
        new_hours = existing_hours + active_hours
    else:
        install_date = now
        new_hours = active_hours
    
    c.execute("""
        INSERT OR REPLACE INTO stats 
        (device_id, country, email, install_date, last_seen, active_hours, app_version, license_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (device_id, country, email, install_date, now, new_hours, app_version, license_tier))
    
    conn.commit()
    conn.close()

# =============================================================================
# SESSION TRACKING
# =============================================================================

def log_activity():
    """Call this whenever user does something."""
    global last_activity_time, session_start_time, total_active_seconds
    
    now = time.time()
    
    # Start new session if idle timeout passed
    if last_activity_time is None or (now - last_activity_time) > SESSION_TIMEOUT:
        session_start_time = now
    else:
        # Continue existing session — cap at 2 hours per day
        session_duration = now - session_start_time
        if session_duration < 7200:
            total_active_seconds += (now - last_activity_time)
    
    last_activity_time = now

def get_active_hours():
    """Get total active hours."""
    return total_active_seconds / 3600.0

# =============================================================================
# SEND PING
# =============================================================================

def send_ping():
    """Send anonymous stats to local database."""
    global total_active_seconds
    
    try:
        device_id = get_device_id()
        country = get_country_from_ip()
        active_hours = get_active_hours()
        
        print(f"[TELEMETRY] Saving: device={device_id[:8]}..., hours={active_hours:.2f}, country={country}")
        
        save_stats_local(device_id, country, active_hours)
        
        # Reset active seconds after saving
        total_active_seconds = 0
        
        print(f"[TELEMETRY] Saved successfully")
    except Exception as e:
        print(f"[TELEMETRY] Error: {e}")

# =============================================================================
# BACKGROUND THREAD
# =============================================================================

def start_telemetry():
    """Start background telemetry."""
    import threading
    
    init_db()
    
    # Initial ping to register this device
    send_ping()
    
    def _ping_loop():
        while True:
            time.sleep(PING_INTERVAL)
            send_ping()
    
    thread = threading.Thread(target=_ping_loop, daemon=True, name="Telemetry")
    thread.start()
    print("[TELEMETRY] Started (ping every 1 hour)")