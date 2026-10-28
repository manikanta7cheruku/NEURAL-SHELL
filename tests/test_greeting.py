"""
Seven greets once per launch: a short welcome the first time after setup, then a greeting with the one most useful
thing (overdue, due today, next reminder, pending, or a clear day), never two greetings.
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from main_modules.startup import greeting, tour


class _Cfg:
    def __init__(self, name="Manikanta", done=True):
        self.KEY = {"identity": {"user_name": name}, "setup_complete": done}


class _Sched:
    def __init__(self, items):
        self.items = items

    def get_all_schedules(self):
        return self.items


class _Ctx:
    def __init__(self, schedules=()):
        self.scheduler_mod = _Sched(list(schedules))


class Greeting(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        p = mock.patch.object(greeting, "_state_path", lambda: os.path.join(self.dir, "greeting.json"))
        p.start()
        self.addCleanup(p.stop)
        greeting._said = False
        self.addCleanup(setattr, greeting, "_said", False)
        b = mock.patch.object(greeting, "_battery", lambda: "")
        b.start()
        self.addCleanup(b.stop)

    def _tasks(self, overdue=(), today=(), pending=0):
        return mock.patch.multiple("backend.routes.tasks", db_get_overdue=lambda: list(overdue),
                                   db_get_due_today=lambda: list(today), db_get_stats=lambda: {"pending": pending})

    def test_first_launch_welcomes_and_teaches_the_wake_word(self):
        kind, text = greeting.message(_Ctx(), _Cfg())
        self.assertEqual(kind, "welcome")
        self.assertIn("Hey Seven", text)
        self.assertIn("Manikanta", text)

    def test_greets_only_once_per_launch(self):
        said = []
        with self._tasks():
            greeting.greet(_Ctx(), _Cfg(), speak=said.append)
            first = len(said)
            greeting.greet(_Ctx(), _Cfg(), speak=said.append)
        self.assertGreater(first, 0)
        self.assertEqual(len(said), first)                 # the second call said nothing

    def test_the_welcome_is_a_tour_of_the_home_screen_then_a_card(self):
        said, steps = [], []
        with self._tasks(), mock.patch.object(tour, "_step", steps.append):
            greeting.greet(_Ctx(), _Cfg(), speak=said.append)
        text = " ".join(said)
        self.assertIn("Hi Manikanta, I'm Seven.", text)
        for word in ("Hey Seven", "Test mic", "Control K"):
            self.assertIn(word, text)
        self.assertEqual([s for s in steps if s in ("intro", "listen", "mic", "pages")][:1], ["intro"])
        self.assertEqual(steps[-1], "card")                # the screen opens the welcome card at the end
        self.assertTrue(greeting.welcome_state()["tour_done"])

    def test_skipping_goes_straight_to_the_card(self):
        said, steps = [], []

        def speak(text):
            said.append(text)
            tour._skip.set()                               # the Skip button, pressed during the first sentence
        with self._tasks(), mock.patch.object(tour, "_step", steps.append):
            greeting.greet(_Ctx(), _Cfg(), speak=speak)
        self.assertEqual(len(said), 1)
        self.assertEqual(steps[-1], "card")

    def test_first_command_is_ticked_off_only_after_the_tour(self):
        greeting.mark_first_command()
        self.assertFalse(greeting.welcome_state()["first_command"])
        greeting.update_welcome(tour_done=True)
        greeting.mark_first_command()
        self.assertTrue(greeting.welcome_state()["first_command"])

    def test_volume_is_raised_only_when_it_is_low_or_muted(self):
        class Vol:
            def __init__(self, level, muted):
                self.level, self.muted = level, muted

            def GetMasterVolumeLevelScalar(self):
                return self.level / 100

            def GetMute(self):
                return self.muted

        class Sys:
            def __init__(self, vol):
                self.vol, self.calls = vol, []

            def _get_volume(self):
                return self.vol

            def _volume_set(self, n):
                self.calls.append(("set", n))

            def _volume_unmute(self):
                self.calls.append(("unmute",))

        def run(level, muted):
            ctx = _Ctx()
            ctx.system_mod = Sys(Vol(level, muted))
            return tour.ensure_audible(ctx), ctx.system_mod.calls

        self.assertEqual(run(70, False), ("", []))                       # fine: untouched
        self.assertEqual(run(41, False), ("", []))
        said, calls = run(15, False)
        self.assertEqual(calls, [("set", 60)])
        self.assertIn("60 percent", said)
        said, calls = run(80, True)                                      # muted but loud: only unmute, never lower
        self.assertEqual(calls, [("unmute",)])
        self.assertIn("unmuted", said)
        said, calls = run(10, True)
        self.assertEqual(calls, [("unmute",), ("set", 60)])
        self.assertEqual(tour.ensure_audible(_Ctx()), "")                # no audio control: nothing happens

    def test_after_the_welcome_it_is_a_daily_greeting(self):
        with self._tasks():
            greeting.greet(_Ctx(), _Cfg(), speak=lambda t: None)
            greeting._said = False
            kind, _ = greeting.message(_Ctx(), _Cfg())
        self.assertEqual(kind, "daily")

    def test_the_most_useful_thing_comes_first(self):
        greeting._save({"welcomed": True})
        morning = datetime.now().replace(hour=9, minute=0)
        with self._tasks(overdue=[{"text": "Submit the script"}], today=[{"text": "Call the bank"}]):
            text = greeting.message(_Ctx(), _Cfg(), morning)[1]
        self.assertTrue(text.startswith("Good morning, Manikanta."))
        self.assertIn("overdue: Submit the script", text)
        with self._tasks(today=[{"text": "Call the bank", "priority": "high"}]):
            self.assertIn("Today you have Call the bank", greeting.message(_Ctx(), _Cfg(), morning)[1])
        soon = (morning + timedelta(hours=6)).isoformat()
        with self._tasks(pending=2):
            text = greeting.message(_Ctx([{"status": "active", "time": soon, "message": "Gym"}]), _Cfg(), morning)[1]
        self.assertIn("next reminder is at 3 PM: Gym", text)
        with self._tasks():
            self.assertIn("clear day", greeting.message(_Ctx(), _Cfg(), morning)[1])

    def test_never_greets_before_setup_is_done(self):
        self.assertEqual(greeting.greet(_Ctx(), _Cfg(done=False), speak=lambda t: None), "")


if __name__ == "__main__":
    unittest.main()
