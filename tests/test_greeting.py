"""
Seven greets once per launch: a short welcome the first time after setup, then a greeting with the one most useful
thing (overdue, due today, next reminder, pending, or a clear day), never two greetings.
"""
import os
import tempfile
import time
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
        self.assertEqual([s for s in steps if s in ("card", "feedback", "about")], ["card", "feedback", "about"])
        self.assertEqual(steps[-1], "about")               # the card opens, shows Feedback while Seven explains, then About
        for step in ("nav-1", "nav-2", "nav-3", "nav-4", "nav-5", "search", "welcome-link"):
            self.assertIn(step, steps)                     # every link along the bottom gets its own moment
        self.assertLess(steps.index("mic"), steps.index("log"))
        self.assertLess(steps.index("log"), steps.index("bar"))      # the voice log, then the voice bar, then the pages
        self.assertLess(steps.index("bar"), steps.index("pages"))
        for word in ("voice log", "voice bar", "Right click"):
            self.assertIn(word, text)
        for word in ("feedback", "read", "Send feedback", "replay"):
            self.assertIn(word, text)
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

    def test_every_bottom_link_is_named_and_explained(self):
        text = " ".join(t for _, t in tour.script("Manikanta"))
        for label, what in (("Overview", "how Seven and your PC"), ("Chat", "type to me"), ("Tasks", "to-do list"),
                            ("Reminders", "alarms"), ("Memory", "remember about you"), ("Search", "Control K"),
                            ("Welcome guide", "tour")):
            self.assertIn(label, text)
            self.assertIn(what, text)

    def test_a_sentence_the_voice_splits_keeps_its_own_step(self):
        steps = tour.script("Manikanta")
        self.assertEqual(tour.step_for("Press Test mic and say anything, and I'll show you exactly what I heard.", steps), "mic")
        self.assertEqual(tour.step_for("Press Test mic and say anything,", steps), "mic")             # split at the comma
        self.assertEqual(tour.step_for("and I'll show you exactly what I heard.", steps), "mic")
        self.assertEqual(tour.step_for("Not sure I can hear you?", steps), "mic")
        self.assertEqual(tour.step_for("Search, or Control K,", steps), "search")
        self.assertEqual(tour.step_for("something unscripted", steps, fallback="listen"), "listen")   # nothing matches: stay put

    def test_the_screen_is_brightened_only_when_it_is_dim(self):
        class Sys:
            def __init__(self):
                self.calls = []

            def _brightness_set(self, n):
                self.calls.append(n)
                return True, "ok"

        def run(level):
            ctx = _Ctx()
            ctx.system_mod = Sys()
            with mock.patch.object(tour, "_screen_brightness", lambda: level):
                return tour.ensure_visible(ctx), ctx.system_mod.calls

        self.assertEqual(run(80), ("", []))
        self.assertEqual(run(60), ("", []))
        said, calls = run(25)
        self.assertEqual(calls, [60])
        self.assertIn("60 percent", said)
        self.assertEqual(run(None), ("", []))                              # a desktop monitor that cannot say: untouched
        ctx = _Ctx()
        ctx.system_mod = type("S", (), {"_brightness_set": lambda self, n: (False, "no")})()
        with mock.patch.object(tour, "_screen_brightness", lambda: 10):
            self.assertEqual(tour.ensure_visible(ctx), "")                 # it could not: it does not claim it did

    def test_opening_the_card_by_hand_has_seven_say_why_feedback_matters(self):
        said = []

        class Mouth:
            def speak(self, text):
                said.append(text)

        ctx = _Ctx()
        ctx.mouth = Mouth()
        tour.attach(ctx, _Cfg())
        try:
            self.assertTrue(tour.speak_welcome())
            for _ in range(100):
                if len(said) >= 4 and not tour._busy.locked():
                    break
                time.sleep(0.02)
        finally:
            tour.attach(None, None)
        spoken = " ".join(said)
        self.assertIn("feedback", spoken)
        self.assertIn("what we build next", spoken)
        self.assertFalse(tour.speak_welcome())                             # nothing attached: nothing to say

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
