"""
The update scripts are run for real (Windows PowerShell, a throwaway install folder), because the failures that matter
only happen when files are replaced: a changed-files update that checks and backs up what it copies, puts the old files
back when something is wrong, and a full update that waits for the installer and reports what really happened.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

import support  # noqa: F401  (sets up paths and test mode)
from backend import update_install, update_package

POWERSHELL = shutil.which("powershell.exe")


def write(root, rel, text):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Packages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old, self.new = os.path.join(self.tmp, "old"), os.path.join(self.tmp, "new")
        for root, version in ((self.old, "1.3.3"), (self.new, "1.3.4")):
            write(root, "resources/app/version.txt", version)
            write(root, "resources/app/backend/same.py", "print('same')")
        write(self.old, "resources/app/backend/changed.py", "old")
        write(self.new, "resources/app/backend/changed.py", "new code")
        write(self.old, "resources/app/backend/gone.py", "bye")
        write(self.new, "resources/app/backend/added.py", "hello")
        write(self.new, "resources/app/backend/__pycache__/x.pyc", "cache")      # never part of a release
        self.m_old = update_package.build_manifest(self.old, "1.3.3")
        self.m_new = update_package.build_manifest(self.new, "1.3.4")

    def test_a_patch_carries_only_what_changed_and_what_went_away(self):
        changed, removed = update_package.diff(self.m_old, self.m_new)
        self.assertEqual(changed, ["resources/app/backend/added.py", "resources/app/backend/changed.py", "resources/app/version.txt"])
        self.assertEqual(removed, ["resources/app/backend/gone.py"])
        meta = update_package.build_patch(self.new, self.m_old, self.m_new, os.path.join(self.tmp, "p.zip"))
        self.assertEqual((meta["from"], meta["to"], meta["files"], meta["removed"]), ("1.3.3", "1.3.4", 3, 1))
        with zipfile.ZipFile(os.path.join(self.tmp, "p.zip")) as z:
            self.assertNotIn("files/resources/app/backend/same.py", z.namelist())

    def test_a_patch_is_proven_before_it_is_used(self):
        meta = update_package.build_patch(self.new, self.m_old, self.m_new, os.path.join(self.tmp, "p.zip"))
        stage = os.path.join(self.tmp, "stage")
        self.assertEqual(update_package.extract_and_verify(os.path.join(self.tmp, "p.zip"), stage, meta["sha256"])["to"], "1.3.4")
        with self.assertRaises(ValueError):                                    # a wrong published checksum
            update_package.extract_and_verify(os.path.join(self.tmp, "p.zip"), stage, "0" * 64)
        with zipfile.ZipFile(os.path.join(self.tmp, "p.zip")) as z, zipfile.ZipFile(os.path.join(self.tmp, "bad.zip"), "w") as out:
            for name in z.namelist():                                          # one file changed after the patch was built
                out.writestr(name, b"tampered" if name.endswith("changed.py") else z.read(name))
        with self.assertRaises(ValueError) as caught:
            update_package.extract_and_verify(os.path.join(self.tmp, "bad.zip"), stage)
        self.assertIn("changed.py", str(caught.exception))

    def test_a_path_that_climbs_out_of_the_folder_is_refused(self):
        with zipfile.ZipFile(os.path.join(self.tmp, "evil.zip"), "w") as z:
            z.writestr("patch.json", json.dumps({"from": "1", "to": "2", "files": {}, "delete": []}))
            z.writestr("files/../../outside.txt", "x")
        with self.assertRaises(ValueError):
            update_package.extract_and_verify(os.path.join(self.tmp, "evil.zip"), os.path.join(self.tmp, "stage"))

    def test_manifests_round_trip_compressed(self):
        path = os.path.join(self.tmp, "m.json.gz")
        update_package.save_manifest(self.m_new, path)
        self.assertEqual(update_package.load_manifest(path), self.m_new)


@unittest.skipUnless(POWERSHELL and sys.platform == "win32", "needs Windows PowerShell")
class Scripts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.appdata = os.path.join(self.tmp, "appdata")
        os.makedirs(self.appdata)
        patcher = mock.patch.dict(os.environ, {"APPDATA": self.appdata})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.install = os.path.join(self.tmp, "Programs", "SEVEN")
        write(self.install, "resources/app/version.txt", "1.3.3")
        write(self.install, "resources/app/backend/changed.py", "old")
        write(self.install, "resources/app/backend/gone.py", "bye")
        shutil.copy(os.path.join(os.environ["SystemRoot"], "System32", "whoami.exe"), os.path.join(self.install, "SEVEN.exe"))

    def run_script(self, text):
        path = os.path.join(self.tmp, "run.ps1")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(text)
        subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path], check=True, timeout=120,
                       capture_output=True)
        return update_install.read_result()

    def read(self, rel):
        with open(os.path.join(self.install, *rel.split("/")), encoding="utf-8") as f:
            return f.read()

    def build_patch(self, tamper=False):
        new = os.path.join(self.tmp, "new")
        write(new, "resources/app/version.txt", "1.3.4")
        write(new, "resources/app/backend/changed.py", "new code")
        write(new, "resources/app/backend/added.py", "hello")
        old = {"version": "1.3.3", "files": {"resources/app/backend/changed.py": ["x", 1], "resources/app/backend/gone.py": ["y", 1],
                                             "resources/app/version.txt": ["z", 1]}}
        manifest = update_package.build_manifest(new, "1.3.4")
        zip_path = os.path.join(self.tmp, "p.zip")
        update_package.build_patch(new, old, manifest, zip_path)
        stage = os.path.join(self.tmp, "stage")
        update_package.extract_and_verify(zip_path, stage)
        if tamper:                                                              # damaged after it was proven, before it was copied
            write(stage, "files/resources/app/backend/added.py", "corrupted")
        return stage, zip_path

    def test_a_patch_replaces_adds_and_removes_checks_and_reports(self):
        stage, zip_path = self.build_patch()
        result = self.run_script(update_install.patch_script(stage, zip_path, self.install, "1.3.3", "1.3.4"))
        self.assertEqual((result["status"], result["to"]), ("ok", "1.3.4"))
        self.assertEqual(self.read("resources/app/version.txt"), "1.3.4")
        self.assertEqual(self.read("resources/app/backend/changed.py"), "new code")
        self.assertEqual(self.read("resources/app/backend/added.py"), "hello")
        self.assertFalse(os.path.exists(os.path.join(self.install, "resources", "app", "backend", "gone.py")))
        self.assertFalse(os.path.exists(stage))                                 # the staged files are cleaned up

    def test_a_patch_that_fails_halfway_puts_every_old_file_back(self):
        stage, zip_path = self.build_patch(tamper=True)
        result = self.run_script(update_install.patch_script(stage, zip_path, self.install, "1.3.3", "1.3.4"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("Nothing was changed", result["detail"])
        self.assertEqual(self.read("resources/app/version.txt"), "1.3.3")      # still the version that worked
        self.assertEqual(self.read("resources/app/backend/changed.py"), "old")
        self.assertEqual(self.read("resources/app/backend/gone.py"), "bye")
        self.assertFalse(os.path.exists(os.path.join(self.install, "resources", "app", "backend", "added.py")))

    def fake_installer(self, version):
        path = os.path.join(self.tmp, "SEVEN-Setup.cmd")
        with open(path, "w") as f:
            f.write(f'@echo off\r\ntimeout /t 1 /nobreak >nul 2>&1\r\n>"{self.install}\\resources\\app\\version.txt" echo {version}\r\nexit /b 0\r\n')
        return path

    def test_a_full_update_waits_for_the_installer_and_checks_the_version_on_disk(self):
        installer = self.fake_installer("1.3.4")
        result = self.run_script(update_install.installer_script(installer, self.install, "1.3.3", "1.3.4"))
        self.assertEqual((result["status"], result["to"]), ("ok", "1.3.4"))
        self.assertFalse(os.path.exists(installer))                            # removed only after it worked

    def test_an_installer_that_leaves_the_old_version_is_reported_as_failed_and_kept_for_a_retry(self):
        installer = self.fake_installer("1.3.3")
        result = self.run_script(update_install.installer_script(installer, self.install, "1.3.3", "1.3.4"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("still 1.3.3", result["detail"])
        self.assertTrue(os.path.exists(installer))
        self.assertTrue(os.path.exists(result["log"]))

    def test_the_install_folder_is_found_from_the_app_path(self):
        with mock.patch.dict(os.environ, {"SEVEN_APP_PATH": os.path.join(self.install, "resources", "app")}):
            self.assertEqual(os.path.normcase(update_install.install_dir()), os.path.normcase(self.install))
        with mock.patch.dict(os.environ, {"SEVEN_APP_PATH": ""}):
            self.assertIsNone(update_install.install_dir())                    # from source: nothing to install into


if __name__ == "__main__":
    unittest.main()
