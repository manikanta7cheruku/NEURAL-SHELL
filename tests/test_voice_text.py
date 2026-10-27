"""
The text side of Seven's voice, checked without a microphone or models:
Whisper's spellings of the wake word ("Hey 7", "H7") wake Seven while ordinary sentences don't, replies are split so
the first words play sooner, the delivery follows what is said, and older speed settings carry over.
(The audio side is measured by scripts/voice_bench.py.)
"""
import unittest

import support  # noqa: F401  (sets up paths and test mode)
from ears.wake_word import check_and_strip, normalize_wake
from mouth import tone, voices

WAKE = ["hey seven", "ok seven", "okay seven", "seven"]


def woke(text):
    return check_and_strip(normalize_wake(text), WAKE)


class WakeWord(unittest.TestCase):
    def test_whisper_spellings_wake_seven(self):
        for heard, request in [("Hey 7, open chrome.", "open chrome."), ("H7 open crown.", "open crown."),
                               ("A 7 open crown.", "open crown."), ("Hay 7 open chrome.", "open chrome."),
                               ("7, what time is it?", "what time is it?"), ("7 open chrome", "open chrome"),
                               ("OK 7 stop", "stop"), ("Hey seven, mute", "mute")]:
            with self.subTest(heard=heard):
                self.assertEqual(woke(heard), (request, True))

    def test_name_alone_wakes_with_nothing_to_do(self):
        self.assertEqual(woke("Seven.")[0].strip(" ,.!?"), "")
        self.assertTrue(woke("Hey 7.")[1])

    def test_sentences_with_seven_in_them_dont(self):
        for heard in ("A seven-day trip to Goa", "7 tasks are due", "Seventeen apps are open", "Heaven knows",
                      "Open my notes", "Set a reminder at 7"):
            with self.subTest(heard=heard):
                self.assertFalse(woke(heard)[1])


class Delivery(unittest.TestCase):
    def test_tone_follows_the_words(self):
        self.assertEqual(tone.of("I'm sorry to hear that.")["tone"], "gentle")
        self.assertLess(tone.of("That must be hard.")["speed"], 1.0)
        self.assertEqual(tone.of("Great news, it worked!")["tone"], "bright")
        self.assertEqual(tone.of("Should I open it?")["tone"], "asking")
        self.assertEqual(tone.of("Your battery is low.")["tone"], "clear")
        self.assertEqual(tone.of("It is 4 pm.")["tone"], "neutral")

    def test_replies_are_split_into_sentences(self):
        self.assertEqual(tone.chunks("Done. Want me to open it? Okay!"), ["Done.", "Want me to open it?", "Okay!"])
        self.assertEqual(tone.chunks("It is 3.5 percent."), ["It is 3.5 percent."])

    def test_a_long_first_sentence_starts_sooner(self):
        long = ("Good morning, your script is due tomorrow and you also have a call reminder at three o'clock "
                "this afternoon with the bank. Want me to open it?")
        parts = tone.chunks(long)
        self.assertEqual(parts[0], "Good morning,")
        self.assertEqual(parts[-1], "Want me to open it?")

    def test_action_tags_are_never_spoken(self):
        self.assertEqual(tone.chunks("Opening it. ###OPEN: chrome"), ["Opening it."])


class Voices(unittest.TestCase):
    def test_old_speed_settings_carry_over(self):
        self.assertAlmostEqual(voices.speed_factor(165), 1.0)
        self.assertAlmostEqual(voices.speed_factor(1.2), 1.2)
        self.assertEqual(voices.speed_factor(400), 1.4)          # clamped
        self.assertEqual(voices.speed_factor("fast"), 1.0)

    def test_catalog_has_a_default_and_describes_each_voice(self):
        ids = [v["id"] for v in voices.NATURAL]
        self.assertIn(voices.DEFAULT_VOICE, ids)
        for v in voices.NATURAL:
            self.assertTrue(v["name"] and v["note"] and v["accent"])


if __name__ == "__main__":
    unittest.main()
