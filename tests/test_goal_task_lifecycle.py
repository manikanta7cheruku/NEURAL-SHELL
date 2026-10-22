"""
Goal + task lifecycle: "I finished X", "forget X", "complete my X task" must update the RIGHT record,
ask when two records fit, and never claim a change that did not happen.

Goals live in learning.db, tasks in the Dashboard's tasks database (faked here with FakeTaskStore, which has
the same interface as the real one). A ###TASK tag is only text: tests run it through the same shared
executor the console uses (lifecycle.execute_task_action) and then check the store itself.
"""
import os
import tempfile
import unittest

from support import ROOT, BrainTest, LLM_CALLS, learning_store
from brain_modules import action_receipts, lifecycle


def goal_titles(status="active"):
    return [g["title"] for g in learning_store.list_goals("default", status)]


class GoalOnly(BrainTest):
    def setUp(self):
        super().setUp()
        self.ask("I need to finish the report by Friday.")

    def test_goal_is_stored_and_not_a_task(self):
        self.assertEqual(len(goal_titles()), 1)
        self.assertEqual(brain_tasks(self).open_texts(), [])

    def test_report_marks_goal_done_and_verifies(self):
        r = self.ask("I finished the report")
        self.assertIn("marked", r)
        self.assertNotIn("###TASK", r)
        self.assertEqual(goal_titles("done").__len__(), 1)
        self.assertEqual(goal_titles(), [])
        self.assertIn("haven't told me about any goals", self.ask("what are my goals"))

    def test_other_phrasings_reach_the_same_goal(self):
        for phrase in ("I'm done with the report", "the report is done", "I wrapped up the report",
                       "mark the report as done", "check off the report", "I have finally completed the report"):
            with self.subTest(phrase=phrase):
                setUp_again(self)
                r = self.ask(phrase)
                self.assertIn("marked", r, phrase)
                self.assertEqual(goal_titles(), [], phrase)

    def test_drop_phrasings(self):
        for phrase in ("forget the report", "drop my report goal", "I gave up on the report", "scrap the report"):
            with self.subTest(phrase=phrase):
                setUp_again(self)
                r = self.ask(phrase)
                self.assertIn("dropped", r, phrase)
                self.assertEqual(goal_titles("dropped").__len__(), 1, phrase)

    def test_goals_remaining_are_still_listed(self):
        self.ask("I want to learn Rust")
        self.ask("I finished the report")
        self.assertIn("Rust", self.ask("what are my goals"))

    def test_failed_goal_write_is_not_reported_as_success(self):
        original = learning_store.get_goal
        learning_store.get_goal = lambda _id: {"status": "active"}       # the write did not stick
        try:
            r = self.ask("I finished the report")
        finally:
            learning_store.get_goal = original
        self.assertNotIn("marked", r)
        self.assertIn("couldn't save", r)


class TaskOnly(BrainTest):
    def setUp(self):
        super().setUp()
        self.store = self.tasks("Finish the report")

    def test_finishing_a_task_updates_the_task(self):
        r = self.ask("I finished the report")
        self.assertIn("###TASK: action=complete", r)
        self.assertIn("id=1", r)
        self.assertNotIn("Got it", r)
        self.assertEqual(self.store.open_texts(), ["Finish the report"])      # a tag alone changes nothing
        self.assertEqual(self.run_tags(r, self.store), ["Finish the report"])
        self.assertEqual(self.store.open_texts(), [])

    def test_explicit_command_forms(self):
        for phrase in ("complete my report task", "mark the report task as done", "check off the report task",
                       "finish the report task"):
            with self.subTest(phrase=phrase):
                self.store = self.tasks("Finish the report")
                r = self.ask(phrase)
                self.assertIn("action=complete", r, phrase)
                self.run_tags(r, self.store)
                self.assertEqual(self.store.open_texts(), [], phrase)

    def test_delete_task(self):
        r = self.ask("delete my report task")
        self.assertIn("action=delete", r)
        self.run_tags(r, self.store)
        self.assertEqual(self.store.rows, {})

    def test_unknown_task_is_reported_not_claimed(self):
        r = self.ask("complete my banana task")
        self.assertNotIn("###TASK", r)
        self.assertIn("couldn't find", r)

    def test_legacy_trigger_without_a_reference_asks_which(self):
        r = self.ask("mark it done")
        self.assertNotIn("###TASK", r)
        self.assertIn("Which task", r)
        self.assertIn("Finish the report", r)

    def test_plain_statement_with_nothing_to_update_is_not_a_command(self):
        r = self.ask("I finished my morning run")
        self.assertNotIn("###TASK", r)
        self.assertNotIn("Got it", r)
        self.assertTrue(LLM_CALLS, "an ordinary statement should reach the model")


class GoalAndTaskBoth(BrainTest):
    def setUp(self):
        super().setUp()
        self.ask("I need to finish the report by Friday.")           # goal
        self.store = self.tasks("Finish the report")                  # and a task with the same name

    def test_ambiguous_reference_asks_and_changes_nothing(self):
        r = self.ask("I finished the report")
        self.assertIn("both a goal", r)
        self.assertNotIn("marked", r)
        self.assertNotIn("###TASK", r)
        self.assertEqual(len(goal_titles()), 1)
        self.assertEqual(self.store.open_texts(), ["Finish the report"])

    def test_answer_task(self):
        self.ask("I finished the report")
        r = self.ask("the task")
        self.assertIn("action=complete", r)
        self.run_tags(r, self.store)
        self.assertEqual(self.store.open_texts(), [])
        self.assertEqual(len(goal_titles()), 1)                       # the goal is untouched

    def test_answer_goal(self):
        self.ask("I finished the report")
        r = self.ask("the goal")
        self.assertIn("marked", r)
        self.assertNotIn("###TASK", r)
        self.assertEqual(goal_titles(), [])
        self.assertEqual(self.store.open_texts(), ["Finish the report"])

    def test_answer_both(self):
        self.ask("I finished the report")
        r = self.ask("both")
        self.assertIn("marked", r)
        self.assertIn("action=complete", r)
        self.run_tags(r, self.store)
        self.assertEqual(goal_titles(), [])
        self.assertEqual(self.store.open_texts(), [])

    def test_answer_neither(self):
        self.ask("I finished the report")
        self.assertIn("leave them", self.ask("neither"))
        self.assertEqual(len(goal_titles()), 1)
        self.assertEqual(self.store.open_texts(), ["Finish the report"])

    def test_explicit_task_wording_beats_ambiguity(self):
        r = self.ask("complete my report task")
        self.assertIn("action=complete", r)
        self.assertNotIn("both", r)
        self.run_tags(r, self.store)
        self.assertEqual(self.store.open_texts(), [])
        self.assertEqual(len(goal_titles()), 1)                       # explicit command preserved, goal remains

    def test_explicit_goal_wording_beats_ambiguity(self):
        r = self.ask("mark my report goal as done")
        self.assertIn("marked", r)
        self.assertEqual(goal_titles(), [])
        self.assertEqual(self.store.open_texts(), ["Finish the report"])


class AmbiguityWithinTasks(BrainTest):
    def test_two_tasks_match_then_user_picks(self):
        store = self.tasks("Report draft", "Report slides", "Buy milk")
        r = self.ask("I finished the report")
        self.assertIn("Which one", r)
        self.assertNotIn("###TASK", r)
        r = self.ask("the slides")
        self.assertIn("action=complete", r)
        self.run_tags(r, store)
        self.assertEqual(sorted(store.open_texts()), ["Buy milk", "Report draft"])

    def test_most_specific_match_wins_without_asking(self):
        store = self.tasks("Report draft", "Report slides")
        r = self.ask("complete my report slides task")
        self.assertIn("action=complete", r)
        self.run_tags(r, store)
        self.assertEqual(store.open_texts(), ["Report draft"])


class NotAReport(BrainTest):
    def setUp(self):
        super().setUp()
        self.ask("I need to finish the report by Friday.")
        self.tasks("Finish the report")

    def test_questions_negations_and_plans_do_not_complete_anything(self):
        for phrase in ("did I finish the report?", "I haven't finished the report", "I want to finish the report",
                       "when I finish the report I will rest", "I will finish the report tomorrow"):
            with self.subTest(phrase=phrase):
                r = self.ask(phrase)
                self.assertNotIn("marked", r, phrase)
                self.assertNotIn("action=complete", r, phrase)
        self.assertEqual(len(goal_titles()), 1)


class HonestExecution(unittest.TestCase):
    def test_missing_or_stale_task_raises_and_receipt_is_failed(self):
        from support import FakeTaskStore
        store = FakeTaskStore("Finish the report")
        fn = lambda: lifecycle.execute_task_action({"action": "complete", "id": "99", "search": "report"}, store)
        receipt = action_receipts.run_action("TASK", "complete", fn)
        self.assertEqual(receipt.status, "failed")
        self.assertEqual(store.open_texts(), ["Finish the report"])         # no fuzzy fallback past a stale id
        self.assertIn("didn't work", action_receipts.reconcile_reply("Marking it done.", [receipt]))

    def test_update_that_does_not_stick_is_a_failure(self):
        from support import FakeTaskStore

        class Broken(FakeTaskStore):
            def complete(self, task_id):
                pass
        store = Broken("Finish the report")
        with self.assertRaises(RuntimeError):
            lifecycle.execute_task_action({"action": "complete", "id": "1"}, store)

    def test_search_without_match_raises(self):
        from support import FakeTaskStore
        with self.assertRaises(LookupError):
            lifecycle.execute_task_action({"action": "complete", "search": "nothing|||here"}, FakeTaskStore("Buy milk"))


class RealSqliteStore(BrainTest):
    """
    The real SQLite code path (backend/routes/tasks.py + SqliteTaskStore) against a fresh temporary
    database per test. Runs only where the backend's dependencies (fastapi) are installed.
    Never touches the user's seven_data/tasks.db.
    """

    def setUp(self):
        super().setUp()
        try:
            from backend.routes import tasks as T
        except Exception:
            self.skipTest("backend.routes.tasks needs fastapi")
        self.T = T
        path = os.path.join(tempfile.mkdtemp(prefix="seven_tasks_"), "tasks.db")
        self.addCleanup(T.set_db_path, T.set_db_path(path))
        T.init_db()
        brain_deps = __import__("brain").EXTRA_DEPS
        brain_deps.pop("tasks", None)                  # the brain resolves against the real store
        self.store = lifecycle.SqliteTaskStore()

    def add(self, text):
        with self.T._get_conn() as conn:
            cur = conn.execute("INSERT INTO tasks (text, priority, completed, created_at, subtasks) "
                               "VALUES (?, 'medium', 0, '2026-01-01', '[]')", (text,))
            conn.commit()
            return cur.lastrowid

    def row(self, task_id):
        return self.store.get(task_id)

    def test_tests_never_use_the_users_tasks_database(self):
        real = os.path.join(ROOT, "seven_data", "tasks.db")
        self.assertNotEqual(os.path.abspath(self.T.TASKS_DB), os.path.abspath(real))
        self.assertTrue(self.T.TASKS_DB.startswith(tempfile.gettempdir()))

    def test_complete_against_the_sqlite_tasks_database(self):
        other = self.add("Complete the task panel")
        target = self.add("Finish the report")
        r = self.ask("I finished the report")
        self.assertIn("action=complete", r)
        self.assertEqual(self.run_tags(r, self.store), ["Finish the report"])
        self.assertEqual(self.row(target)["completed"], True)
        self.assertEqual(self.store.pending(), [{"id": other, "text": "Complete the task panel"}])

    def test_delete_against_the_sqlite_tasks_database(self):
        other = self.add("Complete the task panel")
        target = self.add("Finish the report")
        r = self.ask("delete my report task")
        self.assertIn("action=delete", r)
        self.assertEqual(self.run_tags(r, self.store), ["Finish the report"])
        self.assertIsNone(self.row(target))
        self.assertEqual(self.store.pending(), [{"id": other, "text": "Complete the task panel"}])


def brain_tasks(case):
    import brain
    return brain.EXTRA_DEPS["tasks"]


def setUp_again(case):
    """Fresh goal for each sub-phrasing."""
    for g in learning_store.list_goals("default", None):
        learning_store.set_goal_status(g["id"], "dropped")
    learning_store.upsert_goal("default", "finish the report", "finish the report")


if __name__ == "__main__":
    unittest.main()
