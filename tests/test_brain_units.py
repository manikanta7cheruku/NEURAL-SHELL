"""
Unit tests for the pure brain modules. No Ollama, no ChromaDB needed.

Run from the repository root:
    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["SEVEN_DISABLE_CHROMA"] = "1"
_TMP = tempfile.mkdtemp(prefix="seven_test_")
os.environ["APPDATA"] = _TMP
os.environ["SEVEN_FACTS_DB"] = os.path.join(_TMP, "facts.db")

from brain_modules import (correction_detector, fact_extractor, memory_gate,  # noqa: E402
                           response_filter, social_engine, speech_acts)


class SpeechActs(unittest.TestCase):
    def test_normalize_expands_contractions(self):
        self.assertEqual(speech_acts.normalize("What's the time?"), "what is the time")
        self.assertEqual(speech_acts.normalize("whats up"), "what is up")

    def test_greeting_is_whole_utterance(self):
        for ok in ("hey", "Hello there", "hiii", "good morning", "yo seven"):
            self.assertTrue(speech_acts.is_greeting(speech_acts.normalize(ok)), ok)
        for no in ("history of rome", "this is a test", "hey open chrome", "good idea"):
            self.assertFalse(speech_acts.is_greeting(speech_acts.normalize(no)), no)

    def test_whole_word_phrase(self):
        self.assertFalse(speech_acts.has_phrase("history of rome", "hi"))
        self.assertTrue(speech_acts.has_phrase("say hi to me", "hi"))


class Extractor(unittest.TestCase):
    def facts(self, text):
        return [(f.key, f.value, f.text) for f in fact_extractor.extract_facts(text)]

    def test_explicit_remember_is_clean(self):
        self.assertEqual(self.facts("Remember that my favorite framework is React."),
                         [("favorite_framework", "React", "User's favorite framework is React")])

    def test_questions_never_become_facts(self):
        for q in ("Who created you and what is your name?", "What is my favorite framework?",
                  "do you know my name", "what is your name", "remember what I said?"):
            self.assertEqual(self.facts(q), [], q)

    def test_poisoned_name_is_rejected(self):
        self.assertIsNone(fact_extractor.valid_name("What You"))
        self.assertIsNone(fact_extractor.valid_name("You"))
        self.assertEqual(fact_extractor.valid_name("mani"), "Mani")

    def test_passing_states_are_not_stored(self):
        for t in ("my code is broken", "I'm a bit tired", "my head is hurting", "I love you"):
            self.assertEqual(self.facts(t), [], t)

    def test_stable_statements_are_stored(self):
        self.assertEqual(self.facts("I live in Hyderabad")[0][0], "city")
        self.assertEqual(self.facts("I'm a software engineer")[0][0], "role")
        self.assertEqual(self.facts("I love pizza")[0][0], "likes:pizza")

    def test_remember_to_is_not_a_fact(self):
        self.assertEqual(self.facts("Remember to call mom"), [])

    def test_polite_request_with_question_mark(self):
        self.assertEqual(self.facts("can you remember that I prefer dark mode?")[0][0], "likes:dark_mode")

    def test_legacy_text_detection(self):
        self.assertFalse(fact_extractor.is_clean_fact_text("User said: remember that my name is x"))
        self.assertFalse(fact_extractor.is_clean_fact_text("User's name is What You"))
        self.assertTrue(fact_extractor.is_clean_fact_text("User's favorite framework is React"))


class Gate(unittest.TestCase):
    def test_recall_parsing(self):
        q = memory_gate.parse_recall_query("what is my favorite framework")
        self.assertEqual((q.kind, q.key), ("attr", "favorite_framework"))
        self.assertEqual(memory_gate.parse_recall_query("what do i like").kind, "likes")
        self.assertIsNone(memory_gate.parse_recall_query("what is my name"))
        self.assertIsNone(memory_gate.parse_recall_query("what is wrong with my code"))

    def test_gate_skips_general_questions(self):
        for t in ("what is react", "how does a neural network train", "what is a business model"):
            self.assertFalse(memory_gate.should_search_memory(speech_acts.normalize(t), t), t)
        self.assertTrue(memory_gate.should_search_memory(
            speech_acts.normalize("recommend a framework for my project"), "recommend a framework for my project"))

    def test_live_topic_uses_whole_words(self):
        self.assertEqual(memory_gate.live_topic("what is the weather in rio"), "weather")
        self.assertIsNone(memory_gate.live_topic("how does a neural network train"))
        self.assertIsNone(memory_gate.live_topic("what is the boiling temperature of water"))


class Corrections(unittest.TestCase):
    def test_not_x_its_y(self):
        c = correction_detector.detect_correction("Actually it's Vue, not React")
        self.assertEqual((c["old_value"], c["new_value"]), ("React", "Vue"))

    def test_meant_values_are_not_reversed(self):
        c = correction_detector.detect_correction("I meant Chrome, not Firefox")
        self.assertEqual((c["old_value"], c["new_value"]), ("Firefox", "Chrome"))

    def test_ordinary_negation_is_not_a_correction(self):
        self.assertIsNone(correction_detector.detect_correction("I do not like pizza"))
        self.assertIsNone(correction_detector.detect_correction("actually, what's the weather?"))


class Social(unittest.TestCase):
    def setUp(self):
        social_engine.reset()
        social_engine.seed(7)

    def test_four_hellos_escalate(self):
        replies = [social_engine.respond("k", "hello", "", now=1000 + i, hour=14) for i in range(4)]
        self.assertTrue(all(replies))
        self.assertLess(len(replies[2]), len(replies[0]) + 10)
        self.assertRegex(replies[3].lower(), r"real|actually|topic|work on")
        self.assertEqual(len(set(replies)), 4)

    def test_non_social_resets_streak(self):
        social_engine.respond("k", "hello", "", now=1, hour=10)
        self.assertIsNone(social_engine.respond("k", "open chrome", "", now=2, hour=10))
        self.assertIn(social_engine.respond("k", "hello", "", now=3, hour=10).split()[0], ("Hey.", "Hey,", "Yo.", "Morning."))

    def test_never_mentions_memory(self):
        for _ in range(30):
            r = social_engine.respond("z", "hey", "Mani", now=10_000 + _ * 700, hour=9)
            for banned in ("rio", "7777", "react", "port", "weather"):
                self.assertNotIn(banned, r.lower())


class Filters(unittest.TestCase):
    def _run(self, tokens):
        s, out = response_filter.StreamSanitizer(), []
        for t in tokens:
            out.append(s.feed(t))
            if s.stopped:
                break
        out.append(s.flush())
        return "".join(out)

    def test_role_prefix_and_action_tags_removed(self):
        self.assertEqual(self._run(["Sev", "en: ", "Opening it now. ", "###OPE", "N: chrome"]).strip(),
                         "Opening it now.")

    def test_split_hash_across_tokens(self):
        self.assertEqual(self._run(["Done with that one. #", "##OPEN: x"]).strip(), "Done with that one.")

    def test_echoed_tags_removed(self):
        out = self._run(["Sure, here you go <reference_only>", " ok"])
        self.assertNotIn("<reference_only>", out)
        self.assertIn("here you go", out)

    def test_chunker_sentences_and_abbreviations(self):
        c = response_filter.SentenceChunker()
        got = c.feed("Dr. Smith is here. It is 3.14 today. Fine ") + c.flush()
        self.assertEqual(got[0], "Dr. Smith is here.")
        self.assertEqual(got[1], "It is 3.14 today.")

    def test_trailer_filler_detected(self):
        self.assertTrue(response_filter.is_trailer("Is there anything else?"))
        self.assertFalse(response_filter.is_trailer("Python is better for beginners."))


if __name__ == "__main__":
    unittest.main()
