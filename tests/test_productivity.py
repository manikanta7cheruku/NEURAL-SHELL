"""Seven can read and act on tasks, schedules, triggers and workspaces by chat or voice."""
import unittest

from support import BrainTest
from brain_modules import productivity


class Fake(productivity.DataSource):
    def tasks(self):
        return [{"id": 1, "text": "Finish the report", "due_date": None},
                {"id": 2, "text": "Buy milk", "due_date": "2020-01-01"}]

    def schedules(self, speaker_id):
        return "You have 1 active item. Reminder at 5 PM. drink water"

    def triggers(self):
        return [{"id": 3, "name": "Focus mode", "hotkey": "ctrl+alt+f", "voice_phrase": "focus", "enabled": True},
                {"id": 4, "name": "Music", "enabled": False}]

    def workspaces(self):
        return [{"id": 7, "name": "Coding"}, {"id": 8, "name": "Study"}]


class Productivity(BrainTest):
    def setUp(self):
        super().setUp()
        productivity.set_source(Fake())
        self.addCleanup(productivity.set_source, None)

    def answered(self, q):
        reply = self.ask(q)
        self.assertEqual(self.trace()["answered_by"], "layer_036_productivity", q)
        return reply

    def test_lists_come_from_real_data(self):
        self.assertIn("2 pending tasks", self.answered("show my tasks"))          # used to run a file search
        self.assertIn("1 overdue task: Buy milk", self.answered("what's overdue"))
        self.assertIn("Reminder at 5 PM", self.answered("what are my reminders"))
        self.assertIn('Focus mode (ctrl+alt+f, say "focus")', self.answered("what triggers do i have"))
        self.assertIn("Coding and Study", self.answered("list my workspaces"))

    def test_create_task_with_due_date(self):
        reply = self.answered("add a task to call mom tomorrow")
        self.assertIn('Added "call mom" to your tasks, due tomorrow.', reply)
        self.assertIn("###TASK: action=create text=call|||mom", reply)
        self.assertIn('"buy eggs"', self.answered("add buy eggs to my list"))

    def test_fire_trigger_and_open_workspace_by_name(self):
        self.assertIn("###TRIGGER: action=fire id=3", self.answered("run my focus trigger"))
        self.assertIn("can't find a trigger called gaming", self.answered("run trigger gaming"))
        self.assertIn("###WORKSPACE: action=restore id=7", self.answered("open my coding workspace"))

    def test_other_requests_pass_through(self):
        for q in ("what is a task scheduler", "remind me to drink water at 5pm", "complete my report task", "open chrome"):
            with self.subTest(q=q):
                self.ask(q)
                self.assertNotEqual(self.trace()["answered_by"], "layer_036_productivity")


if __name__ == "__main__":
    unittest.main()
