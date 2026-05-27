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

def _get_data_dir():
    """Always use %APPDATA%\SEVEN\data — works in dev and packaged."""
    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
    d = os.path.join(app_data, 'SEVEN', 'data')
    os.makedirs(d, exist_ok=True)
    return d

DATA_DIR      = _get_data_dir()
DEVICE_ID_FILE = os.path.join(DATA_DIR, "device_id.txt")
EMAIL_FILE     = os.path.join(DATA_DIR, "email.txt")
TELEMETRY_DB   = os.path.join(DATA_DIR, "telemetry.db")
LICENSE_DB     = os.path.join(DATA_DIR, "license.db")

# Timing constants
SESSION_TIMEOUT  = 600   # 10 min idle = session ends
SAVE_INTERVAL    = 60    # Save to local DB every 60 seconds
SERVER_INTERVAL  = 120   # Ping server every 2 minutes

# Session state
_session = {
    "start_time":          None,
    "last_activity":       None,
    "accumulated_seconds": 0,
    "last_save_time":      None,
    "last_server_sync":    None,
    "pending_minutes":     0,      # minutes since last server sync ONLY
    "total_synced_minutes": 0,     # total already sent to server
}

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


def _format_time(total_minutes):
    """Convert minutes to readable string. e.g. 1502 → '1 day 1 hr 2 min'"""
    total_minutes = int(total_minutes)
    days    = total_minutes // 1440
    remain  = total_minutes % 1440
    hours   = remain // 60
    minutes = remain % 60

    if days > 0:
        return f"{days} day{'s' if days > 1 else ''} {hours} hr {minutes} min"
    elif hours > 0:
        return f"{hours} hr {minutes} min"
    else:
        return f"{minutes} min"


def _save_usage_time(seconds, sync_server=False):
    """
    Save accumulated usage time to local databases.
    sync_server=True → also ping Render server with pending minutes.
    """
    if seconds < 5:
        return

    minutes   = seconds / 60.0
    device_id = get_device_id()
    email     = get_email()
    now_iso   = datetime.now().isoformat()
    today     = datetime.now().strftime("%Y-%m-%d")

    print(f"[TELEMETRY] Saving {round(minutes, 1)} min for "
          f"{email or device_id[:8]}...")

    # 1. Local telemetry.db
    try:
        init_db()
        conn = sqlite3.connect(TELEMETRY_DB)
        c    = conn.cursor()

        c.execute("""
            INSERT INTO stats
                (device_id, email, install_date, last_seen, active_hours, app_version, license_tier)
            VALUES (?, ?, ?, ?, ?, '1.1.0', 'free')
            ON CONFLICT(device_id) DO UPDATE SET
                email        = COALESCE(?, email),
                last_seen    = ?,
                active_hours = active_hours + ?
        """, (device_id, email, now_iso, now_iso, minutes / 60.0,
              email, now_iso, minutes / 60.0))

        c.execute("""
            INSERT INTO daily_usage (device_id, date, hours)
            VALUES (?, ?, ?)
            ON CONFLICT(device_id, date) DO UPDATE SET
                hours = hours + ?
        """, (device_id, today, minutes / 60.0, minutes / 60.0))

        conn.commit()
        conn.close()
        print(f"[TELEMETRY] Local DB saved — {_format_time(_get_total_minutes())}")
    except Exception as e:
        print(f"[TELEMETRY] local DB error: {e}")

    # 2. Local license.db (referral tracking)
    try:
        if os.path.exists(LICENSE_DB):
            init_license_db()
            conn = sqlite3.connect(LICENSE_DB)
            c    = conn.cursor()

            c.execute("""
                INSERT INTO activations
                    (device_id, license_key, activated_at, last_validated, usage_hours, email)
                VALUES (?, 'FREE_USER', ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    usage_hours   = usage_hours + ?,
                    last_validated = ?,
                    email         = COALESCE(?, email)
            """, (device_id, now_iso, now_iso, minutes / 60.0, email,
                  minutes / 60.0, now_iso, email))

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
                """, (minutes / 60.0, minutes / 60.0,
                      minutes / 60.0, now_iso, email))

            conn.commit()
            conn.close()
    except Exception as e:
        print(f"[TELEMETRY] license.db error: {e}")

    # 3. Server ping (every SERVER_INTERVAL seconds only)
    if sync_server:
        pending = _session["pending_minutes"]
        if pending >= 0.5:   # at least 30 seconds accumulated
            try:
                import server_sync
                # Also send total so server can correct if behind
                total_min = _get_total_minutes()
                result = server_sync.send_usage_ping(
                        device_id, round(pending, 2), email,
                        total_minutes=round(total_min, 2)
                    )
                if result and result.get("success"):
                    _session["pending_minutes"]    = 0
                    _session["total_synced_minutes"] += pending
                    _session["last_server_sync"]   = time.time()
                    print(f"[TELEMETRY] Server synced: "
                          f"{round(pending, 2)} min sent | "
                          f"total synced: "
                          f"{round(_session['total_synced_minutes'], 1)} min")
            except Exception as e:
                print(f"[TELEMETRY] Server sync failed (ok): {e}")


def _get_total_minutes():
    """Read total minutes from local telemetry.db."""
    try:
        conn = sqlite3.connect(TELEMETRY_DB)
        c    = conn.cursor()
        c.execute("SELECT active_hours FROM stats WHERE device_id = ?",
                  (get_device_id(),))
        row = c.fetchone()
        conn.close()
        return (row[0] or 0) * 60 if row else 0
    except Exception:
        return 0


def get_active_hours():
    """Get current session accumulated hours (not yet saved)."""
    return _session["accumulated_seconds"] / 3600.0


def get_active_minutes():
    """Get current session accumulated minutes (not yet saved)."""
    return _session["accumulated_seconds"] / 60.0

# =============================================================================
# BACKGROUND TELEMETRY
# =============================================================================

def send_ping(force_server=False):
    """
    Save accumulated time locally.
    Send ONLY new minutes (delta) to server every SERVER_INTERVAL.
    Never sends total - always sends what accumulated since last sync.
    """
    try:
        if _session["accumulated_seconds"] <= 0:
            return
    except Exception as e:
        print(f"[TELEMETRY] send_ping error: {e}")
        import traceback
        traceback.print_exc()
        return

    now       = time.time()
    last_sync = _session["last_server_sync"] or 0
    do_server = force_server or (now - last_sync >= SERVER_INTERVAL)

    # pending_minutes = only what has NOT been sent to server yet
    pending_add = _session["accumulated_seconds"] / 60.0
    _session["pending_minutes"] += pending_add

    _save_usage_time(_session["accumulated_seconds"], sync_server=do_server)
    _session["accumulated_seconds"] = 0
    _session["last_save_time"]      = now


def start_telemetry():
    """
    Start telemetry system.
    1. Init local DBs
    2. Register device on server immediately (background)
    3. Start background loop: log every 60s, save every 60s, server every 10min
    """
    import threading

    init_db()
    init_license_db()

    device_id = get_device_id()
    email     = get_email()

    # Register in local DB immediately
    try:
        conn = sqlite3.connect(TELEMETRY_DB)
        c    = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO stats
                (device_id, email, install_date, last_seen, active_hours,
                 app_version, license_tier)
            VALUES (?, ?, ?, ?, 0, '1.1.0', 'free')
        """, (device_id, email,
              datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Read name from config BEFORE starting thread
    user_name = None
    setup_complete = False
    try:
        import config as _cfg
        user_name = _cfg.KEY.get("identity", {}).get("user_name", None)
        setup_complete = _cfg.KEY.get("setup_complete", False)
    except Exception:
        pass

    # Only register on server if setup is complete AND we have identity
    # This prevents ghost rows from pre-setup pings
    def _register(_name=user_name, _email=email, _device_id=device_id,
                  _setup=setup_complete):
        try:
            # Skip if setup not done or no identity at all
            if not _setup:
                print("[TELEMETRY] Setup not complete — skipping server register")
                return
            if not _name and not _email:
                print("[TELEMETRY] No name or email — skipping server register")
                return

            import server_sync

            # Get country with fallback
            country = "Unknown"
            try:
                country = get_country_from_ip()
                # Validate country is ASCII-safe
                country.encode('ascii')
            except (UnicodeEncodeError, UnicodeDecodeError):
                country = "Unknown"
            except Exception:
                country = "Unknown"

            print(f"[TELEMETRY] Registering — "
                  f"name={_name} email={_email} country={country}")

            result = server_sync._post("/api/register", {
                "device_id":    _device_id,
                "email":        _email,
                "name":         _name,
                "country":      country,
                "referral_code": None
            })

            if result and result.get("success"):
                print(f"[TELEMETRY] Registered on server ✓ "
                      f"name={_name} country={country}")
            else:
                print(f"[TELEMETRY] Register returned: {result}")

        except Exception as e:
            import traceback
            print(f"[TELEMETRY] Register failed: {e}")
            traceback.print_exc()

    threading.Thread(
        target=_register, daemon=True, name="TelemetryRegister"
    ).start()

    total_min = _get_total_minutes()
    print(f"[TELEMETRY] Device: {device_id[:8]}... | "
          f"Email: {email or 'Not set'} | "
          f"Total: {_format_time(total_min)}")

    # Auto-create referral code for this user
    def _create_referral():
        try:
            if email:
                import server_sync as _ss
                code = _ss.get_or_create_referral_code(device_id, email)
                if code:
                    print(f"[TELEMETRY] Referral code: {code}")
                    # Save to config for UI to read
                    try:
                        import config as _cfg
                        _cfg.update_config({"referral_code": code})
                    except Exception:
                        pass
        except Exception as e:
            print(f"[TELEMETRY] Referral code fetch failed: {e}")

    threading.Thread(
        target=_create_referral, daemon=True, name="ReferralInit"
    ).start()

    # One-time correction ping on startup
    # Sends local total to server so server catches up immediately
    def _sync_total_on_startup(_device_id=device_id, _email=email,
                               _setup=setup_complete):
        try:
            if not _setup:
                return
            if not _email and not user_name:
                return

            import time as _t
            _t.sleep(5)  # Wait for server register to complete first

            total_min = _get_total_minutes()
            if total_min < 1:
                return

            import server_sync as _ss
            print(f"[TELEMETRY] Startup sync — sending total: "
                  f"{round(total_min, 1)} min to server")
            result = _ss.send_usage_ping(
                _device_id,
                minutes_delta=0,
                email=_email,
                total_minutes=round(total_min, 2)
            )
            if result and result.get("success"):
                print(f"[TELEMETRY] Server total corrected ✓")
            else:
                print(f"[TELEMETRY] Server correction result: {result}")
        except Exception as e:
            print(f"[TELEMETRY] Startup sync failed: {e}")

    threading.Thread(
        target=_sync_total_on_startup, daemon=True, name="TelemetryStartupSync"
    ).start()

    # Background loop
    def _ping_loop():
        tick_count = 0
        while True:
            try:
                time.sleep(60)
                tick_count += 1

                # Add 60 seconds - app is open so user is active
                _session["accumulated_seconds"] += 60
                _session["last_activity"] = time.time()
                if _session["start_time"] is None:
                    _session["start_time"] = time.time()

                # Keep Render server awake every 10 minutes
                if tick_count % 10 == 0:
                    try:
                        import server_sync as _ss
                        _ss.keep_alive()
                    except Exception:
                        pass

                send_ping()

            except Exception as e:
                print(f"[TELEMETRY] _ping_loop error: {e}")
                import traceback
                traceback.print_exc()

    thread = threading.Thread(
        target=_ping_loop, daemon=True, name="Telemetry"
    )
    thread.start()
    print("[TELEMETRY] Started — tracking every minute, "
          "server sync every 10 min")