"""
When Seven does not listen on a friend's PC we need to know why without being there: safe mode must not trap a PC after a
single failed start, the app must say what is wrong, the test mic must explain a refusal, and one report must collect it all.
"""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from main_modules.startup import safe_mode


class SafeMode(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "safe_mode.flag")

    def test_one_failed_start_is_only_noted_the_next_start_tries_again(self):
        safe_mode.record_failure(self.path, "ears failed", "1.3.2")
        self.assertFalse(safe_mode.should_enter(self.path, "1.3.2"))

    def test_three_failed_starts_in_a_row_enter_safe_mode_with_the_reason(self):
        for _ in range(safe_mode.MAX_FAILS):
            safe_mode.record_failure(self.path, "no microphone driver", "1.3.2")
        self.assertTrue(safe_mode.should_enter(self.path, "1.3.2"))
        self.assertEqual(safe_mode.state(self.path, "1.3.2")["reason"], "no microphone driver")

    def test_an_update_forgets_old_failures(self):
        for _ in range(safe_mode.MAX_FAILS):
            safe_mode.record_failure(self.path, "x", "1.3.2")
        self.assertFalse(safe_mode.should_enter(self.path, "1.3.3"))

    def test_the_old_bare_timestamp_flag_counts_once_and_no_longer_traps_the_pc(self):
        with open(self.path, "w") as f:
            f.write("1762000000.5")
        self.assertFalse(safe_mode.should_enter(self.path, "1.3.2"))
        self.assertEqual(safe_mode.state(self.path)["fails"], 1)

    def test_a_good_start_clears_it_and_retry_restarts(self):
        safe_mode.record_failure(self.path, "x")
        safe_mode.clear(self.path)
        self.assertEqual(safe_mode.state(self.path), {})
        called = []
        safe_mode.record_failure(self.path, "x")
        safe_mode.retry(self.path, restart=lambda: called.append(1))
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(called, [1])


class Attention(unittest.TestCase):
    def collect(self, **probes):
        from backend.routes import attention
        base = dict(mic_error=lambda: "", voice=lambda: {"ready": True, "status": "", "progress": 0},
                    ollama_up=lambda: True, uptime=lambda: 999, setup_done=lambda: True,
                    speech=lambda: {"state": "ready"}, problem=lambda: {"problem": "", "safe_mode": ""},
                    mic_blocked=lambda: False)
        base.update(probes)
        return attention.collect(**base)

    def test_all_well_says_nothing(self):
        self.assertEqual(self.collect(), [])

    def test_a_start_that_failed_says_why(self):
        items = self.collect(problem=lambda: {"problem": "Seven's hearing failed to load (ImportError: DLL)", "safe_mode": ""})
        self.assertEqual(items[0]["id"], "hearing-failed")
        self.assertIn("DLL", items[0]["message"])

    def test_safe_mode_has_a_retry_button(self):
        items = self.collect(problem=lambda: {"problem": "", "safe_mode": "ears failed"})
        self.assertEqual(items[0]["id"], "safe-mode")
        self.assertEqual(items[0]["action"]["retry"], "safe-mode")

    def test_the_home_screen_shows_only_what_is_broken_and_only_its_title(self):
        issue = lambda id_, level="warn": {"id": id_, "level": level, "title": id_.replace("_", " ").title(), "detail": "d", "fix": "A long fix"}
        shown = self.collect(hearing=lambda: [issue("no_words"), issue("wake_word"), issue("noise"), issue("own_voice"),
                                              issue("loop_stuck", "error")])
        self.assertEqual([i["id"] for i in shown], ["hearing-loop_stuck"])           # ignored sounds belong in Settings, Hearing
        self.assertEqual(shown[0]["message"], "Loop Stuck.")                            # the title, not a paragraph under the header

    def test_windows_blocking_the_microphone_is_named(self):
        items = self.collect(mic_blocked=lambda: True)
        self.assertEqual(items[0]["id"], "mic-blocked")
        self.assertIn("Privacy", items[0]["message"])


class TestMic(unittest.TestCase):
    def setUp(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend.routes import voice
        except Exception:
            self.skipTest("needs fastapi")
        app = FastAPI()
        app.include_router(voice.router)
        self.client = TestClient(app)

    def fake_ears(self, listening=True, speech=None, result=None):
        ears = types.SimpleNamespace(listening=lambda: listening, start=lambda: None,
                                     models_status=lambda: speech or {"state": "ready"},
                                     hearing_test=lambda: result)
        return mock.patch.dict(sys.modules, {"ears.core": ears})

    def test_hearing_not_loaded_says_so_and_points_to_diagnostics(self):
        with mock.patch.dict(sys.modules):
            sys.modules.pop("ears.core", None)
            r = self.client.post("/api/voice/test")
        self.assertEqual(r.status_code, 409)
        self.assertIn("Diagnostics", r.json()["detail"])

    def test_a_microphone_that_cannot_open_says_what_to_check(self):
        stream = types.SimpleNamespace(STREAM=types.SimpleNamespace(last_error="Invalid input device"))
        with self.fake_ears(listening=False), mock.patch.dict(sys.modules, {"ears.stream": stream}):
            r = self.client.post("/api/voice/test")
        self.assertEqual(r.status_code, 409)
        self.assertIn("Invalid input device", r.json()["detail"])
        self.assertIn("Privacy", r.json()["detail"])

    def test_a_speech_model_still_downloading_says_so(self):
        with self.fake_ears(speech={"state": "downloading", "progress": 40}):
            r = self.client.post("/api/voice/test")
        self.assertEqual(r.status_code, 409)
        self.assertIn("40%", r.json()["detail"])

    def test_when_all_is_well_it_returns_what_was_heard(self):
        with self.fake_ears(result={"heard": "open chrome", "ignored": "", "raw": "open chrome"}):
            self.assertEqual(self.client.post("/api/voice/test").json()["heard"], "open chrome")


class Report(unittest.TestCase):
    def test_one_failing_section_never_hides_the_rest(self):
        from backend import diagnostics

        def broken():
            raise RuntimeError("boom")

        sections = [("Broken", broken), ("Fine", lambda: [diagnostics._c("thing", diagnostics.OK, "works")]),
                    ("Bad", lambda: [diagnostics._c("mic", diagnostics.FAIL, "no microphone")])]
        with mock.patch.object(diagnostics, "SECTIONS", sections), mock.patch.object(diagnostics, "SLOW", set()):
            report = diagnostics.collect()
        text = diagnostics.render(report)
        self.assertEqual(report["problems"], 1)
        self.assertEqual(report["warnings"], 1)                      # the broken section became a warning line
        self.assertIn("READ THESE FIRST", text)
        self.assertLess(text.index("no microphone"), text.index("== Broken =="))   # problems come before the detail
        self.assertIn("works", text)

    def test_the_log_shows_warnings_once_with_a_count_and_leaves_out_the_usual_noise(self):
        from backend import diagnostics
        path = os.path.join(tempfile.mkdtemp(), "seven.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(os.linesep.join([
                "2026-11-02 10:00:01 [INFO    ] seven.events: response_latency",
                "2026-11-02 10:00:02 [WARNING ] phonemizer: words count mismatch on 100.0% of the lines (1/1)",
                "2026-11-02 10:00:03 [ERROR   ] mouth: voice failed to load",
                "2026-11-02 10:00:04 [ERROR   ] mouth: voice failed to load",
                "2026-11-02 10:00:05 [ERROR   ] mouth: voice failed to load"]))
        text = diagnostics._useful(path, 10)
        self.assertEqual(text.count("voice failed to load"), 1)
        self.assertIn("(x3)", text)
        self.assertNotIn("phonemizer", text)
        self.assertNotIn("response_latency", text)

    def test_the_windows_user_name_is_not_in_the_report(self):
        from backend import diagnostics
        report = {"at": "now", "problems": 0, "warnings": 0, "sections": [
            {"title": "Data", "checks": [diagnostics._c("folder", diagnostics.INFO, r"C:\Users\Asha Rao\AppData\SEVEN")]}]}
        with mock.patch.dict(os.environ, {"USERNAME": "Asha Rao"}):
            self.assertNotIn("Asha", diagnostics.render(report))

    def test_the_report_has_a_route_and_the_hotkey_route_answers(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend import diagnostics
            from backend.routes import config_routes, diagnostics as routes
        except Exception:
            self.skipTest("needs fastapi")
        app = FastAPI()
        app.include_router(routes.router)
        app.include_router(config_routes.router)
        client = TestClient(app)
        with mock.patch.object(diagnostics, "SECTIONS", [("Fine", lambda: [diagnostics._c("a", diagnostics.OK, "b")])]), \
                mock.patch.object(diagnostics, "SLOW", set()):
            r = client.get("/api/diagnostics/report")
        self.assertEqual(r.status_code, 200)
        self.assertIn("SEVEN DIAGNOSTICS", r.text)
        self.assertEqual(client.get("/api/panel/get-hotkey").status_code, 200)    # the Settings page asks this path


class Hearing(unittest.TestCase):
    """A PC where Seven is "listening", the microphone is open, and nothing is acted on: the report must say which of the
    several reasons it is."""

    def stats(self, **over):
        mic = {"alive": True, "since_last_frame": 0.03, "frames": 5000, "device": "(Windows default)", "peak_db": -12.0,
               "avg_db": -35.0, "best_speech_score": 0.9, "start_threshold": 0.55, "sensitivity": "balanced",
               "utterances": 4, "too_short": 1}
        base = {"mode": "always", "mic": "", "push_to_talk_listener": True, "speaking_for_s": 0, "outcomes": {}, "mic_stats": mic,
                "sensitivity": "balanced", "wake_words": [], "model_state": {}}
        mic.update(over.pop("mic", {}))
        base.update(over)
        return base

    def run_section(self, stats, live="always"):
        from backend import diagnostics
        ears = types.SimpleNamespace(hearing_stats=lambda: stats)
        with mock.patch.dict(sys.modules, {"ears.core": ears}), mock.patch.object(diagnostics, "_state", lambda: {"listen_mode": live}):
            return {c["name"]: c for c in diagnostics.hearing_section()}

    def test_a_silent_microphone_is_called_silent(self):
        got = self.run_section(self.stats(mic={"peak_db": -90.0, "avg_db": -95.0, "best_speech_score": 0.0}))
        self.assertEqual(got["Microphone level (last 10 s)"]["status"], "fail")
        self.assertIn("SILENT", got["Microphone level (last 10 s)"]["detail"])

    def test_a_very_quiet_microphone_is_a_warning_with_the_fix(self):
        got = self.run_section(self.stats(mic={"peak_db": -48.0, "avg_db": -60.0, "best_speech_score": 0.03}))
        self.assertEqual(got["Microphone level (last 10 s)"]["status"], "warn")
        self.assertIn("Sound settings", got["Microphone level (last 10 s)"]["detail"])

    def test_push_to_talk_without_its_key_listener_is_the_reason_nothing_is_heard(self):
        got = self.run_section(self.stats(mode="ptt", push_to_talk_listener=False), live="ptt")
        self.assertEqual(got["Push to talk"]["status"], "fail")
        self.assertIn("NOT running", got["Push to talk"]["detail"])

    def test_a_screen_that_disagrees_with_the_ears_means_the_voice_loop_is_stuck(self):
        got = self.run_section(self.stats(mode="always"), live="ptt")
        self.assertEqual(got["Mode on screen"]["status"], "warn")

    def test_everything_ignored_because_of_the_wake_word_says_so(self):
        got = self.run_section(self.stats(mode="wake", outcomes={"no wake word": 9, "too short": 1}))
        key = next(k for k in got if k.startswith("Last "))
        self.assertEqual(got[key]["status"], "warn")
        self.assertIn("Always on", got["Most likely reason"]["detail"])

    def test_a_seven_that_thinks_it_has_been_talking_for_minutes_is_flagged(self):
        got = self.run_section(self.stats(speaking_for_s=400, outcomes={"Seven's own voice": 12}))
        self.assertEqual(got["Seven speaking for"]["status"], "fail")
        self.assertIn("own voice", got["Most likely reason"]["detail"])

    def test_a_healthy_hearing_has_no_warnings(self):
        got = self.run_section(self.stats(outcomes={"heard": 6, "no wake word": 1}))
        self.assertFalse([c for c in got.values() if c["status"] in ("warn", "fail")])

    def test_thinking_is_not_reported_as_not_listening(self):
        from backend import diagnostics
        with mock.patch.object(diagnostics, "_state", lambda: {"ready": True, "listening": False, "thinking": True}):
            got = {c["name"]: c for c in diagnostics.state_section()}
        self.assertEqual(got["Listening"]["status"], "info")


class Logs(unittest.TestCase):
    NOW = __import__("datetime").datetime(2026, 11, 3, 22, 0, 0)

    def write(self, name, text):
        path = os.path.join(tempfile.mkdtemp(), name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_a_multi_line_info_message_is_not_a_warning(self):
        from backend import diagnostics
        path = self.write("seven.log", "\n".join([
            "2026-11-03 21:00:00 [INFO    ] dns.resolver: answer for grokipedia.com",
            "; answers 2", "grokipedia.com. 300 IN A 104.18.19.2", "; authorities 0",
            "2026-11-03 21:00:05 [WARNING ] mouth: the voice engine restarted"]))
        text = diagnostics._useful(path, 20, now=self.NOW)
        self.assertIn("the voice engine restarted", text)
        self.assertNotIn("grokipedia", text)

    def test_a_traceback_stays_with_its_error_and_old_entries_are_dropped(self):
        from backend import diagnostics
        path = self.write("python_crash.log", "\n".join([
            "[2026-09-05T20:00:39.459Z] [ERROR] old: this was a long time ago", "Traceback (most recent call last):", "TypeError: old",
            "[2026-11-03T20:00:39.459Z] [ERROR] new: the voice failed", "Traceback (most recent call last):", "TypeError: new"]))
        text = diagnostics._useful(path, 20, now=self.NOW)
        self.assertIn("TypeError: new", text)
        self.assertNotIn("old", text)

    def test_a_native_crash_says_when_and_shows_the_crashing_thread_only(self):
        from backend import diagnostics
        base = tempfile.mkdtemp()
        with open(os.path.join(base, "native_crash.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(["--- Seven started 2026-10-01 10:00:00 (pid 1) ---", "Windows fatal exception: access violation", "",
                                "--- Seven started 2026-11-03 20:00:00 (pid 2) ---", "Windows fatal exception: access violation", "",
                                "Current thread 0x00001234 (most recent call first):", '  File "ctranslate2", line 1 in transcribe',
                                "--- Seven started 2026-11-03 21:00:00 (pid 3) ---"]))
        with open(os.path.join(base, "python_crash.log"), "w", encoding="utf-8") as f:
            f.write("[2026-11-03T20:00:40.000Z] EXIT code=3221225477 signal=null crashCount=0\n")
        with mock.patch.object(diagnostics, "_recent", lambda line, now=None: "2026-11-03" in line):
            crashes, exits = diagnostics._crashes(base)
        self.assertEqual(len(crashes), 1)                                      # the October one is too old
        self.assertIn("2026-11-03 20:00:00", crashes[0])
        self.assertIn("transcribe", crashes[0])
        self.assertIn("access violation", exits[0])


if __name__ == "__main__":
    unittest.main()
