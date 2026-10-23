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

    def test_shipped_version_numbers_agree(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import check_version
        self.assertEqual(check_version.main(), 0)


if __name__ == "__main__":
    unittest.main()
