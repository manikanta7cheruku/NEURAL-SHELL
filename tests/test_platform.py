"""
Platform evaluations: limits and storage, conversations, capabilities and self-knowledge against the real
registry, app map generation, data-flow answers per configuration, web outcomes, action receipts, router,
settings, decision policy, curiosity, outcomes, patches and determinism.
"""
import json
import os
import tempfile

from support import (BrainTest, FakeWeb, LLM_CALLS, brain, capabilities, config, conversation_store, facts_store,
                     learning_store, limits, web_provider)
from brain_modules import (action_receipts, app_map, brain_settings, curiosity, decision_policy, goals,
                           intent_router, speech_acts)
from brain_modules import conversation_state as cs


class LimitsAndStorage(BrainTest):
    def test_limits_are_unlimited_for_history_and_facts(self):
        self.assertEqual((limits.conversation_limit(), limits.fact_limit()), (-1, -1))

    def test_hundreds_of_conversations_are_kept(self):
        ids = [conversation_store.create_conversation("there", f"chat {i}") for i in range(120)]
        for i in ids:
            conversation_store.add_message(i, "user", f"message in {i}")
        self.assertEqual(conversation_store.count_conversations("there"), 120)
        self.assertEqual(len(conversation_store.list_conversations("there", limit=500)), 120)

    def test_many_facts_are_kept_and_indexed_for_later(self):
        from brain_modules import fact_extractor, fact_extractor as fe
        from memory import fact_service
        for i in range(40):
            fact_service.remember("there", fe.ExtractedFact(f"likes:thing{i}", f"thing{i}", f"User likes thing{i}",
                                                            "preference", 0.8, True), index=False)
        self.assertEqual(facts_store.count_facts("there"), 40)
        self.assertEqual(len(facts_store.get_unindexed(100)), 40)      # nothing lost while indexing is pending

    def test_full_disk_is_reported_never_hidden(self):
        original = limits.can_write
        limits.can_write = lambda *a, **k: (False, "Disk space is almost full (10 MB free).")
        try:
            reply = self.ask("explain how a hash map works")
            self.assertTrue(reply)                                       # Seven still answers
            self.assertIn("almost full", self.trace()["storage_error"])  # and says the save failed
            with self.assertRaises(conversation_store.StorageUnavailable):
                conversation_store.add_message(self.conv, "user", "x")
        finally:
            limits.can_write = original

    def test_search_export_delete(self):
        self.ask("I am planning a trip to Lisbon in March with my sister")
        hits = conversation_store.search("default", "Lisbon")
        self.assertTrue(hits and "Lisbon" in hits[0]["content"])
        self.assertEqual(len(conversation_store.export(self.conv)["conversations"][0]["messages"]), 2)
        self.assertTrue(conversation_store.delete_conversation(self.conv))
        self.assertEqual(conversation_store.search("default", "Lisbon"), [])

    def test_persistence_across_reopen(self):
        self.ask("Remember that my favorite framework is React.")
        path = conversation_store.get_db_path()
        conversation_store.set_db_path(path)                              # reopen the same file
        self.assertTrue(conversation_store.list_conversations("default"))


class Capabilities(BrainTest):
    def test_answers_follow_the_registry(self):
        capabilities.set_status_override("apps", "available", "")
        self.assertIn("Yes", self.ask("can you open apps"))
        capabilities.set_status_override("apps", "unavailable", "module hands.core is not installed")
        self.assertIn("Not on this install", self.ask("can you open apps"))
        capabilities.set_status_override("apps", "disabled", "switched off in Settings (x)")
        self.assertIn("switched off", self.ask("can you open apps"))

    def test_what_apps_can_you_open_is_not_a_generic_chatbot_answer(self):
        capabilities.set_status_override("apps", "available", "")
        reply = self.ask("what apps can you open for me")
        self.assertIn("open", reply.lower())
        self.assertNotIn("text-based", reply.lower())
        self.assertEqual(LLM_CALLS, [])

    def test_offline_changes_the_answer(self):
        web_provider.set_online_override(False)
        self.assertIn("needs the internet", self.ask("can you check the weather"))

    def test_unsupported_is_stated_plainly(self):
        self.assertIn("Not yet", self.ask("can you see my screen"))

    def test_degraded_tool_is_reported_from_outcomes(self):
        for _ in range(4):
            learning_store.record_outcome("there", "action", "apps", "failed", "OPEN camera")
        capabilities.set_status_override("apps", None)
        state, reason = capabilities.status("apps")
        self.assertIn(state, ("degraded", "unavailable"))

    def test_self_registration_from_source(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "newtool.py"), "w").write(
            'CAPABILITY = {"id": "photos", "title": "Photo tools", "summary": "resize images", "examples": ["resize it"]}\n')
        self.assertEqual(capabilities.discover([d]), 1)
        self.assertEqual(capabilities.get("photos").title, "Photo tools")


class SelfKnowledge(BrainTest):
    def test_app_questions_come_from_the_app_map(self):
        reply = self.ask("how do I change your model")
        self.assertIn("Settings", reply)
        self.assertEqual(LLM_CALLS, [])
        self.assertIn("Memory", self.ask("what is the memory page for"))

    def test_app_map_is_generated_from_frontend_source(self):
        src = tempfile.mkdtemp()
        os.makedirs(os.path.join(src, "pages"))
        open(os.path.join(src, "App.jsx"), "w").write(
            "import Home from './pages/Home';\n<Route path=\"/dashboard\" element={<Home isFirstLaunch={x} />} />")
        open(os.path.join(src, "pages", "Home.jsx"), "w").write(
            '<PageHeader title="Dashboard" sub="Your overview" />\n<div>Recent activity</div>'
            '<p>Shows the last things Seven did for you.</p>')
        data = app_map.build(src)
        self.assertEqual(data["pages"][0]["title"], "Dashboard")
        self.assertEqual(data["pages"][0]["controls"][0]["label"], "Recent activity")
        out = os.path.join(src, "app_map.json")
        app_map.write(data, out)
        self.assertTrue(app_map.search("where do I see recent activity", path=out))
        before = app_map.source_hash(src)
        open(os.path.join(src, "pages", "Home.jsx"), "a").write("<div>New widget</div>")
        os.utime(os.path.join(src, "pages", "Home.jsx"), (1, 2_000_000_000))
        self.assertNotEqual(before, app_map.source_hash(src))

    def test_storage_answers_are_consistent_and_follow_the_configuration(self):
        where = self.ask("where are our conversations stored")
        device = self.ask("is my data on my device")
        privacy = self.ask("do you send my data anywhere")
        self.assertIn("this computer", where)
        self.assertTrue(device.startswith("Yes"))
        self.assertIn("usage statistics", privacy)
        self.assertNotIn("never sent anywhere", privacy)
        config.update_config({"privacy": {"telemetry_enabled": False}, "web": {"enabled": False}})
        privacy = self.ask("do you send my data anywhere")
        self.assertNotIn("usage statistics", privacy)
        self.assertNotIn("search text", privacy)
        self.assertIn("license", privacy)

    def test_status_questions(self):
        web_provider.set_online_override(False)
        self.assertIn("no internet", self.ask("do you have internet").lower())
        self.assertIn("haven't run", self.ask("did that work"))

    def test_goal_and_memory_counts(self):
        self.ask("Remember that my favorite framework is React.")
        self.assertIn("1 facts", self.ask("how many things do you remember about me"))


class WebOutcomes(BrainTest):
    def test_each_failure_has_its_own_honest_reply(self):
        for status, phrase in (("offline", "internet|offline"), ("error", "didn't respond"), ("empty", "nothing reliable"),
                               ("disabled", "switched off")):
            self.web(status)
            self.assertRegex(self.ask("what's the latest news today"), phrase, status)
        self.assertEqual(LLM_CALLS, [])

    def test_non_time_sensitive_question_still_gets_an_answer_with_a_caveat(self):
        self.web("offline")
        self.ask("who wrote the book dune and what is it about in short")
        self.assertIn("web", self.llm_user_message().lower())

    def test_default_provider_reports_offline_without_touching_the_network(self):
        web_provider.set_online_override(False)
        out = web_provider.DefaultWebProvider().lookup("weather in rio", config)
        self.assertIn(out.status, ("offline", "not_needed"))


class Receipts(BrainTest):
    def test_success_failure_unconfirmed(self):
        ok = action_receipts.run_action("OPEN", "camera", lambda: True)
        bad = action_receipts.run_action("OPEN", "camera", lambda: (_ for _ in ()).throw(RuntimeError("blocked")))
        unk = action_receipts.run_action("OPEN", "camera", lambda: None)
        self.assertEqual((ok.status, bad.status, unk.status), ("success", "failed", "unconfirmed"))
        self.assertIn("didn't work", action_receipts.reconcile_reply("Opening camera.", [bad]))
        self.assertEqual(action_receipts.reconcile_reply("Opening camera.", [unk]), "Opening camera.")

    def test_unverifiable_never_claims_verified(self):
        r = action_receipts.run_action("OPEN", "somethingobscure", lambda: None,
                                       lambda: action_receipts.verify_running("somethingobscure"))
        self.assertFalse(r.verified)

    def test_failed_then_corrected_launch_offers_an_alias_and_learns_after_yes(self):
        failed = action_receipts.ActionReceipt("OPEN", "camra", "failed", "not found")
        self.assertIsNone(brain.note_receipts("default", self.conv, [failed]))
        good = action_receipts.ActionReceipt("OPEN", "camera", "success", "", 5, True)
        q = brain.note_receipts("default", self.conv, [good])
        self.assertIn("\"camra\" means camera", q)
        reply = self.ask("yes")
        self.assertIn("camra", reply)
        self.assertEqual(config.KEY["commands"]["app_aliases"]["camra"], "camera")

    def test_unverified_success_never_creates_an_alias(self):
        brain.note_receipts("default", self.conv, [action_receipts.ActionReceipt("OPEN", "camra", "failed")])
        q = brain.note_receipts("default", self.conv, [action_receipts.ActionReceipt("OPEN", "camera", "success", "", 5, False)])
        self.assertIsNone(q)

    def test_did_that_work_uses_receipts(self):
        brain.note_receipts("default", self.conv, [action_receipts.ActionReceipt("OPEN", "camera", "failed", "blocked")])
        self.assertIn("failed", self.ask("did that work"))

    def test_risky_action_needs_confirmation_then_runs(self):
        self.assertTrue(brain.needs_confirmation("CLOSE", "ALL_chrome"))
        self.assertFalse(brain.needs_confirmation("OPEN", "chrome"))
        question = brain.request_confirmation("default", self.conv, "###CLOSE: ALL_chrome", "That would affect all chrome.")
        self.assertIn("Say yes", question)
        self.assertIn("###CLOSE: ALL_chrome", self.ask("yes"))
        self.assertTrue(self.trace()["confirmed"])


class Router(BrainTest):
    def test_paraphrases_route_and_general_questions_do_not(self):
        cases = {"which programs can you launch": "capability_list", "where can I see my reminders": "app_help",
                 "is anything sent to the cloud": "data_flow", "how do you know this about me": "memory_provenance",
                 "what is a business model": None, "explain photosynthesis": None, "tell me a joke": None}
        for q, expected in cases.items():
            self.assertEqual(intent_router.route(speech_acts.normalize(q)).label, expected, q)

    def test_learned_example_is_bounded_and_used(self):
        self.assertTrue(intent_router.add_example("app_help", "where do i manage my gizmo settings"))
        self.assertFalse(intent_router.add_example("not_a_label", "anything goes here"))
        self.assertEqual(intent_router.route("where do i manage my gizmo settings").label, "app_help")


class Settings(BrainTest):
    def test_values_are_clamped_and_reported(self):
        self.assertEqual(brain_settings.coerce("brain.temperature", 7)[0], 1.0)
        self.assertEqual(brain_settings.coerce("brain.temperature", "x")[0], 0.3)
        self.assertEqual(brain_settings.coerce("brain.tars_humor", -5), (0, False, "minimum is 0"))
        self.assertEqual(brain_settings.validate_update("brain.curiosity_level", "wild")[0], False)
        self.assertTrue(brain_settings.effective(config)["brain.streaming"]["valid"])

    def test_temperature_is_applied_and_capped_for_grounded_answers(self):
        config.update_config({"brain": {"temperature": 0.6}})
        self.ask("explain how a hash map works")
        self.assertEqual(LLM_CALLS[-1]["options"]["temperature"], 0.6)
        self.web("ok", "Rio: 28 C")
        self.ask("what's the weather in Rio")
        self.assertLessEqual(LLM_CALLS[-1]["options"]["temperature"], 0.2)

    def test_humor_and_honesty_reach_the_prompt_but_not_the_facts(self):
        config.update_config({"brain": {"tars_humor": 5}})
        self.ask("explain how a hash map works")
        self.assertIn("deadpan", self.llm_system())
        config.update_config({"brain": {"tars_humor": 95}})
        self.ask("describe how a binary tree is traversed")
        self.assertIn("humor is high", self.llm_system())
        self.assertEqual(self.ask("what time is it")[:4], "It's")

    def test_streaming_off_returns_one_string_on_the_voice_path(self):
        config.update_config({"brain": {"streaming": False}})
        r = brain.think("explain how a hash map works", "voice_user", "sentence", self.conv)
        self.assertIsInstance(r, str)
        config.update_config({"brain": {"streaming": True}})
        r = brain.think("describe how a binary tree is traversed", "voice_user", "sentence", self.conv)
        self.assertIsInstance(r, tuple)
        self.assertTrue(all(isinstance(x, str) for x in r[1]))

    def test_model_selection_is_validated(self):
        st = brain_settings.model_status(config, "llama3.2:1b", ["llama3.2:1b"])
        self.assertTrue(st["installed"])
        config.update_config({"brain": {"model_name": "llama3.1:8b"}})
        self.assertIn("not installed", brain_settings.model_status(config, "llama3.2:1b", ["llama3.2:1b"])["note"])

    def test_history_ttl_limits_context(self):
        config.update_config({"brain": {"history_ttl_seconds": 60}})
        from brain_modules import chat_history
        chat_history.add_exchange(f"default#{self.conv}", "old question here", "old answer here")
        for m in chat_history._history[f"default#{self.conv}"]:
            m["ts"] -= 3600
        self.ask("explain how a hash map works")
        self.assertFalse(any("old question" in m["content"] for m in LLM_CALLS[-1]["messages"]))


class Policy(BrainTest):
    def test_complex_questions_get_depth_and_unknowns_are_declared(self):
        self.ask("compare postgres versus mysql for a small startup and give me the trade-offs step by step")
        self.assertEqual(self.trace()["mode"], "deep")
        self.assertGreater(LLM_CALLS[-1]["options"]["num_predict"], 300)
        self.assertIn("<evidence_status>", self.llm_user_message())
        self.assertLessEqual(LLM_CALLS[-1]["options"]["temperature"], 0.3)

    def test_unsupported_personal_claims_are_refused_in_text_mode(self):
        import support
        support.LLM_REPLY[:] = ["You told me you chose it because it is clean."]
        try:
            self.assertIn("won't guess", self.ask("tell me something about my life choices please now"))
        finally:
            support.LLM_REPLY[:] = ["It holds up. ", "Great movie."]


class CuriosityAndOutcomes(BrainTest):
    def test_question_budget_and_cooldown(self):
        self.ask("What about Interstellar?")
        r1 = self.ask("I love that movie.")
        self.assertIn("favorite movie", r1)                    # one grounded question
        r2 = self.ask("I also really enjoy listening to jazz music at night")
        self.assertFalse(r2.rstrip().endswith("?"))           # budget: not again straight away

    def test_off_means_off(self):
        config.update_config({"brain": {"curiosity_level": "off"}})
        self.ask("What about Interstellar?")
        self.assertFalse(self.ask("I love that movie.").rstrip().endswith("?"))

    def test_ignored_questions_cool_down(self):
        self.ask("What about Interstellar?")
        self.ask("I love that movie.")
        for q in ("tell me about black holes in two lines", "explain how a hash map works please"):
            self.ask(q)
        st = cs.get(f"default#{self.conv}")
        self.assertGreaterEqual(st.ignored, 1)

    def test_outcomes_never_become_facts(self):
        learning_store.record_outcome("there", "action", "apps", "success", "OPEN chrome")
        self.assertEqual(facts_store.count_facts("there"), 0)

    def test_thumbs_feedback_is_recorded_as_an_outcome(self):
        self.ask("explain how a hash map works")
        mid = conversation_store.get_messages(self.conv)[-1]["id"]
        learning_store.record_outcome("there", "feedback", "answer", "down", "too long", self.conv)
        self.assertEqual(learning_store.reliability("feedback", "answer")["last"], "down")


class Goals(BrainTest):
    def test_extraction_rules(self):
        titles = [g.title for g in goals.extract_goals("I want to learn Rust by December. I want to open chrome.")]
        self.assertEqual(titles, ["learn Rust"])
        self.assertEqual(goals.extract_goals("what should I build next?"), [])


class Determinism(BrainTest):
    def test_repeated_runs_are_identical(self):
        import random
        outs = []
        for _ in range(3):
            self.setUp()
            random.seed(11)
            outs.append((self.ask("Hey"), self.ask("Remember that my favorite framework is React."),
                         self.ask("what is my favorite framework"), self.ask("What's the weather in Rio?")))
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])
