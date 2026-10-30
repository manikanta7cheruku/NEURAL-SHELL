"""
Seven knows the PC, so it says which speech model suits it and what to be careful about, and the language-model
download says which model is downloading.
"""
import json
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from backend import bootstrap
from ears import whisper_advice as advice

RTX = {"cuda": True, "gpu": "NVIDIA GeForce RTX 4060", "vram_gb": 8.0, "ram_gb": 32.0}
SMALL_GPU = {"cuda": True, "gpu": "NVIDIA GeForce GTX 1050", "vram_gb": 2.0, "ram_gb": 16.0}
LAPTOP = {"cuda": False, "gpu": "Intel(R) Iris(R) Xe Graphics", "vram_gb": 0.0, "ram_gb": 16.0}
TINY = {"cuda": False, "gpu": None, "vram_gb": 0.0, "ram_gb": 4.0}


def rec(hw):
    return advice.recommended_id(hw)


class Advice(unittest.TestCase):
    def test_small_is_recommended_nearly_everywhere(self):
        self.assertEqual((rec(RTX), rec(SMALL_GPU), rec(LAPTOP), rec({})), ("small.en",) * 4)

    def test_a_processor_only_pc_with_little_memory_gets_the_lightest_model(self):
        self.assertEqual(rec(TINY), "base.en")
        self.assertEqual(rec({"cuda": False, "ram_gb": 0}), "small.en")            # unknown memory never forces it

    def test_exactly_one_model_is_recommended(self):
        for hw in (RTX, SMALL_GPU, LAPTOP, TINY):
            self.assertEqual(sum(advice.advise(m, hw)["recommended"] for m in advice.MODEL_GB), 1, hw)

    def test_medium_is_fine_on_a_real_graphics_card(self):
        a = advice.advise("medium.en", RTX)
        self.assertEqual(a["level"], "ok")
        self.assertIn("RTX 4060", a["note"])

    def test_medium_is_a_caution_without_a_graphics_card_and_says_why(self):
        a = advice.advise("medium.en", LAPTOP)
        self.assertEqual(a["level"], "caution")
        self.assertIn("NVIDIA", a["note"])
        self.assertIn("several seconds", a["note"])

    def test_a_weak_card_and_a_small_memory_are_called_out(self):
        self.assertEqual(advice.advise("medium.en", SMALL_GPU)["level"], "caution")
        self.assertIn("2 GB", advice.advise("medium.en", SMALL_GPU)["note"])
        self.assertIn("3 GB", advice.advise("medium.en", {**LAPTOP, "ram_gb": 8.0})["note"])

    def test_large_needs_a_strong_card(self):
        self.assertEqual(advice.advise("large-v3", RTX)["level"], "ok")
        self.assertEqual(advice.advise("large-v3", SMALL_GPU)["level"], "caution")
        self.assertIn("Not recommended", advice.advise("large-v3", LAPTOP)["note"])

    def test_the_recommended_model_explains_itself(self):
        self.assertIn("RTX 4060", advice.advise("small.en", RTX)["note"])
        self.assertIn("fast model first", advice.advise("small.en", LAPTOP)["note"])
        self.assertIn("little memory", advice.advise("base.en", TINY)["note"])

    def test_unknown_readings_never_block_anything(self):
        for m in advice.MODEL_GB:
            self.assertIn(advice.advise(m, {})["level"], ("ok", "caution"))


class SettingsList(unittest.TestCase):
    def test_every_model_carries_the_advice_and_the_pc(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend.routes import setup as setup_routes
        except Exception:
            self.skipTest("needs fastapi")
        app = FastAPI()
        app.include_router(setup_routes.router)
        with mock.patch.object(setup_routes, "_speech_hardware", lambda: LAPTOP):
            body = TestClient(app).get("/api/setup/whisper-models").json()
        self.assertEqual(body["hardware"]["gpu"], LAPTOP["gpu"])
        by = {m["id"]: m for m in body["models"]}
        self.assertTrue(by["small.en"]["recommended"])
        self.assertFalse(by["medium.en"]["recommended"])
        self.assertEqual(by["medium.en"]["advice"]["level"], "caution")
        self.assertEqual(sum(m["recommended"] for m in body["models"]), 1)


class _Stream:
    def __init__(self, lines, fail=None):
        self.lines, self.fail = lines, fail

    def raise_for_status(self):
        if self.fail:
            raise self.fail

    def iter_lines(self):
        for line in self.lines:
            yield json.dumps(line).encode()


class BrainDownloadSaysWhich(unittest.TestCase):
    def pull(self, name, lines, fail=None):
        with mock.patch("requests.post", return_value=_Stream(lines, fail)), mock.patch.object(bootstrap.time, "sleep"):
            ok = bootstrap.pull_model(name)
        return ok, dict(bootstrap._bootstrap_state["model_pull"])

    def test_the_download_is_named_and_measured(self):
        gb = 1024 ** 3
        lines = [{"status": "pulling manifest"}, {"status": "pulling abc", "total": 5 * gb, "completed": 1 * gb},
                 {"status": "pulling abc", "total": 5 * gb, "completed": 3 * gb}, {"status": "success"}]
        ok, state = self.pull("qwen2.5:7b", lines)
        self.assertTrue(ok)
        self.assertEqual((state["model"], state["label"], state["status"]), ("qwen2.5:7b", "Qwen 2.5 7B", "done"))

    def test_a_model_outside_the_catalog_is_called_by_its_name(self):
        _, state = self.pull("some-model:1b", [{"status": "success"}])
        self.assertEqual(state["label"], "some-model:1b")

    def test_progress_text_and_speed_are_reported_while_it_runs(self):
        gb = 1024 ** 3
        times = iter([100.0, 100.1, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0])
        lines = [{"status": "pulling x", "total": 2 * gb, "completed": gb // 2}]
        with mock.patch("requests.post", return_value=_Stream(lines)), mock.patch.object(bootstrap.time, "time", lambda: next(times)):
            bootstrap.pull_model("llama3.2:3b")
        state = bootstrap._bootstrap_state["model_pull"]
        self.assertIn("GB", state["current"] if state["status"] != "done" else "GB")
        self.assertEqual(state["label"], "Llama 3.2 3B")

    def test_a_failure_names_the_model(self):
        import requests
        ok, state = self.pull("llama3.1:8b", [], fail=requests.exceptions.ConnectionError("no route"))
        self.assertFalse(ok)
        self.assertEqual(state["status"], "error")
        self.assertTrue(state["error"].startswith("Llama 3.1 8B could not be downloaded"))

    def test_status_words_are_plain(self):
        seen = []
        orig = bootstrap._set

        def spy(section, **kw):
            if section == "model_pull" and "current" in kw:
                seen.append(kw["current"])
            return orig(section, **kw)
        with mock.patch.object(bootstrap, "_set", spy):
            self.pull("llama3.2:1b", [{"status": "pulling manifest"}, {"status": "verifying sha256 digest"}])
        self.assertIn("Contacting the model library", seen)


if __name__ == "__main__":
    unittest.main()
