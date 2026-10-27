"""
Snap and clap triggers count real snaps and claps at any reasonable distance, and never fire on typing, mouse clicks,
knocks, beeps, music or silence. Uses the synthetic sounds from scripts/snap_bench.py (no microphone, no models).
"""
import os
import sys
import unittest

import support  # noqa: F401  (sets up paths and test mode)

try:
    import scipy  # noqa: F401
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    import snap_bench as b
except ImportError:
    b = None


@unittest.skipIf(b is None, "needs scipy")
class Snaps(unittest.TestCase):
    def test_patterns_are_counted_at_every_distance(self):
        for level in (-12, -24, -32):
            for name, events, want in [("2 snaps", [(0.5, b.snap()), (0.85, b.snap())], [2]),
                                       ("3 snaps", [(0.5, b.snap()), (0.8, b.snap()), (1.15, b.snap())], [3]),
                                       ("2 claps", [(0.5, b.clap()), (0.9, b.clap())], [2])]:
                with self.subTest(sound=name, level=level):
                    self.assertEqual(b.run(b.room(events, 3, level)[0])[0], want)

    def test_one_clear_snap(self):
        self.assertEqual(b.run(b.room([(0.5, b.snap())], 2.5, -12)[0])[0], [1])

    def test_a_faint_single_snap_is_not_enough(self):
        self.assertEqual(b.run(b.room([(0.5, b.snap())], 2.5, -40)[0])[0], [])

    def test_typing_and_clicking_never_fire(self):
        times = [0.3 + 0.18 * i for i in range(25)]
        audio, _ = b.room([(t, b.key()) for t in times], 6, -14)
        self.assertEqual(b.run(audio, times)[0], [])

    def test_other_sharp_sounds_never_fire(self):
        for name, audio in [("knocks", b.room([(0.5, b.knock()), (0.8, b.knock())], 3, -10)[0]),
                            ("beeps", b.room([(0.5, b.beep()), (0.9, b.beep())], 3, -14)[0]),
                            ("music", b.music(5) * 0.3),
                            ("silence", b.np.zeros(b.RATE * 2, b.np.float32))]:
            with self.subTest(sound=name):
                self.assertEqual(b.run(audio)[0], [])


if __name__ == "__main__":
    unittest.main()
