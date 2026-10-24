"""
Short follow-ups adjust the last action, and everyday questions are understood instead of being misrouted:
"make it 0" after brightness, "make it 70" after transparency, "show chrome", "tell me in a list", "do you know
alphabets", "how can you open these files?".
"""
import unittest

from support import BrainTest, LLM_CALLS


class FollowUps(BrainTest):
    def test_numbers_adjust_the_last_setting(self):
        self.ask("set brightness to 60")
        self.assertIn("action=brightness_set value=0", self.ask("make it 0"))
        self.assertIn("action=brightness_set value=40", self.ask("40"))
        self.assertIn("action=brightness_up", self.ask("a bit more"))
        self.ask("set volume to 30")
        self.assertIn("action=volume_up", self.ask("louder"))

    def test_transparency_follow_up(self):
        self.ask("make seven 50% transparent")
        self.assertIn("opacity=0.70", self.ask("make it 70"))

    def test_follow_ups_expire(self):
        self.ask("set brightness to 60")
        for text in ("Tell me a joke", "What's a good movie", "How are you", "What's new", "Say something"):
            self.ask(text)
        LLM_CALLS.clear()
        self.assertNotIn("###SYS", self.ask("make it 0"))


class Meaning(BrainTest):
    def test_show_an_app_brings_it_forward(self):
        reply = self.ask("show chrome")
        self.assertIn("action=focus target=chrome fallback=open", reply)

    def test_abilities_as_a_list_when_asked(self):
        reply = self.ask("Tell me in a list what you can do")
        self.assertIn("\n- **", reply)

    def test_general_do_you_know_is_not_about_the_user(self):
        self.assertNotIn("Only from what you", self.ask("Do you know alphabets?"))

    def test_how_question_does_not_reopen_files(self):
        self.ask("open my resume")
        self.assertNotEqual(self.ask("How can you open these files?").strip(), "Opened.")

    def test_no_example_conversations_in_the_prompt(self):
        self.ask("Explain recursion simply")
        roles = [m["role"] for m in LLM_CALLS[-1]["messages"]]
        self.assertEqual(roles, ["system", "user"])

    def test_share_with_a_friend(self):
        self.assertIn("Try Seven", self.ask("What should I tell my friend about you"))


if __name__ == "__main__":
    unittest.main()
