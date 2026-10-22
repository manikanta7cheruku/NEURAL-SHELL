"""Runs evals/golden_conversations.json against the brain with a fake model (deterministic steps only)."""
import json
import os

from support import BrainTest, ROOT, brain

GOLDEN = json.load(open(os.path.join(ROOT, "evals", "golden_conversations.json"), encoding="utf-8"))


def _check(test, step, reply):
    low = reply.lower()
    for s in step.get("expect_all", []):
        test.assertIn(s.lower(), low, f'{step["say"]!r} -> {reply!r}')
    if step.get("expect_any"):
        test.assertTrue(any(s.lower() in low for s in step["expect_any"]), f'{step["say"]!r} -> {reply!r}')
    for s in step.get("forbid", []):
        test.assertNotIn(s.lower(), low, f'{step["say"]!r} -> {reply!r}')
    if "max_words" in step:
        test.assertLessEqual(len(reply.split()), step["max_words"])


class Golden(BrainTest):
    def test_golden_conversations(self):
        for conv in GOLDEN:
            with self.subTest(conv["name"]):
                self.setUp()
                if conv.get("web"):
                    self.web(conv["web"])
                cid = self.conv
                for step in conv["steps"]:
                    if step.get("new_chat"):
                        cid = brain.new_conversation()
                    reply = self.ask(step["say"], conv=cid)
                    if step.get("deterministic", True):
                        _check(self, step, reply)
