"""
Regressions from real conversations: questions about the user, about Seven,
routing mistakes and reminders that repeat every few minutes or hours.
"""
import unittest
from datetime import datetime, timedelta

from support import BrainTest, LLM_CALLS
import brain
from brain_modules import command_router, conversation_state, curiosity, prompt_builder


class AboutTheUser(BrainTest):
    def setUp(self):
        super().setUp()
        brain.USER_NAME = "77"

    def teach(self):
        for s in ("My favorite programming language is Python", "I live in Hyderabad",
                  "I'm building a personal AI assistant called SEVEN"):
            self.ask(s)
        LLM_CALLS.clear()

    def test_what_do_you_know_lists_only_stored_evidence(self):
        self.teach()
        for q in ("What do you know about me?", "Tell me about me", "Just tell me everything",
                  "what do you remember about me"):
            with self.subTest(q=q):
                r = self.ask(q)
                self.assertIn("Your name is 77.", r)
                self.assertIn("You live in Hyderabad.", r)
                self.assertIn("Your favorite programming language is Python.", r)
                self.assertIn("You're building a personal AI assistant called SEVEN.", r)
        self.assertEqual(LLM_CALLS, [], "the model must never describe the user")

    def test_nothing_known_is_said_honestly(self):
        r = self.ask("What do you know about me?")
        self.assertIn("77", r)
        self.assertIn("haven't told me anything else", r)
        self.assertNotIn("years old", r)
        self.assertEqual(LLM_CALLS, [])

    def test_how_do_you_know_points_to_the_users_own_words(self):
        self.teach()
        r = self.ask("How do you know all these things about me?")
        self.assertIn("what you've told me", r)
        self.assertEqual(LLM_CALLS, [])

    def test_shorter_favorite_updates_the_same_slot(self):
        self.ask("My favorite programming language is Python")
        self.ask("Actually my favorite language is JavaScript")
        self.assertEqual(self.ask("what is my favorite programming language"), "JavaScript.")
        self.assertIn("Python", self.ask("what did i prefer before"))

    def test_name_is_a_name_not_an_age(self):
        system = prompt_builder.build_system_prompt(speaker_name="77")
        self.assertIn("says nothing about their age", system)
        self.assertIn("Never describe the user's age", system)


class AboutSeven(BrainTest):
    def test_why_use_seven(self):
        r = self.ask("Why should people use seven?")
        self.assertIn("this PC", r)
        self.assertEqual(LLM_CALLS, [])

    def test_what_represents_seven(self):
        self.assertIn("orb", self.ask("I mean what represents you?"))
        self.assertEqual(LLM_CALLS, [])

    def test_what_are_you_says_what_seven_does(self):
        self.assertIn("layer between you and your computer", self.ask("What are you?"))
        self.assertIn("Seven Labs", self.ask("Who created you?"))

    def test_where_is_my_data(self):
        r = self.ask("Where is my data stored")
        self.assertIn("this computer", r)
        self.assertNotIn("I don't know your data", r)


class Routing(BrainTest):
    def test_switch_to_focuses_the_window(self):
        self.assertIn("###WINDOW: action=focus target=chrome", self.ask("Switch to Chrome"))

    def test_restoring_a_workspace_still_works(self):
        r = self.ask("Switch to workspace Focus")
        self.assertIn("workspace", r.lower())
        self.assertNotIn("###WINDOW", r)

    def test_reminders_every_hour_and_every_n_minutes(self):
        def tag(text):
            return command_router._build_sched_tag(text, text.split())
        self.assertEqual(tag("remind me to drink water every hour"),
                         "action=reminder time=in_60_minutes message=drink_water recur=interval_60")
        self.assertIn("recur=interval_30", tag("remind me to stretch every 30 minutes"))
        self.assertIn("recur=interval_120", tag("remind me to check mail every 2 hours"))

    def test_interval_recurrence_moves_forward(self):
        try:
            from hands import scheduler
        except ImportError:
            self.skipTest("hands needs the Windows automation packages")
        self.assertEqual(scheduler._parse_recurrence("interval_60"), "interval_60")
        past = (datetime.now() - timedelta(minutes=150)).replace(microsecond=0)
        nxt = scheduler._next_recurrence({"recur": "interval_60", "time": past.isoformat()})
        self.assertGreater(nxt, datetime.now())
        self.assertLessEqual(nxt - datetime.now(), timedelta(minutes=60))


class Conversation(unittest.TestCase):
    def test_sentence_starters_are_not_topics(self):
        names = [n for n, _k in conversation_state.extract_entities("All of this sounds great. Just tell me more")]
        self.assertNotIn("All", names)
        self.assertNotIn("Just", names)
        names = [n for n, _k in conversation_state.extract_entities("I watched Interstellar again")]
        self.assertIn("Interstellar", names)

    def test_goal_questions_are_grammatical(self):
        self.assertEqual(curiosity._gerund("build a personal AI assistant"), "building a personal AI assistant")
        self.assertEqual(curiosity._gerund("finish the report"), "finishing the report")
        self.assertEqual(curiosity._gerund("get fit"), "getting fit")
        self.assertEqual(curiosity._gerund("the big launch"), "the big launch")


if __name__ == "__main__":
    unittest.main()
