"""
Starting Seven never waits on a download. The setup wizard fetches the speech model with progress (so it is on the
PC before Seven first starts), and if it is ever missing the app opens anyway and says what is happening.
"""
import os
import time
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from backend import bootstrap
from backend.routes.attention import collect


def fake_whisper(**kw):
    """A stand-in for faster_whisper.download_model: CI does not install the speech package (it is large)."""
    import contextlib
    import sys
    import types

    @contextlib.contextmanager
    def _patched():
        download = mock.Mock(**kw)
        with mock.patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(download_model=download)}):
            yield download
    return _patched()


def _probes(**kw):
    p = dict(mic_error=lambda: "", voice=lambda: {"ready": True, "status": "done", "progress": 100},
             ollama_up=lambda: True, uptime=lambda: 600, setup_done=lambda: True, speech=lambda: {"state": "ready", "progress": 100})
    p.update(kw)
    return p


class SpeechModelOnDisk(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        for patcher in (mock.patch.object(bootstrap.os.path, "expanduser", lambda p: self.home),
                        mock.patch.object(bootstrap, "_speech_models", lambda: (["medium.en"], 1500))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def snapshot(self, name, files=("model.bin",)):
        d = os.path.join(self.home, ".cache", "huggingface", "hub", f"models--Systran--faster-whisper-{name}", "snapshots", "abc123")
        os.makedirs(d)
        for f in files:
            open(os.path.join(d, f), "wb").close()

    def test_missing_until_the_model_file_is_there(self):
        self.assertFalse(bootstrap.speech_model_ready())
        self.snapshot("medium.en", files=("config.json",))              # a half-finished download is not ready
        self.assertFalse(bootstrap.speech_model_ready())

    def test_ready_when_the_model_is_on_disk(self):
        self.snapshot("medium.en")
        self.assertTrue(bootstrap.speech_model_ready())

    def test_every_model_the_ears_need_must_be_there(self):
        with mock.patch.object(bootstrap, "_speech_models", lambda: (["base.en", "small.en"], 620)):
            self.snapshot("base.en")
            self.assertFalse(bootstrap.speech_model_ready())
            self.snapshot("small.en")
            self.assertTrue(bootstrap.speech_model_ready())


class ChosenModel(unittest.TestCase):
    def test_the_model_chosen_in_settings_is_the_one_checked(self):
        import config
        with mock.patch.dict(config.KEY, {"brain": {"whisper_model": "small.en"}}):
            self.assertEqual(bootstrap._speech_models(), (["small.en"], 480))


class WhileTheSpeechModelDownloads(unittest.TestCase):
    def test_a_download_is_shown_not_hidden(self):
        items = collect(**_probes(speech=lambda: {"state": "downloading", "progress": 42}))
        self.assertEqual([i["id"] for i in items], ["speech-downloading"])
        self.assertEqual(items[0]["level"], "info")
        self.assertIn("42%", items[0]["message"])
        self.assertIn("typing works", items[0]["message"])

    def test_a_failure_is_a_warning_with_what_to_do(self):
        item = collect(**_probes(speech=lambda: {"state": "error", "progress": 0}))[0]
        self.assertEqual((item["id"], item["level"]), ("speech-failed", "warn"))
        self.assertIn("internet", item["message"])

    def test_nothing_is_shown_when_it_is_ready_or_unknown(self):
        self.assertEqual(collect(**_probes()), [])
        self.assertEqual(collect(**_probes(speech=lambda: {})), [])
        self.assertEqual(collect(**_probes(speech=lambda: None)), [])


if __name__ == "__main__":
    unittest.main()


class SpeechDownload(unittest.TestCase):
    """Step 4's biggest download: real progress (not 1% for minutes), one at a time, and it can start early."""

    def setUp(self):
        self.ready = False
        for patcher in (mock.patch.object(bootstrap, "speech_model_ready", lambda: self.ready),
                        mock.patch.object(bootstrap, "_speech_models", lambda: (["base.en", "small.en"], 630))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.seen = []

    def state(self):
        return dict(bootstrap._bootstrap_state["speech_model"])

    def test_nothing_is_downloaded_when_it_is_already_there(self):
        self.ready = True
        with mock.patch.object(bootstrap, "_download_whisper") as dl:
            self.assertTrue(bootstrap.ensure_speech_model())
        dl.assert_not_called()
        self.assertEqual(self.state()["status"], "done")

    def test_progress_moves_through_the_models_and_ends_done(self):
        def fake(name, on_progress, cache_dir=None):
            for frac in (0.25, 0.5, 1.0):
                on_progress(int(frac * 100), 100)
                self.seen.append((name, self.state()["progress"], self.state()["current"]))
        with mock.patch.object(bootstrap, "_download_whisper", fake):
            self.assertTrue(bootstrap.ensure_speech_model())
        base = [p for n, p, _ in self.seen if n == "base.en"]
        small = [p for n, p, _ in self.seen if n == "small.en"]
        self.assertEqual(base, sorted(base))
        self.assertLess(max(base), min(small) + 1)                       # the second model continues from where the first ended
        self.assertEqual(small, sorted(small))
        self.assertGreater(small[0], 20)
        self.assertIn("MB", self.seen[0][2])                             # says how much, in words a person understands
        self.assertEqual((self.state()["status"], self.state()["progress"]), ("done", 100))

    def test_a_failed_download_says_what_to_do(self):
        with mock.patch.object(bootstrap, "_download_whisper", side_effect=RuntimeError("offline")), \
                fake_whisper(side_effect=RuntimeError("offline")):
            self.assertFalse(bootstrap.ensure_speech_model())
        self.assertEqual(self.state()["status"], "error")
        self.assertIn("internet", self.state()["error"])

    def test_if_the_progress_download_fails_the_plain_one_is_tried(self):
        with mock.patch.object(bootstrap, "_download_whisper", side_effect=RuntimeError("no progress")), \
                fake_whisper() as plain:
            self.assertTrue(bootstrap.ensure_speech_model())
        self.assertEqual([c.args[0] for c in plain.call_args_list], ["base.en", "small.en"])

    def test_two_requests_never_download_twice_at_once(self):
        import threading
        gate, started, calls = threading.Event(), threading.Event(), []

        def slow(name, on_progress, cache_dir=None):
            calls.append(name)
            started.set()
            gate.wait(3)
        with mock.patch.object(bootstrap, "_download_whisper", slow):
            first = threading.Thread(target=bootstrap.ensure_speech_model)
            first.start()
            started.wait(2)
            self.ready = False
            second = threading.Thread(target=bootstrap.ensure_speech_model)
            second.start()
            self.ready = True                                            # the first one finishes and the model is there
            gate.set()
            first.join(5)
            second.join(5)
        self.assertEqual(calls, ["base.en", "small.en"])                 # one pass, not two

    def test_the_plain_download_mode_is_used_and_put_back(self):
        from huggingface_hub import constants
        before = (os.environ.get("HF_HUB_DISABLE_XET"), constants.HF_HUB_DISABLE_XET)
        with bootstrap._classic_downloads():
            self.assertEqual(os.environ["HF_HUB_DISABLE_XET"], "1")
            self.assertTrue(constants.HF_HUB_DISABLE_XET)
        self.assertEqual((os.environ.get("HF_HUB_DISABLE_XET"), constants.HF_HUB_DISABLE_XET), before)

    def test_the_wizard_can_start_it_early_and_only_once(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend.routes import setup as setup_routes
        except Exception:
            self.skipTest("needs fastapi")
        import threading
        app = FastAPI()
        app.include_router(setup_routes.router)
        client = TestClient(app)
        gate, runs = threading.Event(), []

        def slow():
            runs.append(1)
            gate.wait(3)
        setup_routes._speech_thread = None
        with mock.patch.object(bootstrap, "ensure_speech_model", slow):
            self.assertEqual(client.post("/api/setup/speech-install").json()["status"], "running")
            time.sleep(0.1)
            client.post("/api/setup/speech-install")
            gate.set()
        self.assertEqual(len(runs), 1)
        self.ready = True
        self.assertEqual(client.post("/api/setup/speech-install").json()["status"], "done")


class DefaultSpeechModel(unittest.TestCase):
    """The default is small.en (about 480 MB). A PC that already has medium.en and not small.en keeps medium: no new download."""

    def cached(self, *names):
        return mock.patch.object(bootstrap, "_speech_cached", lambda n: n in names)

    def test_small_unless_only_medium_is_on_the_pc(self):
        with self.cached():
            self.assertEqual(bootstrap.default_speech_model(), "small.en")
        with self.cached("small.en"):
            self.assertEqual(bootstrap.default_speech_model(), "small.en")
        with self.cached("small.en", "medium.en"):
            self.assertEqual(bootstrap.default_speech_model(), "small.en")
        with self.cached("medium.en"):
            self.assertEqual(bootstrap.default_speech_model(), "medium.en")

    def test_a_pc_with_a_graphics_card_downloads_the_small_model_not_1_5_gb(self):
        import sys
        import types
        import config
        fake = types.SimpleNamespace(get_cuda_device_count=lambda: 1)
        with mock.patch.dict(sys.modules, {"ctranslate2": fake}), mock.patch.dict(config.KEY, {"brain": {"whisper_model": ""}}),                 self.cached():
            self.assertEqual(bootstrap._speech_models(), (["small.en"], 480))
        with mock.patch.dict(sys.modules, {"ctranslate2": fake}), mock.patch.dict(config.KEY, {"brain": {"whisper_model": ""}}),                 self.cached("medium.en"):
            self.assertEqual(bootstrap._speech_models(), (["medium.en"], 1500))

    def test_settings_offers_medium_as_the_upgrade(self):
        try:
            from backend.routes import setup as setup_routes
        except Exception:
            self.skipTest("needs fastapi")
        tags = {m["id"]: m["tag"] for m in setup_routes.WHISPER_MODELS}
        self.assertEqual(tags["small.en"], "BALANCED")          # the recommendation itself is worked out per PC (test_model_advice)
        self.assertEqual(tags["medium.en"], "BETTER ACCURACY")
