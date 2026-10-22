"""Multi-turn evaluations of the reported failures: facts, corrections, history, references, goals, new chats."""
from support import BrainTest, LLM_CALLS, brain, facts_store, learning_store, conversation_store, config  # noqa: F401


class Timeline(BrainTest):
    def setUp(self):
        super().setUp()
        self.ask("Remember that my favorite programming language is Python.")
        self.ask("Actually, I prefer JavaScript over Python. Remember that.")

    def test_current_and_previous(self):
        r = self.ask("Which programming language do I prefer now, and what did I prefer before?")
        self.assertIn("JavaScript", r)
        self.assertIn("Python", r)
        self.assertLess(r.index("JavaScript"), r.index("Python"))
        self.assertEqual(self.ask("what is my favorite programming language"), "JavaScript.")

    def test_provenance_is_attributed_correctly(self):
        self.ask("Which programming language do I prefer now?")
        r = self.ask("How do you know that, and when did I tell you?")
        self.assertIn("first told me Python", r)
        self.assertIn("changed it to JavaScript", r)
        self.assertNotIn("first told me JavaScript", r)
        self.assertIn("not from a guess", r)

    def test_unknown_reason_is_never_invented(self):
        r = self.ask("Why did I choose that language?")
        self.assertIn("haven't told me why", r)
        self.assertEqual(LLM_CALLS, [])
        for banned in ("data science", "libraries", "because it is", "clean"):
            self.assertNotIn(banned, r.lower())

    def test_reason_given_later_is_remembered_and_not_confused_with_a_fact(self):
        self.ask("Why did I choose that language?")
        self.ask("because it runs in the browser and on servers")
        self.assertIn("runs in the browser", self.ask("Why did I choose that language?"))

    def test_a_new_fact_is_not_swallowed_as_the_answer_to_a_why(self):
        self.ask("Why did I choose that language?")
        self.ask("Actually, I prefer TypeScript over JavaScript. Remember that.")
        self.assertNotIn("TypeScript", self.ask("Why did I choose JavaScript?"))

    def test_history_survives_new_chat_and_restart(self):
        new = brain.new_conversation()
        self.assertNotEqual(new, self.conv)
        q = "Which programming language do I prefer now, and what did I prefer before?"
        self.assertIn("Python", self.ask(q, conv=new))
        # simulate an application restart: all in-memory state gone, databases remain
        from brain_modules import chat_history, conversation_state, learning
        conversation_state.reset(); chat_history.clear(); learning.clear_cache()
        self.assertIn("Python", self.ask(q, conv=new))

    def test_unknown_slot_never_borrows_another_slots_history(self):
        self.assertIn("don't have an earlier value", self.ask("what did I prefer before for framework"))


class Unchanged(BrainTest):
    def test_never_changed_fact_says_so(self):
        self.ask("Remember that my favorite framework is React.")
        self.assertIn("hasn't changed", self.ask("what did I prefer before for framework"))


class References(BrainTest):
    def test_that_movie_resolves_and_is_a_preference_not_a_favorite(self):
        self.ask("What about Interstellar?")
        self.ask("I love that movie.")
        self.assertIn("refers to Interstellar", self.llm_user_message())
        self.assertIn("Acknowledge it naturally", self.llm_user_message())
        self.assertIsNone(facts_store.get_active_by_key("default", "favorite_movie"))
        self.assertEqual(self.ask("What movie do I love?"), "You've told me you love Interstellar.")

    def test_favorite_is_not_assumed_but_can_be_confirmed(self):
        self.ask("What about Interstellar?")
        self.ask("I love that movie.")
        r = self.ask("Do you know what's my favorite movie?")
        self.assertIn("haven't told me a favorite movie", r)
        self.assertIn("Interstellar", r)
        self.assertIn("Is that your favorite", r)
        self.ask("yes")
        self.assertEqual(self.ask("what is my favorite movie"), "Interstellar.")

    def test_ambiguous_reference_asks(self):
        self.ask("Compare Inception and Interstellar for me")
        self.ask("hello there friend")
        r = self.ask("I love that movie.")
        self.assertRegex(r, r"Do you mean .*(Inception|Interstellar)")

    def test_follow_up_keeps_subject_in_the_same_chat_only(self):
        self.ask("What about Interstellar?")
        new = brain.new_conversation()
        self.ask("I love that movie.", conv=new)
        self.assertNotIn("refers to Interstellar", self.llm_user_message())


class Goals(BrainTest):
    def test_goal_is_understood_and_used(self):
        self.ask("I'm building a personal AI assistant called SEVEN.")
        self.assertIn("what they are trying to achieve", self.llm_user_message())
        self.assertIn("working on", self.ask("what am I working on"))
        self.ask("how should I structure the memory part of my assistant project?")
        self.assertIn("<user_goals>", self.llm_user_message())

    def test_goal_lifecycle(self):
        self.ask("I need to finish the report by Friday.")
        self.assertIn("marked", self.ask("I finished the report"))
        self.assertIn("haven't told me about any goals", self.ask("what are my goals"))


class Compound(BrainTest):
    def test_name_plus_facts_plus_goal_in_one_message(self):
        r = self.ask("My name is 77. Remember that my favorite programming language is Python, and I'm building "
                     "a personal AI assistant called SEVEN.")
        self.assertIn("77 it is", r)
        self.assertEqual(self.ask("what is my favorite programming language"), "Python.")
        self.assertIn("SEVEN", self.ask("what am I working on"))
        self.assertIn("77", self.ask("who am i"))


class NewChat(BrainTest):
    def test_new_chat_isolation_and_persistence(self):
        self.ask("explain how a hash map works")
        old = self.conv
        new = brain.new_conversation()
        self.assertNotEqual(old, new)
        self.ask("hello there my friend how are you today", conv=new)
        sent = [m["content"] for m in LLM_CALLS[-1]["messages"] if m["role"] == "user"]
        self.assertFalse(any("hash map" in s for s in sent))
        self.assertEqual(len(conversation_store.get_messages(old)), 2)
        self.assertTrue(conversation_store.get_conversation(new))

    def test_other_conversations_are_retrievable_when_asked(self):
        self.ask("I am planning a trip to Lisbon in March with my sister")
        new = brain.new_conversation()
        self.ask("last time I told you about a trip, where was it", conv=new)
        self.assertIn("From an earlier chat", self.llm_user_message())
        self.assertIn("not verified truth", self.llm_user_message())
