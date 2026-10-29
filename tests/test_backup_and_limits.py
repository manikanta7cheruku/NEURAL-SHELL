"""
Backup and restore bring back everything that is yours, safely and only once; "clear all memory" really clears it all;
and the plan's limit on active triggers holds when a trigger is created, enabled or restored from a backup.
Everything uses temporary databases (tests/support.py), never the real ones.
"""
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from fastapi import HTTPException

from backend import backup
from memory import conversation_store, facts_store, learning_store


try:
    from hands import scheduler           # needs the Windows packages, which the minimal CI install leaves out
except ImportError:
    scheduler = None


def _fresh_stores():
    """Point every store at brand-new empty files, as on a new PC."""
    d = tempfile.mkdtemp(prefix="seven_bk_")
    facts_store.set_db_path(os.path.join(d, "facts.db"))
    conversation_store.set_db_path(os.path.join(d, "conversations.db"))
    learning_store.set_db_path(os.path.join(d, "learning.db"))
    if scheduler:
        scheduler.SCHEDULE_FILE = os.path.join(d, "schedules.json")
        scheduler._schedules, scheduler._next_id = [], 1
    from backend.routes.tasks import _get_conn as tasks_conn, init_db as init_tasks
    from backend.routes.triggers import init_db as init_triggers
    init_tasks()
    init_triggers()
    with tasks_conn() as c:
        c.execute("DELETE FROM tasks")
        c.commit()
    conn = backup._trigger_conn()
    conn.execute("DELETE FROM triggers")
    conn.execute("DELETE FROM workspaces")
    conn.commit()
    conn.close()
    from memory.command_log import command_log
    command_log.clear()


def _limit_of(n):
    """A stand-in for the plan check: n active triggers allowed (-1: no limit)."""
    def check_limit(feature, current):
        if n == -1:
            return {"allowed": True, "limit": -1, "tier": "free", "current": current, "upgrade_needed": None}
        return {"allowed": current < n, "limit": n, "tier": "free", "current": current,
                "upgrade_needed": None if current < n else "pro"}
    return mock.patch.dict(sys.modules, {"backend.api_server": types.SimpleNamespace(check_limit=check_limit)})


def _fill():
    owner = backup._owner()
    facts_store.add_fact("Likes strong coffee", speaker_id=owner, category="preference", key="drink")
    old = facts_store.add_fact("Lives in Pune", speaker_id=owner, category="location", key="city")
    facts_store.supersede_fact(old, "Lives in Hyderabad")
    cid = conversation_store.create_conversation(owner, "Trip planning")
    conversation_store.add_message(cid, "user", "Plan my weekend trip")
    conversation_store.add_message(cid, "assistant", "Here is a two day plan.")
    learning_store.upsert_goal(owner, "ship-beta", "Ship the beta")
    if scheduler:
        scheduler.add_schedule("reminder", "call mom", time_str="in 3 hours")
    from backend.routes.tasks import _get_conn as tasks_conn
    with tasks_conn() as c:
        c.execute("INSERT INTO tasks (text, due_date, priority, completed, created_at) VALUES (?,?,?,?,?)",
                  ("Submit the script", "2026-11-01", "high", 0, "2026-10-20T10:00:00"))
        c.commit()
    conn = backup._trigger_conn()
    conn.execute("INSERT INTO triggers (name, action_type, action_data, voice_phrase, enabled, silent, created_at, updated_at) "
                 "VALUES ('Focus', 'open_app', '{\"app\": \"notepad\"}', 'focus', 1, 0, '2026-10-01T09:00:00', '2026-10-01T09:00:00')")
    conn.execute("INSERT INTO workspaces (name, apps, created_at, updated_at) VALUES ('Work', '[{\"app\": \"code\"}]', "
                 "'2026-10-01T09:00:00', '2026-10-01T09:00:00')")
    conn.commit()
    conn.close()
    from memory.command_log import command_log
    command_log.import_entries([{"timestamp": "2026-10-20 10:00:00", "action": "OPEN", "target": "chrome",
                                 "success": True, "detail": "test"}])      # (log_command prints emoji)


def _counts():
    from backend.routes.tasks import _get_conn as tasks_conn
    conn = backup._trigger_conn()
    with tasks_conn() as c:
        tasks = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    out = {
        "facts": len(facts_store.export_rows()),
        "chats": len(conversation_store.export_all()),
        "messages": conversation_store.count_messages(),
        "goals": len(learning_store.export_all()["goals"]),
        "schedules": len(scheduler.get_all_schedules()) if scheduler else 0,
        "tasks": tasks,
        "triggers": conn.execute("SELECT COUNT(*) FROM triggers").fetchone()[0],
        "workspaces": conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0],
    }
    conn.close()
    return out


class BackupRoundTrip(unittest.TestCase):
    def setUp(self):
        _fresh_stores()

    def test_everything_comes_back_on_a_new_pc(self):
        _fill()
        before = _counts()
        self.assertEqual(before["facts"], 3)                         # two live, one superseded (the history is kept)
        data = json.loads(json.dumps(backup.export_all()))           # a real file: it must survive being written as JSON
        self.assertEqual(data["format"], "seven-backup")
        _fresh_stores()
        self.assertEqual(_counts()["facts"], 0)
        with _limit_of(-1):
            result = backup.import_all(data)
        self.assertEqual(_counts(), before)
        self.assertGreater(result["added"]["messages"], 0)
        self.assertEqual(result["added"]["commands"], 1)
        live = {f["value"] for f in facts_store.export_rows() if f["active"]}
        self.assertEqual(live, {"Likes strong coffee", "Lives in Hyderabad"})
        chat = conversation_store.export_all()[0]
        self.assertEqual((chat["title"], [m["role"] for m in chat["messages"]]), ("Trip planning", ["user", "assistant"]))
        history = [f for f in facts_store.export_rows() if not f["active"]][0]
        self.assertIsNotNone(history["superseded_by"])               # the link between a fact and its history survived

    def test_importing_the_same_file_twice_adds_nothing(self):
        _fill()
        data = backup.export_all()
        with _limit_of(-1):
            again = backup.import_all(data)
        self.assertEqual({k: v for k, v in again["added"].items() if k != "settings"}, {k: 0 for k in again["added"] if k != "settings"})
        self.assertGreater(sum(again["skipped"].values()), 0)
        self.assertEqual(_counts()["facts"], 3)

    def test_a_backup_from_a_pc_with_another_owner_name_lands_under_this_owner(self):
        _fill()
        data = backup.export_all()
        data["owner"] = "someone-else"
        for f in data["facts"]:
            f["speaker_id"] = "someone-else"
        _fresh_stores()
        with _limit_of(-1):
            backup.import_all(data)
        self.assertEqual({f["speaker_id"] for f in facts_store.export_rows()}, {backup._owner()})

    @unittest.skipIf(scheduler is None, "needs the Windows packages")
    def test_reminders_are_added_through_the_scheduler_and_survive_its_next_save(self):
        scheduler.add_schedule("reminder", "call mom", time_str="in 3 hours")
        data = backup.export_all()
        _fresh_stores()
        with _limit_of(-1):
            backup.import_all(data)
        scheduler._save()                                            # the running scheduler saves its own list later
        with open(scheduler.SCHEDULE_FILE, encoding="utf-8") as f:
            self.assertEqual([s["message"] for s in json.load(f)], ["call mom"])

    def test_older_backups_still_import(self):
        old = {"facts": [{"text": "Prefers dark mode", "category": "preference", "timestamp": "2026-09-01 10:00:00"}],
               "conversations": [{"user": "hello", "seven": "hi there", "timestamp": "2026-09-01 10:00:00"}]}
        with _limit_of(-1):
            result = backup.import_all(old)
        self.assertEqual((result["added"]["facts"], result["added"]["conversations"], result["added"]["messages"]), (1, 1, 2))
        self.assertEqual(facts_store.export_rows()[0]["speaker_id"], backup._owner())

    def test_a_file_that_is_not_a_backup_is_refused(self):
        for bad in ({"hello": "world"}, [1, 2], "text"):
            with self.assertRaises(ValueError):
                backup.import_all(bad)

    def test_restoring_triggers_cannot_pass_the_plan_limit(self):
        trigs = [{"name": f"T{i}", "action_type": "open_app", "action_data": {"app": "x"}, "voice_phrase": f"phrase {i}",
                  "enabled": True} for i in range(5)]
        with _limit_of(2):
            result = backup.import_all({"triggers": trigs})
        conn = backup._trigger_conn()
        total, active = conn.execute("SELECT COUNT(*), SUM(enabled) FROM triggers").fetchone()
        conn.close()
        self.assertEqual((total, active), (5, 2))                    # all kept, only two switched on
        self.assertIn("turned off", result["message"])


class ClearAllMemory(unittest.TestCase):
    def test_everything_is_cleared_and_nothing_is_left_behind(self):
        _fresh_stores()
        _fill()
        from backend.routes import memory as routes
        result = routes.clear_all_memory()
        self.assertTrue(result["success"], result)
        after = _counts()
        for k in ("facts", "chats", "messages", "goals"):
            self.assertEqual(after[k], 0, k)
        from memory.command_log import command_log
        self.assertEqual(command_log.get_stats()["total"], 0)
        self.assertEqual(after["tasks"], 1)                          # tasks, triggers and reminders are not memory

    def test_one_store_failing_does_not_stop_the_rest(self):
        _fresh_stores()
        _fill()
        from backend.routes import memory as routes
        with mock.patch.object(learning_store, "clear_all", side_effect=RuntimeError("locked")):
            result = routes.clear_all_memory()
        self.assertFalse(result["success"])
        self.assertEqual(result["failed"], ["learning"])
        self.assertEqual(_counts()["facts"], 0)                      # the others were still cleared


class TriggerPlanLimit(unittest.TestCase):
    def setUp(self):
        _fresh_stores()

    def _create(self, n, enabled=True):
        from backend.routes.triggers import TriggerCreate, create_trigger
        return create_trigger(TriggerCreate(name=f"T{n}", action_type="open_app", action_data={"app": "x"},
                                            voice_phrase=f"phrase {n}", enabled=enabled))

    def test_a_new_trigger_over_the_limit_is_refused(self):
        with _limit_of(2):
            self._create(1)
            self._create(2)
            with self.assertRaises(HTTPException) as e:
                self._create(3)
        self.assertEqual(e.exception.status_code, 403)
        self.assertEqual(e.exception.detail["error"], "plan_limit_reached")
        self.assertEqual(e.exception.detail["limit"], 2)
        self.assertEqual(_counts()["triggers"], 2)                   # nothing was created

    def test_a_trigger_created_off_is_allowed_and_enabling_it_is_refused(self):
        from backend.routes.triggers import TriggerUpdate, update_trigger
        with _limit_of(1):
            self._create(1)
            made = self._create(2, enabled=False)
            with self.assertRaises(HTTPException) as e:
                update_trigger(made["trigger"]["id"], TriggerUpdate(enabled=True))
        self.assertEqual(e.exception.status_code, 403)

    def test_no_limit_on_a_plan_without_one(self):
        with _limit_of(-1):
            for i in range(10):
                self._create(i)
        self.assertEqual(_counts()["triggers"], 10)


@unittest.skipIf(scheduler is None, "needs the Windows packages")
class ReminderAlert(unittest.TestCase):
    """The reminder card: Snooze works for a reminder only the daemon knows about, and brings back the reminder, not
    the sentence Seven spoke for it."""

    def setUp(self):
        _fresh_stores()
        from backend.routes import schedules
        self.routes = schedules
        schedules._schedule_alert_container[0] = {"active": False, "message": "", "type": "", "id": None}

    def test_snooze_uses_the_alert_file_and_the_original_reminder(self):
        import asyncio
        # as the reminder daemon writes it: only in the file, with the spoken sentence as the message
        self.routes._write_alert_file({"active": True, "message": "Hey Cheruku, quick nudge - call mom.",
                                       "original": "call mom", "overlay": True, "type": "reminder", "id": None})
        asyncio.run(self.routes.snooze_schedule_alert(minutes=10))
        self.assertEqual([s["message"] for s in scheduler.get_all_schedules()], ["call mom"])
        self.assertFalse(self.routes._read_alert_file()["active"])      # and the alert is cleared

    def test_the_alert_says_whether_the_windows_card_shows_it(self):
        import asyncio
        self.routes._write_alert_file({"active": True, "message": "m", "original": "m", "overlay": True, "type": "reminder", "id": 1})
        self.assertTrue(asyncio.run(self.routes.get_schedule_alert())["overlay"])
        asyncio.run(self.routes.dismiss_schedule_alert())
        self.assertFalse(asyncio.run(self.routes.get_schedule_alert())["active"])


if __name__ == "__main__":
    unittest.main()
