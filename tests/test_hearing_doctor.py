"""
Seven tells you why it is not hearing you, inside the app: each situation a friend's PC can be in gives one clear problem with
what to do, a healthy one gives none, and what went wrong is written down with the numbers behind it.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from ears import doctor

NOW = 10_000.0


def stats(**over):
    mic = {"alive": True, "since_last_frame": 0.03, "frames": 5000, "device": "(Windows default)", "peak_db": -12.0, "avg_db": -35.0,
           "best_speech_score": 0.9, "start_threshold": 0.55, "sensitivity": "balanced", "utterances": 3, "too_short": 0,
           "problem": "", "notice": "", "last_error": ""}
    mic.update(over.pop("mic", {}))
    base = {"mode": "always", "push_to_talk_listener": True, "speaking_for_s": 0, "outcomes": {}, "mic_stats": mic}
    base.update(over)
    return base


def state(**over):
    base = {"ready": True, "listening": True, "voice_loop_beat": NOW - 1, "speech_model": {"state": "ready"}}
    base.update(over)
    return base


def ids(issues):
    return [i["id"] for i in issues]


class Assess(unittest.TestCase):
    def test_a_healthy_ear_has_no_problems(self):
        self.assertEqual(doctor.assess(stats(outcomes={"heard": 4, "no wake word": 1}), state(), NOW), [])

    def test_nothing_is_judged_while_seven_is_still_loading(self):
        self.assertEqual(doctor.assess(None, {"ready": False}, NOW), [])

    def test_a_failed_start_and_safe_mode_come_first_with_their_reason(self):
        got = doctor.assess(None, state(voice_problem="Seven's hearing failed to load (ImportError: DLL)"), NOW)
        self.assertEqual(got[0]["id"], "startup")
        self.assertIn("DLL", got[0]["detail"])
        got = doctor.assess(None, state(safe_mode={"reason": "ears failed"}), NOW)
        self.assertEqual(got[0]["id"], "safe_mode")

    def test_ears_that_never_loaded_are_reported(self):
        self.assertEqual(ids(doctor.assess(None, state(), NOW)), ["ears_missing"])

    def test_a_voice_loop_that_stopped_beating_is_stuck(self):
        got = doctor.assess(stats(), state(voice_loop_beat=NOW - 120), NOW)
        self.assertEqual((got[0]["id"], got[0]["level"]), ("loop_stuck", "error"))
        self.assertIn("120 s", got[0]["detail"])

    def test_a_long_answer_is_not_a_stuck_loop(self):
        # The loop does not pass while it is thinking and speaking: a minute-long answer is normal, and used to raise the alarm
        # at its end ("Seven stopped acting on what it hears").
        for busy in ({"thinking": True}, {"speaking": True}):
            self.assertEqual(doctor.assess(stats(), state(voice_loop_beat=NOW - 150, **busy), NOW), [], busy)
        self.assertEqual(doctor.assess(stats(), state(voice_loop_beat=NOW - 40), NOW), [])                 # idle, a short gap
        stuck = doctor.assess(stats(), state(voice_loop_beat=NOW - 700, speaking=True), NOW)
        self.assertEqual(stuck[0]["id"], "loop_stuck")                                                  # but not for ever

    def test_a_microphone_stream_that_died_is_an_error(self):
        got = doctor.assess(stats(mic={"alive": False, "last_error": "Invalid input device"}), state(), NOW)
        self.assertEqual(got[0]["id"], "mic_stream")
        self.assertIn("Invalid input device", got[0]["detail"])

    def test_a_silent_microphone_is_a_warning_with_the_windows_fix_not_an_alarm(self):
        got = doctor.assess(stats(mic={"problem": "The microphone has sent only silence for a minute"}), state(), NOW)
        self.assertEqual((got[0]["id"], got[0]["level"]), ("mic_silent", "warn"))
        self.assertIn("Audio enhancements", got[0]["fix"])
        quiet = doctor.assess(stats(mic={"peak_db": -90.0, "frames": 5000}), state(), NOW)
        self.assertEqual((quiet[0]["id"], quiet[0]["level"]), ("mic_quiet_now", "info"))   # a noise-gated array is silent until spoken to

    def test_a_switch_of_microphone_is_told(self):
        got = doctor.assess(stats(mic={"notice": "Seven's microphone was silent, so it switched to Headset (USB)."}), state(), NOW)
        self.assertIn("mic_switched", ids(got))

    def test_push_to_talk_is_named_and_a_dead_key_listener_is_worse(self):
        self.assertEqual(doctor.assess(stats(mode="ptt"), state(), NOW)[0]["level"], "warn")
        self.assertEqual(doctor.assess(stats(mode="ptt", push_to_talk_listener=False), state(), NOW)[0]["level"], "error")

    def test_seven_believing_it_is_talking_for_minutes_is_an_error(self):
        self.assertEqual(doctor.assess(stats(speaking_for_s=400), state(), NOW)[0]["id"], "speaking_stuck")

    def test_everything_ignored_gets_the_reason_that_matches(self):
        for outcomes, want in (({"no wake word": 9}, "wake_word"), ({"Seven's own voice": 8}, "own_voice"), ({"too short": 7}, "noise"),
                               ({"no clear speech": 6, "noise": 1}, "no_words")):
            self.assertEqual(ids(doctor.assess(stats(outcomes=outcomes), state(), NOW)), [want], outcomes)

    def test_a_few_ignored_sounds_or_any_heard_one_says_nothing(self):
        self.assertEqual(doctor.assess(stats(outcomes={"no wake word": 3}), state(), NOW), [])
        self.assertEqual(doctor.assess(stats(outcomes={"no wake word": 9, "heard": 1}), state(), NOW), [])

    def test_the_speech_model_still_downloading_is_a_note_not_a_failure(self):
        got = doctor.assess(stats(), state(speech_model={"state": "downloading", "progress": 40}), NOW)
        self.assertEqual((got[0]["id"], got[0]["level"]), ("speech_model", "info"))

    def test_problems_are_ordered_errors_first(self):
        got = doctor.assess(stats(mode="ptt", outcomes={"no wake word": 9}), state(voice_loop_beat=NOW - 999), NOW)
        self.assertEqual([i["level"] for i in got], sorted((i["level"] for i in got), key=doctor.ORDER.get))

    def test_the_live_numbers_for_the_meter(self):
        got = doctor.live(stats(), state(), NOW)
        self.assertEqual((got["peak_db"], got["start_threshold"], got["loop_age"], got["listening"]), (-12.0, 0.55, 1.0, True))


class Record(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        patcher = mock.patch.dict(os.environ, {"APPDATA": self.dir})
        patcher.start()
        self.addCleanup(patcher.stop)
        doctor._last.update(ids=None, at=0.0)

    def issues(self, *names, level="warn"):
        return [{"id": n, "level": level, "title": n.upper(), "detail": "", "fix": ""} for n in names]

    def lines(self):
        with open(doctor.log_path(), encoding="utf-8") as f:
            return [json.loads(x) for x in f]

    def test_a_change_is_written_with_the_numbers_behind_it(self):
        self.assertTrue(doctor.record(self.issues("wake_word"), stats(outcomes={"no wake word": 9}), NOW))
        got = self.lines()[0]
        self.assertEqual(got["problems"], ["wake_word"])
        self.assertEqual(got["mic"]["peak_db"], -12.0)
        self.assertEqual(got["outcomes"], {"no wake word": 9})

    def test_the_same_problem_is_not_written_again_and_getting_better_is(self):
        doctor.record(self.issues("ptt"), stats(), NOW)
        self.assertFalse(doctor.record(self.issues("ptt"), stats(), NOW + 60))
        self.assertTrue(doctor.record([], stats(), NOW + 120))
        self.assertEqual(self.lines()[-1]["problems"], ["none"])
        self.assertEqual(len(self.lines()), 2)

    def test_notes_alone_are_not_worth_a_line(self):
        self.assertFalse(doctor.record(self.issues("mic_switched", level="info"), stats(), NOW))

    def test_the_recent_log_is_what_the_report_shows(self):
        doctor.record(self.issues("ptt"), stats(), NOW)
        self.assertIn("ptt", doctor.recent_log(3)[0])


class Route(unittest.TestCase):
    def test_the_route_answers_with_issues_live_numbers_and_events(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend.routes import hearing
        except Exception:
            self.skipTest("needs fastapi")
        app = FastAPI()
        app.include_router(hearing.router)
        with mock.patch.dict(os.environ, {"APPDATA": tempfile.mkdtemp()}):
            body = TestClient(app).get("/api/hearing").json()
        self.assertEqual(set(body), {"issues", "live", "events", "log"})
        self.assertIsInstance(body["issues"], list)


if __name__ == "__main__":
    unittest.main()
