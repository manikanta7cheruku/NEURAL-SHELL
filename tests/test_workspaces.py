"""
Workspaces: chat phrases save and restore, browser tabs are read correctly per window, and the browser session
reader understands Chromium's real format.
"""
import os
import struct
import tempfile
import unittest

from support import BrainTest


class Phrases(BrainTest):
    def test_scan_phrases_save_the_workspace(self):
        for text in ("scan my current workspace", "capture my setup", "snapshot my desktop", "save this workspace"):
            with self.subTest(text=text):
                self.assertTrue(self.ask(text).endswith("###WORKSPACE: action=save"))
        self.assertIn("action=save name=study", self.ask("save what I have open as study"))

    def test_workspace_sentences_never_search_files(self):
        self.assertNotIn("Opened", self.ask("open my study workspace"))


def _pickle_string(text: str, wide: bool) -> bytes:
    raw = text.encode("utf-16-le" if wide else "utf-8")
    body = struct.pack("<i", len(text) if wide else len(raw)) + raw
    return body + b"\0" * ((4 - len(raw) % 4) % 4)


def _command(cid: int, payload: bytes) -> bytes:
    return struct.pack("<H", len(payload) + 1) + bytes([cid]) + payload


def _navigation(tab: int, index: int, url: str, title: str) -> bytes:
    body = struct.pack("<ii", tab, index) + _pickle_string(url, False) + _pickle_string(title, True)
    return _command(6, struct.pack("<I", len(body)) + body)


class SessionFile(unittest.TestCase):
    def test_current_page_per_tab_closed_tabs_dropped(self):
        try:
            from hands.workspace_modules import browser_sessions
        except ImportError:
            self.skipTest("hands needs the full Windows install")
        data = b"SNSS" + struct.pack("<i", 3)
        data += _command(0, struct.pack("<ii", 1, 10))                 # tab 10 in window 1
        data += _command(0, struct.pack("<ii", 1, 11))                 # tab 11 in window 1
        data += _navigation(10, 0, "https://example.com/old", "Old")
        data += _navigation(10, 1, "https://example.com/now", "Now")
        data += _command(7, struct.pack("<ii", 10, 1))                 # tab 10 shows navigation 1
        data += _command(2, struct.pack("<ii", 10, 0))
        data += _navigation(11, 0, "https://closed.example/", "Closed")
        data += _command(16, struct.pack("<iq", 11, 0))                # tab 11 closed
        data += _command(12, struct.pack("<i?xxx", 10, True))          # tab 10 pinned
        path = os.path.join(tempfile.mkdtemp(), "Session_1")
        with open(path, "wb") as f:
            f.write(data)
        windows = browser_sessions.parse_session(path)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["tabs"], [{"url": "https://example.com/now", "title": "Now", "pinned": True}])


class BrowserTitles(unittest.TestCase):
    def setUp(self):
        try:
            from hands.workspace_modules import browser_capture, browser_tabs
        except ImportError:
            self.skipTest("hands needs the full Windows install")
        self.capture, self.tabs = browser_capture, browser_tabs

    def test_address_bar_values_get_their_scheme_back(self):
        n = self.tabs.normalize_address
        self.assertEqual(n("google.com/search?q=x"), "https://google.com/search?q=x")
        self.assertEqual(n("M:/notes/week1.pdf"), "file:///M:/notes/week1.pdf")
        self.assertEqual(n("https://already.example/"), "https://already.example/")

    def test_window_titles_lose_the_browser_and_profile(self):
        from unittest import mock
        names = {"personal": "Default", "mani": "Profile 1"}
        with mock.patch.object(self.capture, "_profile_names", lambda browser: names):
            split = self.capture.split_title
            self.assertEqual(split("edge", "Resume.pdf and 1 more page - Personal - Microsoft​ Edge"),
                             ("Resume.pdf", "Default"))
            self.assertEqual(split("edge", "Inbox - Gmail - Microsoft​ Edge"), ("Inbox - Gmail", ""))
            self.assertEqual(split("chrome", "Inbox - Gmail - Google Chrome"), ("Inbox - Gmail", ""))
            self.assertEqual(split("chrome", "Inbox - Gmail - Google Chrome - Mani"), ("Inbox - Gmail", "Profile 1"))


if __name__ == "__main__":
    unittest.main()
