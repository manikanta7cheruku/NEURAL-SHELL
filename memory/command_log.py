"""
=============================================================================
PROJECT SEVEN - memory/command_log.py (Command History)
Version: 1.6
Purpose: Logs every app command Seven executes with timestamp and result.
         Persists to JSON so history survives restarts.

STORAGE: ./seven_data/command_log.json
=============================================================================
"""

import json
import os
from datetime import datetime
from colorama import Fore

LOG_PATH = "./seven_data/command_log.json"


class CommandLog:
    """
    Tracks every OPEN/CLOSE command Seven executes.
    
    Why this matters:
    - Debug failed commands (which apps keep failing?)
    - See usage patterns (which apps does user open most?)
    - Future: Seven can say "You usually open Chrome around this time"
    """

    def __init__(self):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w") as f:
                json.dump([], f)
        print(Fore.CYAN + f"[COMMAND LOG] Initialized. Storage: {os.path.abspath(LOG_PATH)}")

    def _load(self):
        """Load all logs from disk."""
        try:
            with open(LOG_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, logs):
        """Write logs to disk."""
        with open(LOG_PATH, "w") as f:
            json.dump(logs, f, indent=2)

    def log_command(self, action, target, success, detail=""):
        """
        Record a command execution.

        Args:
            action:  "OPEN" or "CLOSE"
            target:  app name (e.g., "chrome", "notepad")
            success: True if it worked, False if it failed
            detail:  optional note (e.g., "URI scheme" or "process not found")
        """
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "target": target,
            "success": success,
            "detail": detail
        }

        logs = self._load()
        logs.append(entry)
        self._save(logs)

        status = "✅" if success else "❌"
        print(Fore.CYAN + f"[COMMAND LOG] {status} {action} {target} — {detail}")

    def get_recent(self, count=10):
        """Return the last N commands."""
        logs = self._load()
        return logs[-count:]

    def get_failures(self):
        """Return all failed commands."""
        logs = self._load()
        return [e for e in logs if not e["success"]]

    def get_stats(self):
        """Summary statistics."""
        logs = self._load()
        if not logs:
            return {"total": 0, "opens": 0, "closes": 0,
                    "successes": 0, "failures": 0, "success_rate": "N/A"}

        total = len(logs)
        opens = sum(1 for l in logs if l["action"] == "OPEN")
        closes = sum(1 for l in logs if l["action"] == "CLOSE")
        successes = sum(1 for l in logs if l["success"])
        failures = total - successes
        rate = f"{(successes / total) * 100:.1f}%" if total > 0 else "N/A"

        return {
            "total": total, "opens": opens, "closes": closes,
            "successes": successes, "failures": failures, "success_rate": rate
        }

    def get_most_used(self, top_n=5):
        """Return the most frequently commanded apps."""
        logs = self._load()
        counts = {}
        for entry in logs:
            target = entry["target"].lower()
            counts[target] = counts.get(target, 0) + 1
        sorted_apps = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_apps[:top_n]

    def clear(self):
        """Wipe all command logs."""
        self._save([])
        print(Fore.YELLOW + "[COMMAND LOG] All logs cleared.")


# Module-level instance
command_log = CommandLog()