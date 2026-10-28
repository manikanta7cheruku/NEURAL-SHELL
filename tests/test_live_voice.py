"""
The live voice pieces around the ears: push to talk (the key starts and ends what Seven hears, and typing a capital
letter never counts), window commands done before Seven speaks, a reminder never calling you "Voice_User", and the
home screen's reading of what Seven uses on this PC. No microphone, no models.
"""
import queue
import sys
import threading
import unittest

import numpy as np

import support  # noqa: F401  (sets up paths and test mode)


class _FakeStream:
    def __init__(self, n, owner):
        self.n, self.i, self.owner = n, 0, owner

    def read(self, frames, exception_on_overflow=False):
        self.i += 1
        if self.i >= self.n:
            self.owner._running.clear()
        return (np.ones(frames, dtype=np.int16) * 300).tobytes()


def _run_stream(held, probs):
    """Feed a MicStream frames whose speech probability is probs[i] while the key is held[i]."""
    from ears.stream import MicStream
    s = MicStream()
    s._running.set()
    s._reopen = False
    s.set_push_to_talk((lambda: held[min(s_frame[0], len(held) - 1)]) if held is not None else None)
    s_frame = [0]

    def vad(frame):
        p = probs[min(s_frame[0], len(probs) - 1)]
        s_frame[0] += 1
        return p
    s._listen(_FakeStream(len(probs), s), vad)
    out = []
    while True:
        try:
            out.append(s.utterances.get_nowait())
        except queue.Empty:
            return out


class PushToTalk(unittest.TestCase):
    def test_letting_go_ends_the_utterance_at_once(self):
        # 40 frames held (1.3 s, speech throughout), then released: one utterance, no waiting for silence
        held = [True] * 40 + [False] * 5
        utts = _run_stream(held, [0.9] * 45)
        self.assertEqual(len(utts), 1)
        self.assertTrue(utts[0].meta.get("ptt"))
        self.assertGreater(utts[0].seconds, 1.0)

    def test_a_tap_is_not_speech(self):
        held = [False] * 5 + [True] * 4 + [False] * 10
        self.assertEqual(_run_stream(held, [0.9] * 19), [])

    def test_holding_the_key_in_silence_is_nothing(self):
        held = [True] * 40 + [False] * 5
        self.assertEqual(_run_stream(held, [0.05] * 45), [])

    def test_shift_with_another_key_is_typing(self):
        from ears import push_to_talk as k
        k._released(True)
        k._pressed(True)
        self.assertTrue(k.is_held())
        k._pressed(False)                      # Shift+A: a capital letter
        self.assertFalse(k.is_held())
        k._pressed(True)                       # still held from before: still typing
        self.assertFalse(k.is_held())
        k._released(True)
        k._pressed(True)                       # a fresh hold on its own counts again
        self.assertTrue(k.is_held())
        k._released(True)
        self.assertFalse(k.is_held())


class WindowsBeforeSpeech(unittest.TestCase):
    def _ctx(self):
        calls = []

        class Hands:
            @staticmethod
            def manage_window(params):
                calls.append(params)
                return True, "ok"

        class Ctx:
            hands_windows = Hands()
            speech_part = "Chrome."
            speak_with_interrupt = None
            update_status = staticmethod(lambda *a: None)
            speak = staticmethod(lambda *a: None)
            system_mod = core = None
        return Ctx(), calls

    def test_focus_runs_before_speaking_and_only_once(self):
        from main_modules.handlers.pre_executor import pre_execute
        from main_modules.handlers.window_handler import WindowHandler
        ctx, calls = self._ctx()
        response = "Chrome. ###WINDOW: action=focus target=chrome fallback=open"
        pre_execute(response, ctx)
        for t in threading.enumerate():
            if t.name == "PreExecWindow":
                t.join(2)
        self.assertEqual([c["action"] for c in calls], ["focus"])
        WindowHandler().execute(response, ctx)           # after speaking: already done
        self.assertEqual(len(calls), 1)
        WindowHandler().execute(response, ctx)           # a later, separate request still works
        self.assertEqual(len(calls), 2)

    def test_listing_windows_waits_for_speech(self):
        from main_modules.handlers.pre_executor import pre_execute
        ctx, calls = self._ctx()
        pre_execute("Here they are. ###WINDOW: action=list", ctx)
        self.assertFalse(ctx.pre_executed_window)
        self.assertEqual(calls, [])


class ReminderName(unittest.TestCase):
    def test_voice_requests_never_become_voice_user(self):
        from brain_modules.session import display_name
        for sid in ("voice_user", "default", "unknown"):
            self.assertNotIn("voice", display_name(sid).lower())
            self.assertNotEqual(display_name(sid), sid.title())


@unittest.skipUnless(sys.platform == "win32", "reads Windows' process list")
class Usage(unittest.TestCase):
    def test_reading_has_seven_and_the_heaviest_apps(self):
        from brain_modules import resource_usage
        u = resource_usage.usage()
        self.assertEqual({p["name"] for p in u["seven"]["parts"]}, {"Seven", "AI model"})
        self.assertGreater(u["seven"]["ram_gb"], 0)              # this test's own Python counts as Seven
        self.assertLessEqual(len(u["top"]), 5)
        self.assertNotIn("Seven", [a["name"] for a in u["top"]])
        self.assertEqual([a["ram_gb"] for a in u["top"]], sorted((a["ram_gb"] for a in u["top"]), reverse=True))
        self.assertGreater(u["total"]["ram_total_gb"], 0)


class Attention(unittest.TestCase):
    """The home screen's "needs attention" strip: only real problems, most important first, nothing when all is well."""

    def collect(self, **kw):
        from backend.routes.attention import collect
        probes = dict(mic_error=lambda: "", voice=lambda: {"ready": True, "status": "done", "progress": 100},
                      ollama_up=lambda: True, uptime=lambda: 600, setup_done=lambda: True)
        probes.update(kw)
        return collect(**probes)

    def test_nothing_when_all_is_well(self):
        self.assertEqual(self.collect(), [])

    def test_nothing_before_setup_is_finished(self):
        self.assertEqual(self.collect(setup_done=lambda: False, mic_error=lambda: "no device"), [])

    def test_a_microphone_problem_comes_first_and_points_to_the_fix(self):
        items = self.collect(mic_error=lambda: "Invalid input device", ollama_up=lambda: False,
                             voice=lambda: {"ready": False, "status": "running", "progress": 40})
        self.assertEqual([i["id"] for i in items], ["mic", "model", "voice-downloading"])
        self.assertEqual(items[0]["level"], "error")
        self.assertEqual(items[0]["action"]["to"], "/settings?section=voice")
        self.assertNotIn("Invalid input device", items[0]["message"])      # no raw error text

    def test_voice_states(self):
        down = self.collect(voice=lambda: {"ready": False, "status": "running", "progress": 62})[0]
        self.assertEqual((down["level"], "62%" in down["message"]), ("info", True))
        failed = self.collect(voice=lambda: {"ready": False, "status": "error", "progress": 0})[0]
        self.assertEqual((failed["id"], failed["level"]), ("voice-failed", "warn"))
        missing = self.collect(voice=lambda: {"ready": False, "status": "pending", "progress": 0})[0]
        self.assertEqual(missing["id"], "voice-missing")

    def test_model_is_not_reported_while_seven_is_still_starting(self):
        self.assertEqual(self.collect(ollama_up=lambda: False, uptime=lambda: 20), [])
        self.assertEqual(self.collect(ollama_up=lambda: False, uptime=lambda: 200)[0]["id"], "model")

    def test_a_probe_that_fails_never_breaks_the_list(self):
        def boom():
            raise RuntimeError("x")
        self.assertEqual(self.collect(mic_error=boom, voice=boom, ollama_up=boom), [])


@unittest.skipUnless(sys.platform == "win32", "Windows' proactor event loop")
class ApiSurvivesDroppedConnections(unittest.TestCase):
    """npm run dev showed "Backend Unreachable" while Seven kept talking: on Windows' default event loop one dropped
    connection during startup (WinError 64) closes the API's listening socket for good. The API runs on a selector loop."""

    def test_the_api_uses_a_selector_loop(self):
        import asyncio
        from backend.api_server import _new_event_loop
        loop = _new_event_loop()
        try:
            self.assertIsInstance(loop, asyncio.SelectorEventLoop)
            self.assertNotIsInstance(loop, asyncio.ProactorEventLoop)
        finally:
            loop.close()

    def test_the_listener_survives_connections_dropped_the_instant_they_open(self):
        import asyncio
        import socket
        import struct
        import time

        import uvicorn
        from fastapi import FastAPI
        from backend.api_server import _new_event_loop

        with socket.socket() as probe:                      # a free port
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        app = FastAPI()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))

        def run():
            loop = _new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(server.serve())
        t = threading.Thread(target=run, daemon=True)
        t.start()
        self.addCleanup(t.join, 5)
        self.addCleanup(setattr, server, "should_exit", True)

        def listening():
            with socket.socket() as s:
                s.settimeout(1)
                return s.connect_ex(("127.0.0.1", port)) == 0

        deadline = time.time() + 10
        while not listening() and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(listening())
        for _ in range(600):
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))   # close sends a reset
            try:
                s.connect(("127.0.0.1", port))
            except OSError:
                pass
            s.close()
        time.sleep(0.5)
        self.assertTrue(listening())


if __name__ == "__main__":
    unittest.main()
