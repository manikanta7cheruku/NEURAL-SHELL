"""
trigger_modules/database.py
Trigger DB access — load triggers, update fire stats.
Uses WAL mode so it can share the DB with backend/routes/triggers.py.
"""
import os
import json
import sqlite3
from datetime import datetime

from trigger_modules.config import TRIGGERS_DB


def load_triggers():
    """Load all enabled triggers from the DB. Returns list of dicts."""
    if not os.path.exists(TRIGGERS_DB):
        return []
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT * FROM triggers WHERE enabled = 1"
        ).fetchall()
        conn.close()

        triggers = []
        for row in rows:
            d = dict(row)
            d["enabled"] = bool(d.get("enabled", 1))
            d["silent"]  = bool(d.get("silent", 0))
            try:
                d["action_data"] = json.loads(d.get("action_data") or "{}")
            except Exception:
                d["action_data"] = {}
            triggers.append(d)
        return triggers
    except Exception as e:
        print(f"[TRIGGER DAEMON] DB load error: {e}")
        return []


def update_fire_stats(trigger_id):
    """Increment fire_count and update last_fired timestamp."""
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE triggers SET fire_count = fire_count + 1, "
            "last_fired = ? WHERE id = ?",
            (datetime.now().isoformat(), trigger_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TRIGGER DAEMON] Stats update error: {e}")