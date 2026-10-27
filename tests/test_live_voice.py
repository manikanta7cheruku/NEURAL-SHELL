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


if __name__ == "__main__":
    unittest.main()
