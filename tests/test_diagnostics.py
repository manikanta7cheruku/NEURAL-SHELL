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


if __name__ == "__main__":
    unittest.main()
