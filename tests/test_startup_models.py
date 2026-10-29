"""
Starting Seven never waits on a download. The setup wizard fetches the speech model with progress (so it is on the
PC before Seven first starts), and if it is ever missing the app opens anyway and says what is happening.
"""
import os
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from backend import bootstrap
from backend.routes.attention import collect


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
