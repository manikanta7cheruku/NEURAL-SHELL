"""
The model catalog drives setup, Settings, Automatic selection and the context size; Seven explains its model,
memory, learning and reasoning when asked, from live values.
"""
import unittest

from support import BrainTest, LLM_CALLS
from brain_modules import model_catalog


class Catalog(unittest.TestCase):
    def test_recommendation_follows_hardware(self):
        self.assertEqual(model_catalog.recommend(8, 16, True)["id"], "qwen2.5:7b")
        self.assertEqual(model_catalog.recommend(6, 16, True)["id"], "llama3.2:3b")
        self.assertEqual(model_catalog.recommend(0, 16, False)["id"], "llama3.2:3b")
        self.assertEqual(model_catalog.recommend(0, 8, False)["id"], "llama3.2:1b")

    def test_recommended_model_always_fits(self):
        for vram, ram, gpu in ((8, 16, True), (6, 16, True), (0, 16, False), (0, 8, False), (0, 4, False)):
            rec = model_catalog.get(model_catalog.recommend(vram, ram, gpu)["id"])
            self.assertTrue(model_catalog.fits(rec, vram, ram, gpu), (vram, ram, gpu))

    def test_automatic_picks_the_strongest_installed_model_that_fits(self):
        installed = ["llama3.2:1b", "qwen2.5:7b", "qwen2.5-coder:7b"]
        self.assertEqual(model_catalog.best_installed(installed, 8, 16, True), "qwen2.5:7b")
        self.assertEqual(model_catalog.best_installed(installed, 0, 8, False), "llama3.2:1b")
        self.assertEqual(model_catalog.best_installed(["mistral:latest"], 8, 16, True), "mistral:latest")
        self.assertIsNone(model_catalog.best_installed([], 8, 16, True))

    def test_context_window_per_model(self):
        self.assertEqual(model_catalog.context_window("llama3.2:1b"), 4096)
        self.assertEqual(model_catalog.context_window("qwen2.5:7b"), 8192)
        self.assertEqual(model_catalog.get("llama3.2")["id"], "llama3.2:3b")      # Ollama's default tag
        self.assertEqual(model_catalog.get("qwen2.5:latest")["id"], "qwen2.5:7b")
        self.assertEqual(model_catalog.context_window("someone/custom-13b"), 8192)


class ExplainsItself(BrainTest):
    def test_context_and_memory_are_explained_with_real_numbers(self):
        for q in ("What's your context window?", "How much can you remember?", "Is the context window infinite?"):
            with self.subTest(q=q):
                r = self.ask(q)
                self.assertIn("words at once", r)
                self.assertIn("disk space", r)
        self.assertEqual(LLM_CALLS, [])

    def test_learning_is_explained_honestly(self):
        r = self.ask("Do you learn and evolve?")
        self.assertIn("don't do is retrain the model", r)
        self.assertEqual(LLM_CALLS, [])

    def test_model_details_only_when_asked(self):
        self.ask("Set your model to llama3.2:1b")
        short = self.ask("What model are you using")
        self.assertIn("Llama 3.2 1B", short)
        self.assertNotIn("less suited", short)
        deep = self.ask("What is your model good at?")
        self.assertIn("less suited to", deep)

    def test_why_did_you_say_that_describes_the_real_path(self):
        self.ask("Set brightness to 50")
        self.assertIn("direct command", self.ask("Why did you say that?"))
        self.ask("Explain recursion simply")
        self.assertIn("language model", self.ask("Why did you answer that way?"))

    def test_abilities_are_phrased_by_a_capable_model_and_templated_for_the_smallest(self):
        import config
        config.update_config({"brain": {"model_name": "qwen2.5:7b"}})
        self.ask("What can you do?")
        self.assertIn("<capabilities>", LLM_CALLS[-1]["messages"][-1]["content"])
        config.update_config({"brain": {"model_name": "llama3.2:1b"}})
        LLM_CALLS.clear()
        replies = {self.ask("What can you do?") for _ in range(4)}
        self.assertEqual(LLM_CALLS, [])
        self.assertGreaterEqual(len(replies), 3)            # asked again, worded differently each time

    def test_can_you_answers_are_grammatical(self):
        from brain_modules import capabilities
        capabilities.set_status_override("reminders", "available")    # CI has no Windows scheduler packages
        self.assertIn("I can set one-off or repeating reminders", self.ask("Can you set reminders?"))


if __name__ == "__main__":
    unittest.main()
