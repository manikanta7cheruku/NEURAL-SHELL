"""
One Seven account per PC: setup finds what an earlier user left, and starting fresh backs it up before clearing.
"""
import os
import tempfile

from support import BrainTest
from backend import account
from knowledge import store


class ReturningUser(BrainTest):
    def test_clean_pc_has_no_account(self):
        store.clear()
        self.assertFalse(account.existing()["found"])

    def test_earlier_user_is_found_and_start_fresh_backs_up_first(self):
        self.ask("Remember that my favourite subject is physics")
        path = os.path.join(tempfile.mkdtemp(), "notes.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Newton's second law: force equals mass times acceleration.")
        store.wait(store.add(path)["id"])

        found = account.existing()
        self.assertTrue(found["found"])
        self.assertEqual(found["source"], "this_pc")
        self.assertGreaterEqual(found["local"]["documents"], 1)

        result = account.start_fresh()
        self.assertTrue(os.path.isdir(result["backup"]))
        self.assertTrue(os.path.isdir(os.path.join(result["backup"], "knowledge")))
        after = account.local_footprint()
        self.assertEqual((after["documents"], after["facts"], after["conversations"]), (0, 0, 0))
