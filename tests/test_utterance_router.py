"""
Every utterance Seven hears ends in a named decision. These are the situations where the old inline code threw the person's
words away without saying so, or did something they never asked for.
"""
import unittest

import support  # noqa: F401  (sets up paths and test mode)
from main_modules.startup.utterance_router import control_match, decide

WAKE_CTL = ["seven", "hey seven", "wake up", "continue", "start listening"]
PAUSE_CTL = ["not you", "hold on", "wait", "stop listening"]
KILL_CTL = ["go to sleep", "goodbye", "shutdown", "close seven"]


def route(text, **over):
    args = dict(mode="always", wake_words=["hey seven", "seven"], active=True, follow_up_open=False, pending=False, interrupted=False,
                speaking=False, wake_ctl=WAKE_CTL, pause_ctl=PAUSE_CTL, kill_ctl=KILL_CTL)
    args.update(over)
    return decide(text, **args)


class ControlWords(unittest.TestCase):
    def test_a_control_phrase_is_the_whole_thing_said_not_a_word_inside_a_sentence(self):
        self.assertTrue(control_match("Wait.", PAUSE_CTL))
        self.assertTrue(control_match("stop listening please", PAUSE_CTL))
        self.assertTrue(control_match("Hold on a second", PAUSE_CTL))
        self.assertFalse(control_match("wait what's the weather", PAUSE_CTL))        # used to pause Seven
        self.assertFalse(control_match("hold on let me check the calendar for tomorrow", PAUSE_CTL))
        self.assertFalse(control_match("stop the music", PAUSE_CTL))

    def test_saying_goodbye_to_someone_else_does_not_close_seven(self):
        self.assertFalse(control_match("goodbye", KILL_CTL, address_required=("goodbye", "shutdown")))
        self.assertTrue(control_match("goodbye seven", KILL_CTL, address_required=("goodbye", "shutdown")))
        self.assertTrue(control_match("go to sleep", KILL_CTL, address_required=("goodbye", "shutdown")))
        self.assertTrue(control_match("close seven", KILL_CTL, address_required=("goodbye", "shutdown")))

    def test_the_name_alone_wakes_it(self):
        self.assertTrue(control_match("Hey Seven", WAKE_CTL))
        self.assertTrue(control_match("wake up", WAKE_CTL))
        self.assertFalse(control_match("seven things I need to buy", WAKE_CTL))


class Decisions(unittest.TestCase):
    def test_a_normal_request_is_acted_on(self):
        d = route("What time is it")
        self.assertEqual((d.action, d.text), ("process", "What time is it"))

    def test_wait_alone_pauses_but_a_sentence_with_wait_is_a_request(self):
        self.assertEqual(route("wait").action, "pause")
        self.assertEqual(route("wait, what's the weather").action, "process")

    def test_goodbye_alone_is_just_a_sentence_and_goodbye_seven_closes_it(self):
        self.assertEqual(route("goodbye").action, "process")
        self.assertEqual(route("goodbye seven").action, "kill")

    def test_in_standby_the_name_wakes_it_and_anything_else_says_why_it_was_ignored(self):
        self.assertEqual(route("seven", active=False).action, "resume")
        d = route("open chrome", active=False)
        self.assertEqual(d.action, "drop")
        self.assertIn("standby", d.reason)

    def test_thanks_is_noise_on_its_own_but_an_answer_to_seven(self):
        self.assertEqual(route("thank you").action, "drop")
        self.assertEqual(route("Thanks!", follow_up_open=True).action, "process")
        self.assertEqual(route("okay", follow_up_open=True).action, "process")
        self.assertEqual(route("thank you", pending=True).action, "process")
        self.assertEqual(route("you", follow_up_open=True).action, "drop")                 # never a request

    def test_the_next_thing_said_after_interrupting_seven_is_not_swallowed(self):
        d = route("what's the weather tomorrow", interrupted=True)
        self.assertEqual((d.action, d.text), ("process", "what's the weather tomorrow"))   # it used to vanish
        self.assertEqual(route("continue", interrupted=True).action, "resume_interrupted")
        self.assertEqual(route("go ahead", interrupted=True).action, "resume_interrupted")

    def test_something_said_while_seven_is_talking_waits_instead_of_vanishing(self):
        self.assertEqual(route("remind me to call mom at five", speaking=True).action, "wait_speaking")

    def test_the_wake_word_mode(self):
        wake = dict(mode="wake")
        d = route("open chrome", **wake)
        self.assertEqual((d.action, d.reason), ("drop", "no wake word"))
        self.assertEqual(route("open chrome", follow_up_open=True, **wake).action, "process")       # just after Seven spoke
        self.assertEqual(route("Hey Seven", **wake).action, "wake_only")
        d = route("Hey Seven, open chrome", **wake)
        self.assertEqual((d.action, d.text, d.wake_found), ("process", "open chrome", True))

    def test_the_wake_word_does_not_apply_while_in_standby_so_the_name_can_wake_it(self):
        self.assertEqual(route("Hey Seven", mode="wake", active=False).action, "resume")

    def test_every_drop_has_a_reason_for_the_voice_log(self):
        for text, over in (("you", {}), ("open chrome", {"mode": "wake"}), ("open chrome", {"active": False}), ("thanks", {})):
            d = route(text, **over)
            self.assertEqual(d.action, "drop", (text, over))
            self.assertTrue(d.reason, (text, over))


if __name__ == "__main__":
    unittest.main()
