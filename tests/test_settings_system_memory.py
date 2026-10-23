"""
Seven can change its own settings by chat, answers questions about the user's machine from live
readings, and the Memory page edits the same memory the brain recalls from.
"""
import unittest

from support import BrainTest, LLM_CALLS, config
import brain
from brain_modules import brain_settings, settings_control, system_info
from memory import conversation_store, fact_service, facts_store

FAKE_PC = {
    "cpu": "AMD Ryzen 7 7840HS", "cores": 8, "threads": 16, "cpu_load": 12,
    "os": "Windows 11 Home (version 24H2, build 26100)", "host": "test-pc", "gpus": ["NVIDIA GeForce RTX 4060"],
    "gpu": {"name": "NVIDIA GeForce RTX 4060", "vram_gb": 8.0, "vram_used_gb": 1.5, "load": 3, "temp_c": 44},
    "ram": {"total_gb": 32.0, "used_gb": 12.5, "free_gb": 19.5, "percent": 39},
    "disks": [{"drive": "C:", "total_gb": 953, "free_gb": 410, "percent": 57}],
    "uptime_s": 3 * 3600 + 25 * 60,
}


class SettingsByChat(BrainTest):
    def setUp(self):
        super().setUp()
        settings_control.set_model_lister(lambda: ["llama3.2:3b", "mistral:7b"])
        self.addCleanup(settings_control.set_model_lister, None)

    def setting(self, path):
        return brain_settings.get_effective(config, path)

    def test_set_honesty_saves_and_confirms(self):
        r = self.ask("set honesty to 75%")
        self.assertEqual(self.setting("brain.tars_honesty"), 75)
        self.assertIn("Honesty is now 75%", r)
        self.assertEqual(self.trace()["answered_by"], "layer_034_settings")

    def test_phrasings_for_the_same_change(self):
        for phrase, value in [("Set your honesty to 60 percent.", 60), ("make your humor 40", 40),
                              ("can you set humor to 55?", 55)]:
            with self.subTest(phrase=phrase):
                self.ask(phrase)
                path = "brain.tars_humor" if "humor" in phrase else "brain.tars_honesty"
                self.assertEqual(self.setting(path), value)

    def test_relative_changes(self):
        self.ask("set honesty to 50")
        self.ask("be a bit more honest")
        self.assertEqual(self.setting("brain.tars_honesty"), 60)
        self.ask("lower your honesty by 25")
        self.assertEqual(self.setting("brain.tars_honesty"), 35)

    def test_out_of_range_is_clamped_and_explained(self):
        r = self.ask("set honesty to 150")
        self.assertEqual(self.setting("brain.tars_honesty"), 100)
        self.assertIn("maximum is 100", r)

    def test_toggles_and_queries(self):
        self.ask("turn off streaming")
        self.assertFalse(self.setting("brain.streaming"))
        self.assertIn("off", self.ask("is streaming on"))
        self.ask("disable web search")
        self.assertFalse(self.setting("web.enabled"))
        self.ask("turn on web search")
        self.assertTrue(self.setting("web.enabled"))

    def test_temperature_scales(self):
        self.ask("set your temperature to 0.5")
        self.assertEqual(self.setting("brain.temperature"), 0.5)
        self.ask("change temperature to 70%")
        self.assertEqual(self.setting("brain.temperature"), 0.7)

    def test_model_switch_checks_installed_models_and_applies_next_message(self):
        r = self.ask("switch your model to gpt5")
        self.assertIn("can't find gpt5", r)
        self.assertEqual(self.setting("brain.model_name"), "auto")
        self.ask("switch your model to llama3.2")
        self.assertEqual(self.setting("brain.model_name"), "llama3.2:3b")
        self.assertEqual(brain.current_model(), "llama3.2:3b")

    def test_real_phrasings_from_user_testing(self):
        """Typos and follow-ups from real chats that used to reach the model and fail."""
        self.ask("set honesty to 60")
        for phrase in ("what is you honest percentage?", "what's you're honesty percentage?", "how honest are you",
                       "honesty level?"):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.ask(phrase), "Honesty is 60% (direct).")
        self.assertEqual(self.ask("just tell me the number"), "Honesty is 60% (direct).")
        self.assertIn("Humor is", self.ask("how funny are you right now"))

    def test_summary(self):
        r = self.ask("what are your settings")
        for label in ("Honesty", "Humor", "Temperature", "Streaming", "Web search"):
            self.assertIn(label, r)

    def test_not_settings_requests_pass_through(self):
        before = brain_settings.effective(config)
        for phrase in ("how do i change your humor level", "dont turn off streaming", "set volume to 50",
                       "set a reminder at 5pm", "i like your sarcasm", "be honest with me"):
            with self.subTest(phrase=phrase):
                self.ask(phrase)
                self.assertNotEqual(self.trace()["answered_by"], "layer_034_settings")
        self.assertEqual(brain_settings.effective(config), before)

    def test_weather_temperature_is_not_a_setting(self):
        self.assertIsNone(settings_control.parse("what's the temperature outside"))
        self.assertIsNone(settings_control.parse("what is the temperature in london"))
        self.ask("what's the temperature outside")
        self.assertNotIn(self.trace()["answered_by"], ("layer_034_settings", "layer_035_router"))

    def test_settings_api_uses_the_same_registry(self):
        try:
            from backend.routes import config_routes
        except Exception:
            self.skipTest("backend routes need fastapi")
        from fastapi import HTTPException
        out = config_routes.update_brain_config(config_routes.BrainConfigUpdate(updates={"tars_honesty": 40}))
        self.assertEqual(out["brain"]["tars_honesty"], 40)
        with self.assertRaises(HTTPException):
            config_routes.update_brain_config(config_routes.BrainConfigUpdate(updates={"curiosity_level": "max"}))
        self.assertIn("curiosity_level", config_routes.get_brain_config())


class MachineKnowledge(BrainTest):
    def setUp(self):
        super().setUp()
        self.real = system_info.snapshot
        system_info.snapshot = lambda: dict(FAKE_PC)
        self.addCleanup(setattr, system_info, "snapshot", self.real)

    def test_questions_about_this_machine(self):
        cases = {
            "what cpu do i have": "AMD Ryzen 7 7840HS with 8 cores and 16 threads",
            "how much ram does my pc have": "32 GB of RAM",
            "which gpu do i have": "RTX 4060 with 8 GB of VRAM",
            "how much disk space is left": "C: has 410 GB free of 953 GB",
            "what os am i running": "Windows 11 Home",
            "how long has my pc been on": "3 hours and 25 minutes",
            "what are my system specs": "32 GB RAM",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertIn(expected, self.ask(question))
                self.assertEqual(self.trace()["answered_by"], "layer_03_identity")

    def test_general_knowledge_is_not_about_this_machine(self):
        for q in ("what is a gpu", "how does a cpu work", "what is the best gpu for gaming",
                  "how much memory do you have about me", "how much storage are you using"):
            with self.subTest(q=q):
                self.assertEqual(system_info.match(q), [])

    def test_reasoning_questions_go_to_the_model_with_specs_attached(self):
        self.ask("can my laptop run cyberpunk")
        self.assertEqual(self.trace()["answered_by"], "layer_08_llm")
        prompt = " ".join(m["content"] for m in LLM_CALLS[-1]["messages"])
        self.assertIn("RTX 4060", prompt)

    def test_version_comes_from_version_txt(self):
        from seven_utils.version import get_version
        self.assertIn(get_version(), self.ask("what version are you"))


class AppMapReadsSharedComponents(unittest.TestCase):
    def test_settings_rows_sections_and_page_titles(self):
        import os
        import tempfile
        from brain_modules import app_map
        src = tempfile.mkdtemp()
        os.makedirs(os.path.join(src, "pages", "settings"))
        os.makedirs(os.path.join(src, "components"))
        open(os.path.join(src, "App.jsx"), "w").write(
            "import Settings from './pages/settings/index'\nimport Tasks from './pages/Tasks';\n"
            '<Route path="/settings"  element={<Settings />} />\n<Route path="/tasks" element={<Tasks />} />')
        open(os.path.join(src, "components", "Sidebar.jsx"), "w").write(
            "{ to: '/tasks', label: 'Tasks', icon: X },\n{ to: '/settings', label: 'Settings', icon: Y },")
        open(os.path.join(src, "pages", "Tasks.jsx"), "w").write("<div>Undo</div><p>Something happened just now ok</p>")
        open(os.path.join(src, "pages", "settings", "index.jsx"), "w").write(
            "/* SEVEN_DOC {\"purpose\": \"Configure Seven\", \"keywords\": [\"preferences\"]} */\n"
            "{ key: 'brain', label: 'Brain', icon: Cpu, desc: 'x', component: BrainSection },\n"
            '<PageShell title="Settings" description={active.desc} actions={<span>Saving</span>}>')
        open(os.path.join(src, "pages", "settings", "BrainSection.jsx"), "w").write(
            '<Row label="Temperature"\n     description={`${label(t)}. Lower is more precise.`}>\n'
            '<Row label="Stream replies" description="Speak while the answer is written.">')
        data = app_map.build(src)
        pages = {p["id"]: p for p in data["pages"]}
        self.assertEqual(pages["tasks"]["title"], "Tasks")                 # from the sidebar, not "Undo"
        self.assertEqual(pages["settings"]["title"], "Settings")
        self.assertEqual(pages["settings"]["purpose"], "Configure Seven")
        labels = [c["label"] for c in pages["settings"]["controls"]]
        self.assertEqual(labels, ["Temperature", "Stream replies"])         # header text like "Saving" is ignored
        self.assertEqual(pages["settings"]["controls"][0]["description"], "Lower is more precise.")
        out = os.path.join(src, "map.json")
        app_map.write(data, out)
        reply = app_map.describe(app_map.search("how do I change the temperature", path=out)[0])
        self.assertIn("Settings, in the Brain section", reply)
        self.assertIn('"Temperature"', reply)


class PlanInfoForTheModel(unittest.TestCase):
    def test_plan_summary_matches_license_limits(self):
        from brain_modules.prompt_builder import plan_summary
        text = plan_summary()
        self.assertIn("unlimited on every plan", text)
        self.assertNotIn("7 facts", text)


class MemoryPageMatchesBrainMemory(BrainTest):
    def test_manual_fact_is_stored_under_the_brain_speaker_key(self):
        from brain_modules import session
        fact_id = fact_service.add_manual(session.resolve_key("default"), "My sister is called Priya")
        row = facts_store.get_by_id(fact_id)
        self.assertEqual(row["speaker_id"], session.resolve_key("default"))
        self.assertEqual(row["source_text"], "Added on the Memory page")

    def test_deleted_or_replaced_facts_are_not_recalled_from_the_index(self):
        fid = facts_store.add_fact("I like jazz", speaker_id="owner")
        self.assertTrue(fact_service._still_active({"sql_id": fid}))
        new_id = fact_service.edit(fid, "I like blues", "supersede")
        self.assertFalse(fact_service._still_active({"sql_id": fid}))
        self.assertTrue(fact_service._still_active({"sql_id": new_id}))
        fact_service.delete(new_id)
        self.assertFalse(fact_service._still_active({"sql_id": new_id}))
        self.assertTrue(fact_service._still_active({}))                     # legacy documents are kept

    def test_routes_overview_edit_delete_and_clear(self):
        try:
            from backend.routes import memory as routes
        except Exception:
            self.skipTest("backend routes need fastapi")
        key = routes._speaker_key()
        a = facts_store.add_fact("I live in Hyderabad", speaker_id=key, category="personal")
        facts_store.add_fact("I prefer tea", speaker_id=key, category="preference")
        conv = conversation_store.create_conversation(key)
        conversation_store.add_message(conv, "user", "hello there seven", source="voice")
        conversation_store.add_message(conv, "assistant", "Hi.")

        ov = routes.memory_overview()
        self.assertEqual(ov["facts"]["active"], 2)
        self.assertEqual(ov["facts"]["by_category"], {"personal": 1, "preference": 1})
        self.assertEqual(ov["conversations"]["count"], 1)
        self.assertEqual(ov["conversations"]["messages"], 2)
        self.assertEqual(ov["conversations"]["by_source"], {"voice": 1})
        self.assertIsNotNone(ov["conversations"]["last_at"])

        self.assertTrue(routes.delete_structured_fact(a)["success"])
        self.assertEqual(routes.memory_overview()["facts"]["active"], 1)

        out = routes.clear_all_memory()
        self.assertTrue(out["success"])
        self.assertEqual(facts_store.count_facts(), 0)
        self.assertEqual(conversation_store.count_conversations(), 0)


if __name__ == "__main__":
    unittest.main()
