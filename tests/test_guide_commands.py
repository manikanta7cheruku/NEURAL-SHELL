"""
Every command the in-app Guide shows must work. The Guide reads its phrases from
frontend/src/guide/guide.json; this test sends each one through the brain and
checks it is handled by an instant layer (not guessed by the language model)
and, when the Guide promises an action, that the reply carries it.
"""
import json
import os
import unittest

from support import BrainTest, LLM_CALLS, ROOT
from brain_modules import command_router

GUIDE = os.path.join(ROOT, "frontend", "src", "guide", "guide.json")


def guide_phrases():
    with open(GUIDE, encoding="utf-8") as f:
        data = json.load(f)
    for item in data["tryIt"]:
        yield item["say"], item.get("expect"), False
        if item.get("undo"):
            yield item["undo"]["say"], None, False
    for group in data["groups"]:
        for ex in group["examples"]:
            yield ex["say"], ex.get("expect"), ex.get("live", False)


class GuideCommands(BrainTest):
    def test_every_guide_phrase_is_understood(self):
        for say, expect, live in guide_phrases():
            if live:
                continue
            with self.subTest(say=say):
                self.setUp()
                reply = self.ask(say)
                self.assertEqual(LLM_CALLS, [], f"{say!r} fell through to the language model")
                self.assertNotEqual(self.trace().get("answered_by"), "layer_08_llm")
                if expect:
                    self.assertIn(f"###{expect}:", reply)


class WindowAndToggleParsing(unittest.TestCase):
    def window(self, text, **flags):
        base = dict(is_desktop_cmd=False, is_notarget_cmd=False, is_layout=False, put_pattern=False,
                    is_switch=False, is_move_monitor=False, is_swap=False, is_window_close=False,
                    is_transparent=False, is_solid=False, is_pin=False, is_unpin=False)
        base.update(flags)
        return command_router._build_window_tag(text, **base)

    def test_snap_keeps_the_whole_app_name(self):
        self.assertEqual(self.window("snap chrome to the left"), "action=snap target=chrome position=left")
        self.assertEqual(self.window("snap code to the right"), "action=snap target=code position=right")

    def test_side_by_side_keeps_multi_word_names_together(self):
        tag = self.window("put chrome and file explorer side by side", is_layout=True)
        self.assertEqual(tag, "action=layout mode=split targets=chrome,file|||explorer")
        self.assertEqual(self.window("quad chrome code notepad explorer", is_layout=True),
                         "action=layout mode=quad targets=chrome,code,notepad,explorer")

    def test_questions_read_the_state_instead_of_changing_it(self):
        self.assertEqual(command_router._build_system_tag("is wifi on"), "action=wifi_status")
        self.assertEqual(command_router._build_system_tag("is bluetooth on"), "action=bluetooth_status")
        self.assertEqual(command_router._build_system_tag("turn on wifi"), "action=wifi_on")
        self.assertEqual(command_router._build_system_tag("turn off bluetooth"), "action=bluetooth_off")


if __name__ == "__main__":
    unittest.main()
