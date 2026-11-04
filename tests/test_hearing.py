"""
A microphone that delivers only digital silence (muted at the hardware, a driver that gives nothing) made Seven look "listening"
while hearing nothing. Seven now notices, tries the other microphones, and says so when none works.
"""
import unittest

import support  # noqa: F401  (sets up paths and test mode)
from ears import stream as ears_stream
from ears.stream import MicStream


class FakePA:
    DEVICES = [
        {"name": "Microsoft Sound Mapper - Input", "maxInputChannels": 2, "hostApi": 0},
        {"name": "Microphone Array (AMD Audio Dev", "maxInputChannels": 2, "hostApi": 0},
        {"name": "Headset Microphone (USB)", "maxInputChannels": 1, "hostApi": 0},
        {"name": "Stereo Mix (Realtek)", "maxInputChannels": 2, "hostApi": 0},
        {"name": "Microphone Array (AMD Audio Device)", "maxInputChannels": 2, "hostApi": 1},
        {"name": "Speakers", "maxInputChannels": 0, "hostApi": 0},
        {"name": "Microphone (WASAPI)", "maxInputChannels": 2, "hostApi": 2},
    ]

    def get_default_host_api_info(self):
        return {"index": 0}

    def get_host_api_count(self):
        return 3

    def get_host_api_info_by_index(self, i):
        return {"name": ["MME", "Windows DirectSound", "Windows WASAPI"][i]}

    def get_device_count(self):
        return len(self.DEVICES)

    def get_device_info_by_index(self, i):
        return self.DEVICES[i]


class Silence(unittest.TestCase):
    def setUp(self):
        self.mic = MicStream()
        self.published = []
        self.mic.set_publisher(lambda k, v: self.published.append((k, v)))
        self.pa = FakePA()
        self.mic._device_index = lambda pa: 1                      # the default is the AMD array

    def feed(self, seconds, peak, start=1000.0):
        self.mic.last_speech_at = getattr(self, "speech_at", 0.0)
        t, switched = start, False
        while t < start + seconds:
            switched = self.mic._watch_silence(self.pa, peak, t) or switched
            t += 0.032
        return switched

    def test_only_real_microphones_are_tried_not_loopbacks_or_the_mapper(self):
        names = [n for _, n in self.mic._candidates(self.pa)]
        self.assertEqual(names, ["Microphone Array (AMD Audio Dev", "Headset Microphone (USB)", "Microphone Array (AMD Audio Device)"])

    def test_a_quiet_room_is_not_a_dead_microphone(self):
        self.mic._peak_of = lambda index, seconds=0.7: 0.5
        self.assertFalse(self.feed(30, peak=3e-4))                 # a real microphone still hears its own noise
        self.assertIsNone(self.mic._force_index)

    def test_short_silence_does_nothing(self):
        self.assertFalse(self.feed(30, peak=0.0))

    def test_a_microphone_that_carried_speech_lately_is_not_replaced_because_the_room_is_quiet(self):
        self.mic._peak_of = lambda index, seconds=0.7: 0.5
        self.speech_at = 990.0                                     # a noise-gated array: silent until someone speaks
        self.assertFalse(self.feed(300, peak=0.0))
        self.assertIsNone(self.mic._force_index)

    def test_long_digital_silence_switches_to_a_microphone_that_works(self):
        levels = {1: 0.0, 2: 0.02, 4: 0.0}
        self.mic._peak_of = lambda index, seconds=0.7: levels.get(index)
        self.assertTrue(self.feed(70, peak=0.0))
        self.assertEqual(self.mic._force_index, 2)
        self.assertIn("Headset Microphone (USB)", self.mic.notice)
        self.assertIn(("mic_notice", self.mic.notice), self.published)
        self.assertEqual(self.mic.problem, "")

    def test_when_none_works_it_says_so_in_plain_words_and_clears_when_sound_returns(self):
        self.mic._peak_of = lambda index, seconds=0.7: 0.0
        self.assertFalse(self.feed(70, peak=0.0))
        self.assertIn("muted", self.mic.problem)
        self.assertIn(("mic_problem", self.mic.problem), self.published)
        self.mic._watch_silence(self.pa, 0.05, 2000.0)             # someone unmuted it
        self.assertEqual(self.mic.problem, "")
        self.assertEqual(self.published[-1], ("mic_problem", ""))

    def test_it_looks_again_after_a_minute_so_a_plugged_in_headset_is_found(self):
        calls = []
        self.mic._peak_of = lambda index, seconds=0.7: calls.append(index) or 0.0
        self.feed(70, peak=0.0)
        first = len(calls)
        self.feed(60, peak=0.0, start=1070.0)
        self.assertEqual(len(calls), first)                        # within two minutes: no new search
        self.feed(70, peak=0.0, start=1130.0)
        self.assertGreater(len(calls), first)

    def test_choosing_a_microphone_in_settings_overrides_the_automatic_one(self):
        self.mic._force_index = 2
        self.mic.configure(device_name="Some other microphone")
        self.assertIsNone(self.mic._force_index)

    def test_stats_report_what_the_microphone_gave(self):
        self.mic._recent.append((ears_stream.time.time(), 0.01, 0.2, 0.9))
        got = self.mic.stats()
        self.assertEqual(got["best_speech_score"], 0.9)
        self.assertAlmostEqual(got["peak_db"], -13.98, places=1)
        self.assertEqual(got["start_threshold"], 0.55)


if __name__ == "__main__":
    unittest.main()
