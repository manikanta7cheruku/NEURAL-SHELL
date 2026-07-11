"""
=============================================================================
backend/routes/triggers.py

Triggers CRUD API + database schema.

TRIGGER TYPES (activation methods):
  hotkey   → global keyboard shortcut (works when Seven closed)
  voice    → "Seven [word]" phrase (works when Seven closed via daemon)
  audio    → snap/clap detection (requires compatible mic)
  tray     → click from tray menu

ACTION TYPES (what trigger does):
  open_app       → launch application
  open_url       → open URL in browser
  open_file      → open file
  open_folder    → open folder in Explorer
  open_workspace → restore saved workspace
  run_command    → execute shell command
  seven_action   → internal Seven action (mute, pause, etc.)

STORAGE: SQLite WAL mode at seven_data/triggers.db
  Shared with trigger_daemon.py (concurrent access via WAL)
=============================================================================
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from colorama import Fore


# ─────────────────────────────────────────────────────────────────────────
# DATABASE PATH
# ─────────────────────────────────────────────────────────────────────────

try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception:
    print(Fore.YELLOW + "[TRIGGERS] seven_paths unavailable, using fallback")
    _SEVEN_DATA = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "seven_data"
    )

os.makedirs(_SEVEN_DATA, exist_ok=True)
TRIGGERS_DB = os.path.join(_SEVEN_DATA, "triggers.db")

print(Fore.GREEN + f"[TRIGGERS] DB: {TRIGGERS_DB}")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────

class TriggerCreate(BaseModel):
    name:          str
    action_type:   str                    # open_app, open_url, open_workspace, etc.
    action_data:   dict                   # action-specific parameters

    # Activation methods (all optional, but at least one must be set)
    hotkey:        Optional[str] = None   # "ctrl+shift+f" or "f9" or "shift+space"
    voice_phrase:  Optional[str] = None   # "focus" (user says "Seven focus")
    audio_pattern: Optional[str] = None   # "1_tap", "2_tap", "3_tap" or null

    # Settings
    enabled:       bool = True
    silent:        bool = False           # skip sound/toast if True
    icon:          Optional[str] = None   # emoji or icon name for UI


class TriggerUpdate(BaseModel):
    name:          Optional[str]  = None
    action_type:   Optional[str]  = None
    action_data:   Optional[dict] = None
    hotkey:        Optional[str]  = None
    voice_phrase:  Optional[str]  = None
    audio_pattern: Optional[str]  = None
    enabled:       Optional[bool] = None
    silent:        Optional[bool] = None
    icon:          Optional[str]  = None


# ─────────────────────────────────────────────────────────────────────────
# DATABASE CONNECTION
# ─────────────────────────────────────────────────────────────────────────

def _get_conn():
    """Get SQLite connection with WAL mode (concurrent access)."""
    conn = sqlite3.connect(TRIGGERS_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call every startup."""
    try:
        with _get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS triggers (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    name          TEXT NOT NULL,
                    action_type   TEXT NOT NULL
                                  CHECK(action_type IN (
                                      'open_app', 'open_url', 'open_file',
                                      'open_folder', 'open_workspace',
                                      'run_command', 'seven_action'
                                  )),
                    action_data   TEXT NOT NULL,      -- JSON blob
                    hotkey        TEXT,               -- e.g. "ctrl+shift+f"
                    voice_phrase  TEXT,               -- e.g. "focus"
                    audio_pattern TEXT,               -- 1_tap, 2_tap, 3_tap
                    enabled       INTEGER DEFAULT 1
                                  CHECK(enabled IN (0, 1)),
                    silent        INTEGER DEFAULT 0
                                  CHECK(silent IN (0, 1)),
                    icon          TEXT,
                    created_at    TEXT NOT NULL,
                    updated_at    TEXT NOT NULL,
                    last_fired    TEXT,
                    fire_count    INTEGER DEFAULT 0
                )
            """)

            # Indexes for daemon lookup speed
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triggers_hotkey       ON triggers(hotkey)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triggers_voice_phrase ON triggers(voice_phrase)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triggers_audio        ON triggers(audio_pattern)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_triggers_enabled      ON triggers(enabled)")

            # Workspaces table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    name         TEXT NOT NULL,
                    description  TEXT,
                    apps         TEXT NOT NULL,       -- JSON array of app configs
                    icon         TEXT,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    last_used    TEXT,
                    use_count    INTEGER DEFAULT 0
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_name ON workspaces(name)")

            conn.commit()
            print(Fore.GREEN + "[TRIGGERS] DB initialized (triggers + workspaces tables)")

    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] DB init failed: {e}")


# Run on import
init_db()


# ─────────────────────────────────────────────────────────────────────────
# ROW SERIALIZATION
# ─────────────────────────────────────────────────────────────────────────

def _row_to_dict(row):
    """Convert SQLite row to JSON-serializable dict."""
    d = dict(row)
    d["enabled"] = bool(d.get("enabled", 1))
    d["silent"]  = bool(d.get("silent", 0))

    # Parse action_data JSON
    try:
        d["action_data"] = json.loads(d.get("action_data") or "{}")
    except Exception:
        d["action_data"] = {}

    return d


def _validate_action_type(action_type):
    """Validate action_type is in allowed set."""
    valid = {
        "open_app", "open_url", "open_file", "open_folder",
        "open_workspace", "run_command", "seven_action"
    }
    if action_type not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action_type. Must be one of: {', '.join(valid)}"
        )


def _validate_hotkey_format(hotkey):
    """Basic hotkey format validation."""
    if not hotkey:
        return
    # Allow: single keys (f9), 2-key combos (ctrl+space), 3-key combos (ctrl+shift+f)
    parts = hotkey.lower().replace(" ", "").split("+")
    if len(parts) < 1 or len(parts) > 4:
        raise HTTPException(
            status_code=400,
            detail="Hotkey must have 1-4 keys separated by '+' (e.g., 'f9', 'ctrl+space', 'ctrl+shift+f')"
        )


def _check_hotkey_conflict(hotkey, exclude_id=None):
    """Check if hotkey is already used by another trigger."""
    if not hotkey:
        return None

    hotkey_normalized = hotkey.lower().replace(" ", "")

    with _get_conn() as conn:
        query = "SELECT id, name FROM triggers WHERE LOWER(hotkey) = ? AND enabled = 1"
        params = [hotkey_normalized]

        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)

        row = conn.execute(query, params).fetchone()

    return dict(row) if row else None


def _check_voice_phrase_conflict(phrase, exclude_id=None):
    """Check if voice phrase is already used."""
    if not phrase:
        return None

    phrase_normalized = phrase.lower().strip()

    with _get_conn() as conn:
        query = "SELECT id, name FROM triggers WHERE LOWER(voice_phrase) = ? AND enabled = 1"
        params = [phrase_normalized]

        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)

        row = conn.execute(query, params).fetchone()

    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────
# ROUTES — SPECIFIC BEFORE PARAMETERIZED (FastAPI order matters)
# ─────────────────────────────────────────────────────────────────────────

@router.get("/api/triggers/stats")
def get_stats():
    """Aggregate stats for dashboard badge."""
    try:
        with _get_conn() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM triggers").fetchone()[0]
            enabled   = conn.execute("SELECT COUNT(*) FROM triggers WHERE enabled = 1").fetchone()[0]
            hotkey_ct = conn.execute("SELECT COUNT(*) FROM triggers WHERE hotkey IS NOT NULL").fetchone()[0]
            voice_ct  = conn.execute("SELECT COUNT(*) FROM triggers WHERE voice_phrase IS NOT NULL").fetchone()[0]
            audio_ct  = conn.execute("SELECT COUNT(*) FROM triggers WHERE audio_pattern IS NOT NULL").fetchone()[0]

        return {
            "total":   total,
            "enabled": enabled,
            "hotkey":  hotkey_ct,
            "voice":   voice_ct,
            "audio":   audio_ct,
        }
    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/triggers/active")
def get_active():
    """Return only enabled triggers (used by daemon for lookup)."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM triggers WHERE enabled = 1 ORDER BY name ASC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] active error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/triggers")
def list_triggers(
    action_type: Optional[str] = None,
    enabled:     Optional[bool] = None,
):
    """List all triggers with optional filters."""
    try:
        with _get_conn() as conn:
            query = "SELECT * FROM triggers WHERE 1=1"
            params = []

            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)

            if enabled is not None:
                query += " AND enabled = ?"
                params.append(1 if enabled else 0)

            query += " ORDER BY created_at DESC"

            rows = conn.execute(query, params).fetchall()
            return [_row_to_dict(r) for r in rows]

    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] list error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/triggers")
def create_trigger(body: TriggerCreate):
    """Create a new trigger with conflict checking."""

    # Validation
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Trigger name cannot be empty")

    _validate_action_type(body.action_type)
    _validate_hotkey_format(body.hotkey)

    # Must have at least one activation method
    if not any([body.hotkey, body.voice_phrase, body.audio_pattern]):
        raise HTTPException(
            status_code=400,
            detail="At least one activation method required (hotkey, voice, or audio)"
        )

    # Conflict checks
    if body.hotkey:
        conflict = _check_hotkey_conflict(body.hotkey)
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Hotkey '{body.hotkey}' is already used by trigger '{conflict['name']}'"
            )

    if body.voice_phrase:
        conflict = _check_voice_phrase_conflict(body.voice_phrase)
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Voice phrase '{body.voice_phrase}' is already used by trigger '{conflict['name']}'"
            )

    now_iso = datetime.now().isoformat()

    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO triggers
                    (name, action_type, action_data, hotkey, voice_phrase,
                     audio_pattern, enabled, silent, icon, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body.name.strip(),
                    body.action_type,
                    json.dumps(body.action_data),
                    body.hotkey.lower().replace(" ", "") if body.hotkey else None,
                    body.voice_phrase.lower().strip() if body.voice_phrase else None,
                    body.audio_pattern,
                    1 if body.enabled else 0,
                    1 if body.silent else 0,
                    body.icon,
                    now_iso,
                    now_iso,
                )
            )
            conn.commit()
            new_id = cursor.lastrowid

        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM triggers WHERE id = ?", (new_id,)
            ).fetchone()

        print(Fore.GREEN + f"[TRIGGERS] Created #{new_id}: {body.name}")

        # Notify daemon to reload triggers (via file signal)
        _signal_daemon_reload()

        return {"success": True, "trigger": _row_to_dict(row)}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] create error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/triggers/{trigger_id}")
def update_trigger(trigger_id: int, body: TriggerUpdate):
    """Update trigger fields (partial update)."""
    try:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT * FROM triggers WHERE id = ?", (trigger_id,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

            # Validation for updated fields
            if body.action_type is not None:
                _validate_action_type(body.action_type)

            if body.hotkey is not None:
                _validate_hotkey_format(body.hotkey)
                if body.hotkey:
                    conflict = _check_hotkey_conflict(body.hotkey, exclude_id=trigger_id)
                    if conflict:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Hotkey '{body.hotkey}' is already used by trigger '{conflict['name']}'"
                        )

            if body.voice_phrase is not None and body.voice_phrase:
                conflict = _check_voice_phrase_conflict(body.voice_phrase, exclude_id=trigger_id)
                if conflict:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Voice phrase '{body.voice_phrase}' is already used by trigger '{conflict['name']}'"
                    )

            # Build UPDATE query
            updates = []
            params  = []

            if body.name is not None:
                if not body.name.strip():
                    raise HTTPException(status_code=400, detail="Name cannot be empty")
                updates.append("name = ?")
                params.append(body.name.strip())

            if body.action_type is not None:
                updates.append("action_type = ?")
                params.append(body.action_type)

            if body.action_data is not None:
                updates.append("action_data = ?")
                params.append(json.dumps(body.action_data))

            if body.hotkey is not None:
                updates.append("hotkey = ?")
                params.append(body.hotkey.lower().replace(" ", "") if body.hotkey else None)

            if body.voice_phrase is not None:
                updates.append("voice_phrase = ?")
                params.append(body.voice_phrase.lower().strip() if body.voice_phrase else None)

            if body.audio_pattern is not None:
                updates.append("audio_pattern = ?")
                params.append(body.audio_pattern if body.audio_pattern else None)

            if body.enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if body.enabled else 0)

            if body.silent is not None:
                updates.append("silent = ?")
                params.append(1 if body.silent else 0)

            if body.icon is not None:
                updates.append("icon = ?")
                params.append(body.icon)

            if not updates:
                return {"success": True, "trigger": _row_to_dict(existing)}

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            params.append(trigger_id)
            conn.execute(
                f"UPDATE triggers SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()

            updated = conn.execute(
                "SELECT * FROM triggers WHERE id = ?", (trigger_id,)
            ).fetchone()

        print(Fore.GREEN + f"[TRIGGERS] Updated #{trigger_id}")
        _signal_daemon_reload()

        return {"success": True, "trigger": _row_to_dict(updated)}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/triggers/{trigger_id}")
def delete_trigger(trigger_id: int):
    """Permanently delete a trigger."""
    try:
        with _get_conn() as conn:
            existing = conn.execute(
                "SELECT id, name FROM triggers WHERE id = ?", (trigger_id,)
            ).fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

            conn.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,))
            conn.commit()

        print(Fore.GREEN + f"[TRIGGERS] Deleted #{trigger_id}: {existing['name']}")
        _signal_daemon_reload()

        return {"success": True, "deleted_id": trigger_id}

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/triggers/{trigger_id}/fire")
def fire_trigger(trigger_id: int):
    """Manually fire a trigger (from UI test button)."""
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM triggers WHERE id = ?", (trigger_id,)
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

            trigger = _row_to_dict(row)

            # Update fire count and timestamp
            conn.execute(
                "UPDATE triggers SET fire_count = fire_count + 1, last_fired = ? WHERE id = ?",
                (datetime.now().isoformat(), trigger_id)
            )
            conn.commit()

        # Execute trigger action
        try:
            from main_modules.handlers.trigger_handler import execute_trigger_action
            success, message = execute_trigger_action(trigger)
        except ImportError as ie:
            print(Fore.YELLOW + f"[TRIGGERS] Handler import failed: {ie}")
            success, message = False, f"Trigger handler not available: {ie}"
        except Exception as ex:
            print(Fore.RED + f"[TRIGGERS] Execution error: {ex}")
            import traceback; traceback.print_exc()
            success, message = False, str(ex)

        return {
            "success": success,
            "message": message,
            "trigger_id": trigger_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(Fore.RED + f"[TRIGGERS] fire error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────
# DAEMON RELOAD SIGNAL
# ─────────────────────────────────────────────────────────────────────────

def _signal_daemon_reload():
    """
    Signal trigger_daemon.py to reload triggers from DB.
    Uses a marker file the daemon polls every 2 seconds.
    """
    try:
        signal_file = os.path.join(_SEVEN_DATA, "trigger_reload.signal")
        with open(signal_file, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGERS] Reload signal failed: {e}")


# ─────────────────────────────────────────────────────────────────────────
# DIRECT DB ACCESS (for daemon and internal use)
# ─────────────────────────────────────────────────────────────────────────

def db_get_all_active():
    """Get all enabled triggers. Used by daemon."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM triggers WHERE enabled = 1"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGERS] db_get_all_active failed: {e}")
        return []


def db_get_by_hotkey(hotkey):
    """Find trigger by hotkey. Used by daemon on key press."""
    if not hotkey:
        return None
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM triggers WHERE LOWER(hotkey) = ? AND enabled = 1",
                (hotkey.lower(),)
            ).fetchone()
        return _row_to_dict(row) if row else None
    except Exception:
        return None


def db_get_by_voice_phrase(phrase):
    """Find trigger by voice phrase. Used by daemon on wake word."""
    if not phrase:
        return None
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM triggers WHERE LOWER(voice_phrase) = ? AND enabled = 1",
                (phrase.lower().strip(),)
            ).fetchone()
        return _row_to_dict(row) if row else None
    except Exception:
        return None


def db_get_by_audio_pattern(pattern):
    """Find trigger by audio pattern (1_tap, 2_tap, 3_tap). Used by daemon."""
    if not pattern:
        return None
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM triggers WHERE audio_pattern = ? AND enabled = 1",
                (pattern,)
            ).fetchone()
        return _row_to_dict(row) if row else None
    except Exception:
        return None


def db_increment_fire_count(trigger_id):
    """Update fire count after execution. Used by daemon."""
    try:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE triggers SET fire_count = fire_count + 1, last_fired = ? WHERE id = ?",
                (datetime.now().isoformat(), trigger_id)
            )
            conn.commit()
    except Exception as e:
        print(Fore.YELLOW + f"[TRIGGERS] fire count update failed: {e}")