"""
The last setup page loads Seven while it waits, so Launch Seven opens the app straight away.

    POST /api/setup/prepare        saves the wizard's choices WITHOUT finishing setup, and asks the backend to load
    GET  /api/setup/prepare-status how far loading has got (what the last page shows)
    POST /api/setup/complete       finishes setup (the loaded Seven then starts talking, no restart)
"""
import copy
import unittest
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
import config

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routes import setup as setup_routes
except Exception:                                       # fastapi missing: this file is skipped
    FastAPI = None

BODY = {"name": "Asha", "email": "asha@example.com", "wake_word": "Seven", "voice_index": 0, "voice_id": "af_heart",
        "voice_engine": "kokoro", "model_name": "llama3.2:3b"}


@unittest.skipIf(FastAPI is None, "needs fastapi")
class Prepare(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(setup_routes.router)
        self.client = TestClient(app)
        self.state = {}
        saved = copy.deepcopy(config.KEY)
        self.addCleanup(lambda: (config.KEY.clear(), config.KEY.update(saved)))
        config.KEY["setup_complete"] = False
        import backend.api_server as api
        p = mock.patch.multiple(api, _state=self.state, set_state=lambda k, v: self.state.__setitem__(k, v))
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(config, "update_config", side_effect=self._update)    # in memory: never the real file
        q.start()
        self.addCleanup(q.stop)

    def _update(self, updates):
        self._merge(config.KEY, updates)
        return True

    def _merge(self, base, override):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def test_it_saves_the_choices_but_does_not_finish_setup(self):
        r = self.client.post("/api/setup/prepare", json=BODY)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(config.KEY.get("setup_complete"))                 # still in the wizard
        self.assertEqual(config.KEY["identity"]["user_name"], "Asha")
        self.assertEqual(config.KEY["identity"]["wake_words"], ["seven", "hey seven"])
        self.assertEqual(config.KEY["brain"]["model_name"], "llama3.2:3b")
        self.assertEqual(config.KEY["voice"]["voice_id"], "af_heart")
        self.assertTrue(self.state["prepare_requested"])

    def test_asking_twice_is_harmless(self):
        self.assertFalse(self.client.post("/api/setup/prepare", json=BODY).json()["already"])
        self.assertTrue(self.client.post("/api/setup/prepare", json=BODY).json()["already"])

    def test_a_name_and_email_are_still_required(self):
        self.assertEqual(self.client.post("/api/setup/prepare", json={**BODY, "name": " "}).status_code, 400)
        self.assertEqual(self.client.post("/api/setup/prepare", json={**BODY, "email": "nope"}).status_code, 400)
        self.assertNotIn("prepare_requested", self.state)

    def test_status_tells_the_last_page_how_far_loading_got(self):
        self.assertEqual(self.client.get("/api/setup/prepare-status").json(),
                         {"requested": False, "started": False, "ready": False, "stage": "", "speech": None})
        self.state.update(prepare_requested=True, prepare_started=True, ready=False, ready_stage="Starting the ears",
                          speech_model={"state": "downloading", "progress": 40})
        s = self.client.get("/api/setup/prepare-status").json()
        self.assertEqual((s["started"], s["ready"], s["stage"], s["speech"]["progress"]), (True, False, "Starting the ears", 40))
        self.state["ready"] = True
        self.assertTrue(self.client.get("/api/setup/prepare-status").json()["ready"])

    def test_ready_is_never_reported_before_loading_started(self):
        self.state.update(ready=True)                                     # a stale flag must not enable Launch
        self.assertFalse(self.client.get("/api/setup/prepare-status").json()["ready"])

    def test_complete_still_finishes_setup(self):
        with mock.patch("requests.post"):
            r = self.client.post("/api/setup/complete", json=BODY)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(config.KEY["setup_complete"])


if __name__ == "__main__":
    unittest.main()
