"""
Hands: everyday PC requests reach the right action, file search ranks the user's own files and never guesses, and
"the last pdf I downloaded" means the newest file, not an earlier list.
"""
import os
import tempfile
import time
import unittest
from unittest import mock

from support import BrainTest
import brain

try:
    from hands import files            # needs the Windows packages, which the minimal CI install leaves out
except ImportError:
    files = None


class Routing(BrainTest):
    def test_session_and_screen_actions(self):
        self.assertIn("###SYS: action=lock", self.ask("lock my pc"))
        self.assertIn("###SYS: action=screenshot", self.ask("take a screenshot"))
        self.assertIn("###SYS: action=empty_recycle_bin", self.ask("empty the recycle bin"))
        self.assertTrue(brain.needs_confirmation("SYS", "action=empty_recycle_bin"))

    def test_windows_tools_open_as_apps_not_file_searches(self):
        for name in ("control panel", "vs code", "device manager"):
            with self.subTest(name=name):
                self.assertIn(f"###OPEN: {name}", self.ask(f"open {name}"))

    def test_this_window_is_spoken_naturally(self):
        reply = self.ask("maximize this window")
        self.assertIn("action=maximize", reply)
        self.assertTrue(reply.startswith(reply[0].upper()))
        self.assertNotIn("this,", reply.lower())


@unittest.skipIf(files is None, "hands needs the full Windows install")
class Scoring(unittest.TestCase):
    VIDEO = [".mp4", ".mov", ".avi", ".mkv", ".wmv"]

    def test_short_keywords_do_not_fuzz_into_other_words(self):
        self.assertEqual(files._score_file("tr", ["trip", "video"], self.VIDEO, 0), 0)
        self.assertEqual(files._score_file("TRIM_20191227_115419.mp4", ["trip", "video"], self.VIDEO, 0), 0)
        self.assertGreater(files._score_file("goa_trip.mp4", ["trip", "video"], self.VIDEO, 0), 250)
        self.assertGreater(files._score_file("trip-2024.mp4", ["trip", "video"], self.VIDEO, 0),
                           files._score_file("tripoli.mp4", ["trip", "video"], self.VIDEO, 0))

    def test_folders_never_answer_a_file_type_request(self):
        self.assertEqual(files._score_file("Trip", ["trip", "video"], self.VIDEO, 0, is_folder=True), 0)

    def test_newest_download_by_type(self):
        home = tempfile.mkdtemp()
        downloads = os.path.join(home, "Downloads")
        os.makedirs(downloads)
        for i, name in enumerate(("old.pdf", "photo.jpg", "new.pdf")):
            path = os.path.join(downloads, name)
            open(path, "w").close()
            os.utime(path, (time.time() - 100 + i * 10,) * 2)
        with mock.patch("os.path.expanduser", lambda p: p.replace("~", home)):
            self.assertEqual(files.latest_file("open the last pdf i downloaded")["name"], "new.pdf")
            self.assertIsNone(files.latest_file("open my resume"))


if __name__ == "__main__":
    unittest.main()
