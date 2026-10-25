"""
A mistyped file name finds the file it was close to, and Seven asks before opening it ("gookarna" -> GOKARNA.mp4).
An app whose shortcut points to a program that is gone is reported as such, never as launched.
"""
import os
import tempfile
import unittest

import support  # noqa: F401  (sets up paths and test mode)
from brain_modules import action_receipts
from hands import app_launcher, files


class Typos(unittest.TestCase):
    VOCAB = sorted({"gokarna", "dandiya", "resume", "budget", "trip", "goa", "invoice", "report"})

    def test_close_words_are_corrected(self):
        self.assertEqual(files._closest_word("gookarna", self.VOCAB), "gokarna")
        self.assertEqual(files._closest_word("dandya", self.VOCAB), "dandiya")
        self.assertEqual(files._closest_word("resme", self.VOCAB), "resume")

    def test_unrelated_and_short_words_are_left_alone(self):
        self.assertIsNone(files._closest_word("zqxwv", self.VOCAB))
        self.assertIsNone(files._closest_word("gao", self.VOCAB))          # too short to guess at
        self.assertIsNone(files._closest_word("budget", self.VOCAB))       # already a real word

    def test_near_matches_never_open_by_themselves(self):
        real = files.search_files
        try:
            files.search_files = lambda q, n=None, u="": [{"name": "GOKARNA.mp4", "path": "x", "score": 1050,
                                                           "ext": ".mp4", "size_kb": 1, "modified": ""}]
            original = files._name_vocabulary
            files._name_vocabulary = lambda: self.VOCAB
            out = files._search_similar("gookarna video", ["gookarna", "video"], 8, "")
        finally:
            files.search_files = real
            files._name_vocabulary = original
        self.assertEqual(out[0]["similar_to"], "gokarna video")
        self.assertLess(out[0]["score"], files.CONFIDENT_SCORE)

    def test_chat_card_says_what_happened(self):
        hit = [{"name": "a.mp4", "path": "p", "size_kb": 1, "modified": "", "ext": ".mp4", "similar_to": "a video"}]
        card = files.format_results_for_chat(hit, "aa video")
        self.assertFalse(card["opened"])
        self.assertEqual(card["similar_to"], "a video")
        self.assertTrue(files.format_results_for_chat(hit[:1], "a", opened=True)["opened"])


class MissingApps(unittest.TestCase):
    def test_missing_program_is_detected(self):
        gone = r"M:\nowhere-seven-test\App\App.exe"
        self.assertEqual(app_launcher._missing_target({"exe_path": gone, "launch": f'"{gone}"'}), gone)
        self.assertEqual(app_launcher._missing_target({"launch": f'"{gone}" --flag'}), gone)

    def test_present_program_and_store_apps_pass(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            here = f.name
        try:
            self.assertIsNone(app_launcher._missing_target({"exe_path": here, "launch": f'"{here}"'}))
        finally:
            os.unlink(here)
        self.assertIsNone(app_launcher._missing_target({"launch": "explorer.exe shell:AppsFolder\\Microsoft.Photos"}))

    def test_reply_explains_instead_of_claiming_success(self):
        def gone():
            raise app_launcher.AppNotInstalled("Adobe Premiere Pro 2025 isn't where Windows thinks it is (M:\\adobe2). "
                                               "It may have been moved or uninstalled")
        r = action_receipts.run_action("OPEN", "premiere pro", gone)
        self.assertEqual(r.status, "failed")
        reply = action_receipts.reconcile_reply("Sure, launching premiere pro.", [r])
        self.assertTrue(reply.startswith("I couldn't open premiere pro. Adobe Premiere Pro 2025 isn't where"), reply)


if __name__ == "__main__":
    unittest.main()
