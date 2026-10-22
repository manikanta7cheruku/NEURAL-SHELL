"""The patch script: exact, idempotent, CRLF-safe, and never forces a mismatch."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import apply_patches  # noqa: E402

LICENSE = '"free": {\n  "conversation_history": 7,\n  "facts_limit": 7,\n}\n"pro": {\n  "conversation_history": 77,\n  "facts_limit": 77,\n}\n'
CORE = ('class M:\n    def a(self):\n        try:\n            import voice_limits\n            _tier = voice_limits.get_tier()\n'
        '            _limits = {"free": 7, "pro": 77, "ultimate": -1}\n            _max_allowed = _limits.get(_tier, 7)\n'
        '    def b(self):\n        try:\n            _tier = 1\n            _limits = {"free": 7, "pro": 77, "ultimate": -1}\n'
        '            _max_allowed = _limits.get(_tier, 7)\n')


def make(files, crlf=False):
    root = tempfile.mkdtemp()
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, rel)) or root, exist_ok=True)
        with open(os.path.join(root, rel), "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace("\n", "\r\n") if crlf else text)
    return root


class Patches(unittest.TestCase):
    def read(self, root, rel):
        return open(os.path.join(root, rel), encoding="utf-8", newline="").read()

    def test_dry_run_writes_nothing_and_apply_is_idempotent(self):
        root = make({"license.py": LICENSE, "memory/core.py": CORE})
        apply_patches.run(root, apply=False)
        self.assertEqual(self.read(root, "license.py"), LICENSE)
        apply_patches.run(root, apply=True)
        text = self.read(root, "license.py")
        self.assertNotIn(": 7,", text)
        self.assertEqual(text.count('"conversation_history": -1,'), 2)
        self.assertEqual(self.read(root, "memory/core.py").count("_max_allowed = -1"), 2)
        again = dict(apply_patches.run(root, apply=True))
        self.assertTrue(all(s == "already applied" for s, _ in again["license.py"]))

    def test_crlf_files_stay_crlf(self):
        root = make({"memory/core.py": CORE}, crlf=True)
        apply_patches.run(root, apply=True)
        text = self.read(root, "memory/core.py")
        self.assertIn("\r\n", text)
        self.assertNotIn("\n_", text.replace("\r\n", ""))
        self.assertEqual(text.count("_max_allowed = -1"), 2)

    def test_mismatch_is_reported_and_nothing_is_written(self):
        root = make({"license.py": '"conversation_history": 7,\n"something_else": 1\n'})
        result = dict(apply_patches.run(root, apply=True))
        self.assertTrue(any(s == "NOT FOUND" for s, _ in result["license.py"]))
        self.assertIn('"conversation_history": 7,', self.read(root, "license.py"))

    def test_missing_files_are_reported(self):
        self.assertTrue(any(s == "MISSING FILE" for _f, rep in apply_patches.run(make({}), False) for s, _ in rep))

    def test_gitignore_append(self):
        root = make({".gitignore": "node_modules\n"})
        apply_patches.run(root, apply=True)
        lines = self.read(root, ".gitignore").splitlines()
        self.assertIn("*.db", lines)
        self.assertEqual(lines.count("node_modules"), 1)


if __name__ == "__main__":
    unittest.main()
