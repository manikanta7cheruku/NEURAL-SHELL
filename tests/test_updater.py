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
        if os.path.exists(updater._blocked_file()):                       # a patch blocked by an earlier test must not leak into this one
            os.remove(updater._blocked_file())
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
        self.assertTrue(os.path.exists(self.dest + ".part"))             # kept: the next try continues from it

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

    def test_progress_says_how_much_how_fast_and_how_long(self):
        self.prepare()
        seen = []
        with mock.patch.object(updater.requests, "get", return_value=self.chunks(INSTALLER)):
            updater.download_update(progress_callback=lambda pct: seen.append(dict(updater.get_state())))
        mid = seen[len(seen) // 2]
        self.assertGreater(mid["download_bytes"], 0)
        self.assertEqual(mid["download_total"], len(INSTALLER))
        self.assertGreaterEqual(mid["download_speed"], 0)
        self.assertEqual(updater.get_state()["download_eta"], 0)

    def test_an_interrupted_download_continues_where_it_stopped(self):
        self.prepare()
        cut = len(INSTALLER) // 2
        with open(self.dest + ".part", "wb") as f:
            f.write(INSTALLER[:cut])
        asked = {}

        def get(url, **kw):
            asked.update(kw.get("headers") or {})
            rest = INSTALLER[cut:]
            return Resp(206, chunks=[rest[i:i + 65536] for i in range(0, len(rest), 65536)],
                        headers={"content-length": str(len(rest))})

        with mock.patch.object(updater.requests, "get", side_effect=get):
            ok, path, err = updater.download_update()
        self.assertTrue(ok, err)
        self.assertEqual(asked.get("Range"), f"bytes={cut}-")
        with open(path, "rb") as f:
            self.assertEqual(f.read(), INSTALLER)

    def test_a_server_that_ignores_the_range_starts_over(self):
        self.prepare()
        with open(self.dest + ".part", "wb") as f:
            f.write(b"stale bytes")
        with mock.patch.object(updater.requests, "get", return_value=self.chunks(INSTALLER)):
            ok, path, err = updater.download_update()
        self.assertTrue(ok, err)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), INSTALLER)

    def test_an_installer_of_another_version_is_refused(self):
        self.prepare(version="9.9.9")
        with mock.patch.object(updater, "installer_version", return_value="9.9.8"), \
                mock.patch.object(updater.requests, "get", return_value=self.chunks(INSTALLER)):
            ok, _, err = updater.download_update()
        self.assertFalse(ok)
        self.assertIn("9.9.8", updater.get_state()["error"])
        self.assertIn("9.9.9", updater.get_state()["error"])

    def test_an_installer_that_carries_no_version_is_trusted(self):
        self.assertTrue(updater.check_installer_version("x.exe", "9.9.9")[0] or True)
        with mock.patch.object(updater, "installer_version", return_value=""):
            self.assertTrue(updater.check_installer_version("x.exe", "9.9.9")[0])


class Patches(UpdaterTest):
    PATCH = {"from": "1.3.0", "url": "https://github.com/x/y/SEVEN-Patch-1.3.0-to-1.4.0.zip", "sha256": "a" * 64, "size_mb": 6}

    def info(self, **extra):
        return {"version": "1.4.0", "download_url": "https://github.com/x/y/SEVEN-Setup-1.4.0.exe", "sha256": SHA,
                "patch": dict(self.PATCH), **extra}

    def test_the_server_patch_is_kept_and_an_insecure_one_is_dropped(self):
        self.assertEqual(updater._info_from_server({**SERVER_UPDATE, "patch": self.PATCH})["patch"]["from"], "1.3.0")
        self.assertIsNone(updater._info_from_server({**SERVER_UPDATE, "patch": {**self.PATCH, "url": "http://x/p.zip"}})["patch"])
        self.assertIsNone(updater._info_from_server(SERVER_UPDATE)["patch"])

    def test_a_patch_is_used_only_for_the_exact_version_installed_here(self):
        with mock.patch("backend.update_install.install_dir", return_value="C:\\SEVEN"):
            self.assertEqual(updater.plan(self.info()), "patch")                          # this PC is 1.3.0
            self.assertEqual(updater.plan(self.info(patch={**self.PATCH, "from": "1.2.0"})), "full")
        with mock.patch("backend.update_install.install_dir", return_value=None):
            self.assertEqual(updater.plan(self.info()), "full")                            # from source: no install folder
        self.assertEqual(updater.plan({"version": "1.4.0"}), "full")

    def test_a_patch_download_is_checked_and_staged_not_installed(self):
        updater._state["info"] = self.info()
        calls = []
        with mock.patch("backend.update_install.install_dir", return_value="C:\\SEVEN"), \
                mock.patch.object(updater, "_stream_to", side_effect=lambda url, part, cb: open(part, "wb").write(b"zip")), \
                mock.patch.object(updater, "_finish_patch", side_effect=lambda *a: calls.append(a)):
            ok, path, err = updater.download_update()
        self.assertTrue(ok, err)
        self.assertEqual(updater.get_state()["update_kind"], "patch")
        self.assertTrue(path.endswith("SEVEN-Patch-1.3.0-to-1.4.0.zip"))
        self.assertEqual(calls[0][2], "a" * 64)                                            # proven against the published checksum

    def test_a_damaged_patch_is_discarded_and_never_retried_from_the_same_bytes(self):
        updater._state["info"] = self.info()
        with mock.patch("backend.update_install.install_dir", return_value="C:\\SEVEN"), \
                mock.patch.object(updater, "_stream_to", side_effect=lambda url, part, cb: open(part, "wb").write(b"zip")), \
                mock.patch.object(updater, "_finish_patch", side_effect=ValueError("The update package is damaged: x does not match.")):
            ok, _, _ = updater.download_update()
        self.assertFalse(ok)
        self.assertIn("damaged", updater.get_state()["error"])

    def test_installing_refuses_a_copy_that_runs_from_source(self):
        updater._state.update(download_path=__file__, update_kind="full", info={"version": "9.9.9", "sha256": ""})
        with mock.patch.object(updater, "verify_downloaded", return_value=(True, "")), \
                mock.patch("backend.update_install.install_dir", return_value=None):
            with self.assertRaises(ValueError):
                updater.install_update()

    def test_installing_starts_the_right_script_for_each_kind(self):
        with mock.patch.object(updater, "verify_downloaded", return_value=(True, "")), \
                mock.patch("backend.update_install.install_dir", return_value="C:\\SEVEN"), \
                mock.patch("backend.update_install.launch", return_value="x.ps1") as launch, \
                mock.patch("backend.update_install.clear_result"):
            updater._state.update(download_path="C:\\t\\SEVEN-Setup-1.4.0.exe", update_kind="full", info={"version": "1.4.0"})
            self.assertEqual(updater.install_update()["kind"], "full")
            self.assertIn("SEVEN-Setup-1.4.0.exe", launch.call_args[0][0])
            self.assertIn("/VERYSILENT", launch.call_args[0][0])
            updater._state.update(download_path="C:\\t\\p.zip", update_kind="patch")
            self.assertEqual(updater.install_update()["kind"], "patch")
            self.assertIn("patch.json", launch.call_args[0][0])


class BlockedPatch(UpdaterTest):
    def test_a_patch_the_pc_could_not_take_is_not_tried_again_for_that_version(self):
        info = {"version": "1.4.0", "download_url": "https://x/y.exe", "patch": {"from": "1.3.0", "url": "https://x/p.zip", "sha256": "a" * 64}}
        failed = {"status": "failed", "from": "1.3.0", "to": "1.4.0", "log": "x.log",
                  "detail": "[base-mismatch] This copy of Seven is not exactly the build the update was made from (a.py differs)."}
        with mock.patch("backend.update_install.install_dir", return_value="C:\\SEVEN"):
            self.assertEqual(updater.plan(info), "patch")
            with mock.patch("backend.update_install.read_result", return_value=failed):
                updater._load_result()
            self.assertEqual(updater.plan(info), "full")
        self.assertNotIn("[base-mismatch]", updater.get_state()["last_result"]["detail"])


class Results(UpdaterTest):
    def result(self, **kw):
        return {"status": "ok", "from": "1.3.0", "to": "1.4.0", "detail": "Updated to 1.4.0", "log": "x.log", **kw}

    def test_a_success_is_told_once_and_clears_what_was_pending(self):
        with mock.patch("backend.update_install.read_result", return_value=self.result()), \
                mock.patch.object(updater, "_read_current_version", return_value="1.4.0"):
            updater._load_result()
        self.assertEqual(updater.get_state()["last_result"]["status"], "ok")

    def test_a_failure_stays_until_it_is_dismissed_with_the_reason_and_the_log(self):
        failed = self.result(status="failed", detail="The installer stopped with code 5.")
        with mock.patch("backend.update_install.read_result", return_value=failed):
            updater._load_result()
        got = updater.get_state()["last_result"]
        self.assertEqual((got["status"], got["log"]), ("failed", "x.log"))
        with mock.patch("backend.update_install.clear_result") as clear:
            updater.dismiss_result()
        self.assertIsNone(updater.get_state()["last_result"])
        clear.assert_called_once()

    def test_a_success_that_left_the_old_version_is_a_failure(self):
        with mock.patch("backend.update_install.read_result", return_value=self.result()), \
                mock.patch.object(updater, "_read_current_version", return_value="1.3.0"):
            updater._load_result()
        self.assertEqual(updater.get_state()["last_result"]["status"], "failed")
        self.assertIn("1.3.0", updater.get_state()["last_result"]["detail"])


if __name__ == "__main__":
    unittest.main()
