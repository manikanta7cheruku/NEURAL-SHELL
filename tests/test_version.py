"""The version every API reports comes from version.txt, cleanly, and the shipped files agree on it."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from seven_utils.version import get_version  # noqa: E402


class Version(unittest.TestCase):
    def test_reads_version_txt_without_byte_order_mark(self):
        with open(os.path.join(ROOT, "version.txt"), encoding="utf-8-sig") as f:
            expected = f.read().strip()
        self.assertEqual(get_version(), expected)
        self.assertNotIn("﻿", get_version())
        self.assertRegex(get_version(), r"^\d+\.\d+\.\d+$")

    def test_status_routes_report_the_version(self):
        try:
            from backend.routes import status
        except Exception:
            self.skipTest("backend.routes.status needs fastapi")
        import time
        import types
        from unittest import mock
        server = types.SimpleNamespace(_state={}, _start_time=time.time())   # not the real server: no ML imports
        with mock.patch.dict(sys.modules, {"backend.api_server": server}):
            self.assertEqual(status.get_version()["version"], get_version())   # used to recurse forever
            self.assertEqual(status.get_status()["version"], get_version())

    def test_no_module_shadows_a_name_it_imports(self):
        """A top-level def with the same name as an import replaces it, so calls hit the def instead."""
        import ast
        import warnings
        warnings.simplefilter("ignore", SyntaxWarning)       # old regex strings in scanned files
        warnings.simplefilter("ignore", DeprecationWarning)
        clashes = []
        for folder in ("backend", "backend/routes", "brain_modules", "memory", "seven_utils"):
            path = os.path.join(ROOT, folder)
            for name in sorted(os.listdir(path)):
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(path, name), encoding="utf-8-sig") as f:
                    tree = ast.parse(f.read())
                imported = {a.asname or a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
                defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                clashes += [f"{folder}/{name}: {n}" for n in sorted(imported & defined)]
        self.assertEqual(clashes, [])

    def test_shipped_version_numbers_agree(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import check_version
        self.assertEqual(check_version.main(), 0)


if __name__ == "__main__":
    unittest.main()
