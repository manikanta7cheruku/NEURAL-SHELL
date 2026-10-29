"""
The update system on the user's PC: what it asks for, who it trusts, how it checks a download, and when it stays quiet.
Nothing here touches the internet or the real settings.
"""
import hashlib
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="seven_upd_")

import requests  # noqa: E402

from backend import updater  # noqa: E402

INSTALLER = b"MZ" + b"\0" * (updater.MIN_INSTALLER_BYTES + 10)
SHA = hashlib.sha256(INSTALLER).hexdigest()


class Resp:
    def __init__(self, status=200, data=None, chunks=(), headers=None):
        self.status_code, self._data, self._chunks, self.headers = status, data, chunks, headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        yield from self._chunks


SERVER_UPDATE = {"update_available": True, "version": "1.4.0", "summary": "Faster and calmer.",
                 "notes": {"new": ["Voice mode"], "improved": ["Startup"], "fixed": ["Reminders"]},
                 "changelog": ["New: Voice mode", "Improved: Startup", "Fixed: Reminders", "Also: a loose line"],
                 "download_url": "https://github.com/x/y/SEVEN-Setup-1.4.0.exe", "size_mb": 180, "is_critical": False,
                 "download_mode": "manual", "sha256": SHA, "published_at": "2026-10-29T10:00:00"}

GITHUB_RELEASE = {"tag_name": "v1.4.0", "published_at": "2026-10-29T10:00:00", "assets": [
    {"name": "SEVEN-Setup-1.4.0.exe", "browser_download_url": "https://github.com/x/y/SEVEN-Setup-1.4.0.exe", "size": 188743680}],
    "body": "A calmer, faster Seven.\n\n### New\n- Voice mode\n\n### Fixed\n- Reminders\n\nSHA256: " + SHA}


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        updater._state.update(update_available=False, checking=False, downloading=False, download_progress=0,
                              download_path=None, error=None, info=None, check_failed=False, last_checked=None)
        for name, value in (("_read_current_version", "1.3.0"), ("_get_tier", "free"), ("_check_local_override", None)):
            p = mock.patch.object(updater, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(updater.time, "sleep")
        p.start()
        self.addCleanup(p.stop)


def wait_for_check():
    import time as real
    deadline = real.monotonic() + 5
    while updater._state["last_checked"] is None and real.monotonic() < deadline:
        pass                                            # the check sets last_checked when it finishes, however it ends


class Notes(unittest.TestCase):
    def test_a_github_description_becomes_summary_and_groups(self):
        summary, notes, loose = updater.parse_release_body(GITHUB_RELEASE["body"])
        self.assertEqual(summary, "A calmer, faster Seven.")
        self.assertEqual(notes, {"new": ["Voice mode"], "fixed": ["Reminders"]})
        self.assertEqual(loose, [])

    def test_bullets_without_headings_are_kept(self):
        summary, notes, loose = updater.parse_release_body("- Fixed a thing\n- Added a thing")
        self.assertEqual((summary, notes, loose), ("", {}, ["Fixed a thing", "Added a thing"]))

    def test_server_notes_keep_the_groups_and_any_extra_line(self):
        info = updater._info_from_server(SERVER_UPDATE)
        self.assertEqual(info["notes"]["new"], ["Voice mode"])
        self.assertEqual(info["summary"], "Faster and calmer.")
        self.assertEqual(info["changelog"], ["New: Voice mode", "Improved: Startup", "Fixed: Reminders", "Also: a loose line"])
        self.assertEqual(info["sha256"], SHA)

    def test_an_older_server_with_only_a_changelog_still_works(self):
        info = updater._info_from_server({"update_available": True, "version": "v1.4.0", "changelog": ["Fixed a thing"]})
        self.assertEqual((info["version"], info["notes"], info["changelog"]), ("1.4.0", {}, ["Fixed a thing"]))


class Integrity(unittest.TestCase):
    def write(self, data):
        path = os.path.join(tempfile.mkdtemp(), "SEVEN-Setup.exe")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_checks(self):
        self.assertTrue(updater.verify_file(self.write(INSTALLER), SHA)[0])
        self.assertTrue(updater.verify_file(self.write(INSTALLER), "")[0])
        self.assertFalse(updater.verify_file(self.write(INSTALLER), "0" * 64)[0])
        self.assertIn("checksum", updater.verify_file(self.write(INSTALLER), "0" * 64)[1])
        self.assertFalse(updater.verify_file(self.write(b"MZ" + b"\0" * 100), "")[0])                         # too small
        self.assertFalse(updater.verify_file(self.write(b"<html>" + b" " * updater.MIN_INSTALLER_BYTES), "")[0])   # an error page
        self.assertFalse(updater.verify_file(os.path.join(tempfile.gettempdir(), "no-such-file.exe"), "")[0])


class Checking(UpdaterTest):
    def run_check(self, get):
        updater._state["last_checked"] = None
        with mock.patch.object(updater.requests, "get", side_effect=get):
            updater.check_for_updates(force=True)
            wait_for_check()
        return updater.get_state()

    def test_the_render_answer_is_trusted(self):
        calls = []

        def get(url, **kw):
            calls.append(url)
            return Resp(200, SERVER_UPDATE) if "onrender" in url else Resp(200, GITHUB_RELEASE)

        state = self.run_check(get)
        self.assertTrue(state["update_available"])
        self.assertEqual(state["info"]["version"], "1.4.0")
        self.assertEqual(state["info"]["source"], "server")
        self.assertEqual(len(calls), 1)

    def test_a_withdrawn_release_is_not_taken_from_github(self):
        calls = []

        def get(url, **kw):
            calls.append(url)
            return Resp(200, {"update_available": False}) if "onrender" in url else Resp(200, GITHUB_RELEASE)

        state = self.run_check(get)
        self.assertFalse(state["update_available"])
        self.assertEqual([("onrender" in c) for c in calls], [True])
        self.assertFalse(state["check_failed"])

    def test_it_waits_for_a_sleeping_server(self):
        answers = iter([requests.exceptions.Timeout(), Resp(503), Resp(200, SERVER_UPDATE)])

        def get(url, **kw):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a

        state = self.run_check(get)
        self.assertEqual(state["info"]["source"], "server")

    def test_github_is_used_only_when_render_cannot_be_reached(self):
        def get(url, **kw):
            if "onrender" in url:
                raise requests.exceptions.ConnectionError()
            return Resp(200, GITHUB_RELEASE)

        state = self.run_check(get)
        self.assertTrue(state["update_available"])
        self.assertEqual(state["info"]["source"], "github")
        self.assertEqual(state["info"]["sha256"], SHA)
        self.assertEqual(state["info"]["notes"], {"new": ["Voice mode"], "fixed": ["Reminders"]})
        self.assertEqual(state["info"]["summary"], "A calmer, faster Seven.")
        self.assertFalse(state["info"]["is_critical"])

    def test_critical_needs_the_marker_not_just_the_word(self):
        loose = dict(GITHUB_RELEASE, body="This is not a critical change, just polish.")
        marked = dict(GITHUB_RELEASE, body="[critical] Fixes a security problem.")
        for release, expected in ((loose, False), (marked, True)):
            def get(url, **kw):
                if "onrender" in url:
                    raise requests.exceptions.ConnectionError()
                return Resp(200, release)
            self.assertEqual(self.run_check(get)["info"]["is_critical"], expected)

    def test_offline_is_reported_not_called_up_to_date(self):
        def get(url, **kw):
            raise requests.exceptions.ConnectionError()
        state = self.run_check(get)
        self.assertTrue(state["check_failed"])
        self.assertFalse(state["update_available"])

    def test_the_automatic_switch_is_honoured(self):
        import config
        for value, expected in ((False, False), (True, True)):
            with mock.patch.dict(config.KEY, {"updates": {"auto_check": value}}):
                self.assertEqual(updater._auto_enabled(), expected)

    def test_withdrawing_after_a_download_clears_it(self):
        path = os.path.join(tempfile.mkdtemp(), "SEVEN-Setup-1.4.0.exe")
        with open(path, "wb") as f:
            f.write(INSTALLER)
        updater._state.update(update_available=True, download_path=path, download_progress=100, info={"version": "1.4.0"})
        self.run_check(lambda url, **kw: Resp(200, {"update_available": False}))
        self.assertFalse(os.path.exists(path))
        self.assertIsNone(updater.get_state()["download_path"])


class Downloading(UpdaterTest):
    def prepare(self, **info):
        base = dict(version="9.9.9", download_url="https://github.com/x/y/SEVEN-Setup-9.9.9.exe", sha256=SHA)
        base.update(info)
        updater._state["info"] = base
        self.dest = os.path.join(tempfile.gettempdir(), "SEVEN-Setup-9.9.9.exe")
        for p in (self.dest, self.dest + ".part"):
            if os.path.exists(p):
                os.remove(p)

    def chunks(self, data, total=None):
        parts = [data[i:i + 65536] for i in range(0, len(data), 65536)]
        return Resp(200, chunks=parts, headers={"content-length": str(len(data) if total is None else total)})

    def test_a_good_download_is_kept(self):
        self.prepare()
        with mock.patch.object(updater.requests, "get", return_value=self.chunks(INSTALLER)):
            ok, path, err = updater.download_update()
        self.assertTrue(ok, err)
        self.assertEqual(updater.get_state()["download_progress"], 100)
        self.assertTrue(os.path.exists(path))
        self.assertFalse(os.path.exists(path + ".part"))
        self.assertTrue(updater.verify_downloaded()[0])

    def test_a_download_with_the_wrong_checksum_is_thrown_away(self):
        self.prepare(sha256="1" * 64)
        with mock.patch.object(updater.requests, "get", return_value=self.chunks(INSTALLER)) as get:
            ok, _, _ = updater.download_update()
        self.assertFalse(ok)
        self.assertEqual(get.call_count, updater.DOWNLOAD_ATTEMPTS)
        self.assertFalse(os.path.exists(self.dest))
        self.assertFalse(os.path.exists(self.dest + ".part"))
        self.assertIn("checksum", updater.get_state()["error"])
        self.assertFalse(updater.get_state()["downloading"])

    def test_a_cut_connection_is_retried_then_reported_plainly(self):
        self.prepare()
        with mock.patch.object(updater.requests, "get", return_value=self.chunks(INSTALLER, total=len(INSTALLER) + 500)):
            ok, _, _ = updater.download_update()
        self.assertFalse(ok)
        self.assertIn("did not finish", updater.get_state()["error"])
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_a_flaky_connection_succeeds_on_the_second_try(self):
        self.prepare()
        answers = iter([requests.exceptions.ConnectionError(), self.chunks(INSTALLER)])

        def get(url, **kw):
            a = next(answers)
            if isinstance(a, Exception):
                raise a
            return a

        with mock.patch.object(updater.requests, "get", side_effect=get):
            ok, _, err = updater.download_update()
        self.assertTrue(ok, err)

    def test_an_insecure_link_is_refused(self):
        self.prepare(download_url="http://github.com/x/y/SEVEN-Setup-9.9.9.exe")
        with mock.patch.object(updater.requests, "get") as get:
            ok, _, _ = updater.download_update()
        self.assertFalse(ok)
        get.assert_not_called()

    def test_a_tampered_file_is_refused_at_install_time(self):
        self.prepare()
        with open(self.dest, "wb") as f:
            f.write(INSTALLER[:-1] + b"X")
        updater._state["download_path"] = self.dest
        self.assertFalse(updater.verify_downloaded()[0])

    def test_an_already_verified_download_is_reused(self):
        self.prepare()
        with open(self.dest, "wb") as f:
            f.write(INSTALLER)
        with mock.patch.object(updater.requests, "get") as get:
            ok, path, _ = updater.download_update()
        self.assertTrue(ok)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
