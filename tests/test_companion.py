"""
Seven the friend (companion/): it reaches out like a person, not a timer. Only when you are idle, at a human pace that
changes from day to day, never in quiet hours, never twice about the same thing, and it learns from your answers.
"""
import datetime
import os
import random
import tempfile
import time
import unittest
from unittest import mock

from support import BrainTest
import brain
from companion import content, engine, scheduler, settings, store
from memory import conversation_store as cstore, facts_store, learning_store

D = datetime.datetime


def at(h, m=0, day=10):
    return D(2026, 11, day, h, m)


class Settings(unittest.TestCase):
    def test_garbage_falls_back_to_the_defaults(self):
        for raw in (None, "x", 5, {"pace": "wild", "quiet": {"start": "25:99", "end": "nope"}, "topics": []}):
            s = settings.normalize(raw)
            self.assertEqual((s["pace"], s["quiet"]["start"], s["quiet"]["end"]), ("auto", "22:00", "08:00"))
            self.assertTrue(s["enabled"] and s["voice"])

    def test_what_the_person_chose_is_kept(self):
        s = settings.normalize({"enabled": False, "pace": "calm", "voice": False, "quiet": {"enabled": False, "start": "9:5", "end": "07:30"},
                                "topics": {"facts": False}})
        self.assertEqual((s["enabled"], s["pace"], s["voice"]), (False, "calm", False))
        self.assertEqual((s["quiet"]["enabled"], s["quiet"]["start"], s["quiet"]["end"]), (False, "09:05", "07:30"))
        self.assertEqual(s["topics"], {"you": True, "seven": True, "facts": False})

    def test_quiet_hours_wrap_midnight(self):
        s = settings.normalize(None)
        for h, m, quiet in ((23, 0, True), (2, 0, True), (7, 59, True), (8, 0, False), (12, 0, False), (21, 59, False), (22, 0, True)):
            self.assertEqual(settings.in_quiet_hours(s, at(h, m)), quiet, (h, m))

    def test_quiet_hours_inside_one_day_and_when_off(self):
        s = settings.normalize({"quiet": {"enabled": True, "start": "13:00", "end": "15:00"}})
        self.assertEqual([settings.in_quiet_hours(s, at(h)) for h in (12, 13, 14, 15)], [False, True, True, False])
        self.assertFalse(settings.in_quiet_hours(settings.normalize({"quiet": {"enabled": False}}), at(23)))
        self.assertFalse(settings.in_quiet_hours(settings.normalize({"quiet": {"start": "10:00", "end": "10:00"}}), at(10)))

    def test_the_daily_number_varies_between_3_5_and_7_and_is_fixed_for_a_day(self):
        s = settings.normalize(None)
        days = [datetime.date(2026, 11, 1) + datetime.timedelta(days=i) for i in range(60)]
        seen = {settings.daily_target(s, d) for d in days}
        self.assertEqual(seen, {3, 5, 7})
        self.assertEqual(settings.daily_target(s, days[3]), settings.daily_target(s, days[3]))
        self.assertEqual(settings.daily_target(settings.normalize({"pace": "calm"}), days[0]), 3)
        self.assertEqual(settings.daily_target(settings.normalize({"pace": "lively"}), days[0]), 7)

    def test_the_gap_is_7_to_17_minutes_by_default(self):
        rng = random.Random(1)
        gaps = [settings.gap_minutes(settings.normalize(None), rng) for _ in range(300)]
        self.assertTrue(all(7 <= g <= 17 for g in gaps))
        self.assertLess(min(gaps), 8.5)
        self.assertGreater(max(gaps), 15.5)
        calm = [settings.gap_minutes(settings.normalize({"pace": "calm"}), rng) for _ in range(100)]
        self.assertTrue(all(14 <= g <= 30 for g in calm))


class CompanionTest(BrainTest):
    def setUp(self):
        super().setUp()
        store.set_db_path(os.path.join(tempfile.mkdtemp(prefix="seven_comp_"), "companion.db"))
        self.addCleanup(store.set_db_path, None)
        for p in (mock.patch.object(engine, "_user_name", lambda: "Asha"),
                  mock.patch.object(scheduler, "_last_touch", 0.0)):
            p.start()
            self.addCleanup(p.stop)
        self.rng = random.Random(7)

    def thread(self):
        return cstore.get_messages(engine.conversation_id(), limit=50)

    def last_text(self):
        return self.thread()[-1]["content"]


class Thread(CompanionTest):
    def test_it_is_one_thread_called_seven_and_never_the_current_chat(self):
        cid = engine.conversation_id()
        self.assertEqual(engine.conversation_id(), cid)
        conv = cstore.get_conversation(cid)
        self.assertEqual((conv["title"], conv["kind"]), ("Seven", "companion"))
        engine.post(content.ABOUT_YOU[0])
        self.assertNotEqual(brain.resolve_conversation("default"), cid)       # a voice chat never lands in Seven's thread
        self.assertTrue(engine.is_companion(cid))
        self.assertFalse(engine.is_companion(self.conv))

    def test_a_posted_message_is_unread_until_the_thread_is_opened(self):
        engine.post(content.ABOUT_YOU[0])
        engine.post(content.FACTS[0])
        self.assertEqual(store.unread_count(), 2)
        self.assertEqual(store.mark_read_all(), 2)
        self.assertEqual(store.unread_count(), 0)

    def test_the_message_is_a_normal_assistant_message_marked_as_seven_reaching_out(self):
        engine.post(content.ABOUT_YOU[0], spoken=True, rng=random.Random(99))
        m = self.thread()[-1]
        self.assertEqual((m["role"], m["source"]), ("assistant", "companion"))
        self.assertIn('"spoken": true', m["meta"])
        self.assertIn("work", m["content"])


class Choosing(CompanionTest):
    def choose(self, now=None, **kw):
        return engine.choose(now or at(14), self.rng, settings.normalize(kw.get("cfg")), kw.get("exclude", ()))

    def test_it_never_repeats_a_topic_it_asked_recently(self):
        seen = set()
        for _ in range(12):
            c = self.choose()
            self.assertNotIn(c.topic, seen)
            seen.add(c.topic)
            engine.post(c)

    def test_the_kind_changes_so_it_never_feels_like_a_fixed_loop(self):
        kinds = []
        for _ in range(9):
            c = self.choose()
            kinds.append(c.kind)
            engine.post(c)
        for a, b, c in zip(kinds, kinds[1:], kinds[2:]):
            self.assertFalse(a == b == c, kinds)

    def test_topics_the_person_turned_off_are_never_chosen(self):
        cfg = {"topics": {"you": False, "seven": False, "facts": True}}
        for _ in range(8):
            c = self.choose(cfg=cfg)
            self.assertEqual(c.kind, "facts")
            engine.post(c)

    def test_nothing_when_every_topic_is_off(self):
        self.assertIsNone(self.choose(cfg={"topics": {"you": False, "seven": False, "facts": False}}))

    def test_morning_and_evening_questions_only_come_at_those_times(self):
        pool = [c for c in content.ABOUT_YOU if c.moment != "any"]
        self.assertTrue(pool)
        for _ in range(30):
            c = self.choose(at(14))
            self.assertEqual(c.moment, "any")
        got = {self.choose(at(9)).moment for _ in range(200)}
        self.assertIn("morning", got)
        self.assertNotIn("evening", got)

    def test_it_checks_in_when_you_seem_down(self):
        with mock.patch("memory.mood.mood_engine.get_status", lambda: {"label": "down"}):
            c = self.choose()
        self.assertEqual(c.topic, "care.mood")
        self.assertIn("here if you want to talk", c.text)
        self.assertIn("Asha", c.text)

    def test_it_follows_up_on_a_goal_you_told_it_about(self):
        learning_store.upsert_goal(engine.speaker_key(), "rust", "learn Rust")
        goals = {c.text for c in (self.choose() for _ in range(1))}
        for _ in range(80):
            goals.add(self.choose().text)
            if "How is learning Rust going?" in goals:
                break
        self.assertIn("How is learning Rust going?", goals)

    def test_it_welcomes_you_back_after_a_long_time_away(self):
        store.set_state("previous_seen", (at(14) - datetime.timedelta(hours=30)).strftime(store.FMT))
        self.assertEqual(self.choose().topic, "welcome.back")
        store.set_state("previous_seen", (at(14) - datetime.timedelta(hours=2)).strftime(store.FMT))
        self.assertNotEqual(self.choose().topic, "welcome.back")

    def test_it_asks_the_question_it_was_saving(self):
        learning_store.add_gap(engine.speaker_key(), "entity_interest", "Rust", {"entity": "Rust"}, 5)
        texts = [self.choose().text for _ in range(120)]
        self.assertTrue(any("keep coming back to Rust" in t for t in texts))

    def test_the_name_is_used_now_and_then_not_every_time(self):
        texts = [engine.render(content.ABOUT_YOU[0], random.Random(i)) for i in range(200)]
        named = [t for t in texts if t.startswith("Asha, ")]
        self.assertTrue(30 < len(named) < 100)
        self.assertEqual(engine.render(content.Candidate("x", "you", "Asha, are you there?"), random.Random(1)).count("Asha"), 1)

    def test_no_line_has_an_em_dash_and_every_seven_line_asks_something(self):
        for c in content.ABOUT_YOU + content.ABOUT_SEVEN + content.FACTS:
            self.assertNotIn("—", c.text)
            self.assertTrue(c.text.rstrip().endswith("?"), c.topic)
        self.assertEqual(len({c.topic for c in content.ABOUT_YOU + content.ABOUT_SEVEN + content.FACTS}),
                         len(content.ABOUT_YOU + content.ABOUT_SEVEN + content.FACTS))


class Learning(CompanionTest):
    def ask(self, topic):
        c = engine.BY_TOPIC[topic]
        engine.post(c)
        return c

    def facts(self):
        return [f["value"] for f in facts_store._rows("SELECT value FROM facts WHERE active=1")]

    def test_a_short_answer_becomes_a_fact_and_a_deeper_question_is_queued(self):
        self.ask("you.job")
        engine.note_user_message(engine.conversation_id(), "I'm a teacher")
        self.assertIn("Does or studies: teacher", self.facts())
        self.assertEqual(store.get_state("deepen")["text"], "What do you enjoy most about it?")

    def test_a_no_or_a_question_is_not_remembered_as_an_answer(self):
        self.ask("you.music")
        engine.note_user_message(engine.conversation_id(), "no")
        engine.note_user_message(engine.conversation_id(), "why do you ask?")
        self.assertEqual(self.facts(), [])
        self.assertIsNone(store.get_state("deepen"))

    def test_a_long_message_is_a_conversation_not_an_answer(self):
        self.ask("you.food")
        engine.note_user_message(engine.conversation_id(), "well it depends a lot on the season and who I am eating with and where we are")
        self.assertEqual(self.facts(), [])

    def test_answering_clears_the_unanswered_count(self):
        self.ask("you.pet")
        self.ask("you.learn")
        self.assertEqual(store.unanswered_streak(), 2)
        engine.note_user_message(engine.conversation_id(), "a cat")
        self.assertEqual(store.unanswered_streak(), 0)

    def test_not_now_means_quiet_for_a_while(self):
        self.ask("you.pet")
        now = at(14)
        engine.note_user_message(engine.conversation_id(), "not now, I'm busy", now)
        self.assertTrue(engine.snoozed(now + datetime.timedelta(hours=2)))
        self.assertFalse(engine.snoozed(now + datetime.timedelta(hours=4)))
        self.assertEqual(self.facts(), [])

    def test_a_message_in_another_chat_is_ignored(self):
        self.ask("you.job")
        engine.note_user_message(self.conv, "I'm a teacher")
        self.assertEqual(self.facts(), [])

    def test_a_spoken_answer_soon_after_the_question_counts(self):
        self.ask("you.job")
        engine.note_voice_message("a nurse")
        self.assertIn("Does or studies: nurse", self.facts())

    def test_a_spoken_remark_long_after_does_not(self):
        c = self.ask("you.job")
        old = (D.now() - datetime.timedelta(minutes=30)).strftime(store.FMT)
        store._run("UPDATE sent SET created_at=?", (old,))
        engine.note_voice_message("a nurse")
        self.assertEqual(self.facts(), [])

    def test_the_answers_are_cleaned_up(self):
        for raw, want in (("I'm a teacher.", "teacher"), ("It's jazz!", "jazz"), ("probably rock", "rock"), ("I love ramen", "ramen")):
            self.assertEqual(engine.clean_answer(raw), want)


class AskingBack(CompanionTest):
    def test_the_deeper_question_comes_first_and_as_a_second_message(self):
        engine.post(engine.BY_TOPIC["you.job"], now=at(14))
        engine.note_user_message(engine.conversation_id(), "I'm a teacher")
        self.assertIsNotNone(engine.follow_up(at(14), self.rng, reply="That is a great job to have."))
        m = self.thread()[-1]
        self.assertEqual(m["content"], "What do you enjoy most about it?")
        self.assertEqual(m["source"], "companion")
        self.assertEqual(store.unread_count(), 1)                  # only Seven's first message; the follow-up was written to someone reading
        self.assertEqual(store.sent_today(at(14).date()), 1)       # a follow-up does not use up the day's messages

    def test_otherwise_a_fresh_question_is_asked_back(self):
        engine.post(engine.BY_TOPIC["you.pet"])
        before = len(self.thread())
        self.assertIsNotNone(engine.follow_up(at(14), self.rng, reply="Nice, dogs are great company."))
        self.assertEqual(len(self.thread()), before + 1)
        self.assertTrue(self.last_text().endswith("?"))

    def test_it_asks_one_question_at_a_time(self):
        engine.conversation_id()
        self.assertIsNone(engine.follow_up(at(14), self.rng, reply="That sounds great. What are you building?"))
        self.assertIsNotNone(engine.follow_up(at(14), self.rng, reply="That sounds great."))

    def test_it_asks_nothing_while_snoozed_or_off(self):
        engine.conversation_id()
        store.set_state("snooze_until", (at(14) + datetime.timedelta(hours=1)).strftime(store.FMT))
        self.assertIsNone(engine.follow_up(at(14), self.rng, reply="Okay."))
        store.set_state("snooze_until", None)
        with mock.patch.object(settings, "get", lambda config=None: settings.normalize({"enabled": False})):
            self.assertIsNone(engine.follow_up(at(14), self.rng, reply="Okay."))

    def test_after_reply_asks_back_only_in_seven_s_thread_and_not_after_one_word(self):
        self.assertFalse(engine.after_reply(self.conv, "how are you doing today", delay=0))
        engine.conversation_id()
        self.assertFalse(engine.after_reply(engine.conversation_id(), "ok", delay=0))
        self.assertFalse(engine.after_reply(engine.conversation_id(), "stop asking me things", delay=0))
        engine.post(engine.BY_TOPIC["you.pet"])
        before = len(self.thread())
        self.assertTrue(engine.after_reply(engine.conversation_id(), "I like dogs a lot", delay=0, reply="Dogs are wonderful."))
        for _ in range(100):
            if len(self.thread()) > before:
                break
            time.sleep(0.02)
        self.assertEqual(len(self.thread()), before + 1)

    def test_the_button_asks_something_now(self):
        self.assertIsNotNone(engine.nudge(at(14), self.rng))
        self.assertEqual(store.unread_count(), 0)


class Friend(CompanionTest):
    """The scheduler: when Seven reaches out and when it speaks. Time, idleness and speech are all supplied by the test."""

    def make(self, now=None, idle=60.0, touched=1000.0, busy=False, cfg=None, started=None):
        self.now = now or at(14)
        self.idle, self.touched, self.busy = idle, touched, busy
        self.said = []
        self.cfg = settings.normalize(cfg)
        c = scheduler.Companion(speak=self.said.append, busy=lambda: self.busy, cfg=lambda: self.cfg, clock=lambda: self.now,
                                rng=random.Random(3), idle=lambda: self.idle, since_touch=lambda: self.touched)
        c.started_at = started or (self.now - datetime.timedelta(hours=1))
        return c

    def test_when_everything_is_calm_it_writes_one_message_and_says_it(self):
        c = self.make()
        self.assertEqual(c.tick(), "spoke")
        self.assertEqual(len(self.said), 1)
        self.assertEqual(self.said[0], self.last_text())
        self.assertEqual(store.unspoken(), [])
        self.assertIn('"spoken": true', self.thread()[-1]["meta"])

    def test_it_waits_a_human_gap_before_the_next_one(self):
        c = self.make()
        c.tick()
        nxt = D.strptime(store.get_state("next_at"), store.FMT)
        self.assertTrue(at(14) + datetime.timedelta(minutes=7) <= nxt <= at(14) + datetime.timedelta(minutes=17, seconds=1))
        self.assertEqual(c.blocked(self.now, self.cfg), "gap")
        self.now = nxt + datetime.timedelta(seconds=1)
        self.assertIsNone(c.blocked(self.now, self.cfg))

    def test_each_reason_to_stay_quiet(self):
        cases = {"quiet": dict(now=at(23)), "start": dict(started=at(14) - datetime.timedelta(seconds=60)),
                 "active": dict(idle=5), "talking": dict(touched=10), "busy": dict(busy=True), "off": dict(cfg={"enabled": False})}
        for reason, kw in cases.items():
            c = self.make(**kw)
            self.assertEqual(c.blocked(self.now, self.cfg), reason, reason)
            self.assertIsNone(c.tick(), reason)
        c = self.make()
        store.set_state("snooze_until", (self.now + datetime.timedelta(hours=1)).strftime(store.FMT))
        self.assertEqual(c.blocked(self.now, self.cfg), "snoozed")

    def test_it_stops_at_the_days_number(self):
        c = self.make(cfg={"pace": "calm"})                              # 3 a day
        for _ in range(3):
            self.assertEqual(c.tick(), "spoke")
            self.now += datetime.timedelta(minutes=40)
            engine.note_user_message(engine.conversation_id(), "a cat", self.now)     # answered, so it is the number that stops it
        self.assertEqual(c.blocked(self.now, self.cfg), "cap")
        self.assertIsNone(c.tick())

    def test_the_auto_pace_stops_at_3_5_or_7_depending_on_the_day(self):
        totals = set()
        for day in range(1, 20):
            store.clear_all()
            c = self.make(now=at(12, 0, day))
            n = 0
            for _ in range(12):
                if c.tick() == "spoke":
                    n += 1
                    engine.note_user_message(engine.conversation_id(), "a cat")
                self.now += datetime.timedelta(minutes=40)
            totals.add(n)
            self.assertEqual(n, settings.daily_target(self.cfg, datetime.date(2026, 11, day)))
        self.assertTrue(len(totals) >= 2)

    def test_two_unanswered_messages_double_the_gap_and_three_give_you_space(self):
        c = self.make(cfg={"pace": "lively"})                                 # 7 a day, so it is not the day's number that stops it
        for t in content.ABOUT_YOU[:2]:
            engine.post(t, spoken=True, now=self.now)                      # said, and the person has not answered either
        c.tick()
        gap = (D.strptime(store.get_state("next_at"), store.FMT) - self.now).total_seconds() / 60
        self.assertTrue(14 <= gap <= 34.1, gap)
        self.now += datetime.timedelta(hours=2)
        self.assertEqual(c.blocked(self.now, self.cfg), "space")

    def test_one_message_waits_at_a_time_so_it_never_piles_up(self):
        c = self.make(idle=scheduler.AWAY_AFTER + 60)
        self.assertEqual(c.tick(), "wrote")
        self.now += datetime.timedelta(hours=1)
        self.assertEqual(c.blocked(self.now, self.cfg), "waiting")
        self.assertIsNone(c.tick())
        self.assertEqual(len(store.unspoken()), 1)

    def test_it_never_speaks_while_you_are_typing_or_in_a_conversation(self):
        for kw in (dict(idle=5), dict(touched=30)):
            c = self.make(**kw)
            engine.post(content.ABOUT_YOU[0])
            self.assertFalse(c.deliver(self.now, self.cfg))
            self.assertEqual(self.said, [])

    def test_when_you_are_busy_the_message_waits_in_the_chat_and_is_said_when_you_pause(self):
        c = self.make(idle=5)
        engine.post(content.ABOUT_YOU[0])
        self.assertIsNone(c.tick())
        self.assertEqual(len(store.unspoken()), 1)
        self.idle = 45
        self.assertEqual(c.tick(), "spoke")
        self.assertEqual(len(self.said), 1)
        self.assertEqual(store.unspoken(), [])

    def test_when_you_are_away_it_writes_but_does_not_talk_to_an_empty_room(self):
        c = self.make(idle=scheduler.AWAY_AFTER + 60)
        self.assertEqual(c.tick(), "wrote")
        self.assertEqual(self.said, [])
        self.assertEqual(len(store.unspoken()), 1)
        self.now += datetime.timedelta(minutes=45)
        self.idle = 30                                               # you are back
        self.assertEqual(c.tick(), "spoke")
        self.assertTrue(self.said[0].startswith("I left you a note while you were away."))

    def test_after_the_greeting_it_says_what_was_written_while_it_was_closed_or_you_were_away(self):
        c = self.make(idle=1, touched=1)                             # you just launched Seven
        for t in (content.ABOUT_YOU[0], content.FACTS[0]):
            engine.post(t)
        self.assertFalse(c.deliver(self.now, self.cfg))              # not an ordinary moment
        self.assertTrue(c.deliver(self.now, self.cfg, launch=True))
        self.assertTrue(self.said[0].startswith("I left you a few notes while you were away."))
        self.assertEqual(len(self.said), 2)
        self.assertEqual(store.unspoken(), [])

    def test_at_most_three_are_said_at_once(self):
        c = self.make()
        for t in content.ABOUT_YOU[:5]:
            engine.post(t)
        c.deliver(self.now, self.cfg, launch=True)
        self.assertEqual(len(self.said), 3)
        self.assertEqual(len(store.unspoken()), 2)

    def test_with_the_voice_off_it_only_writes(self):
        c = self.make(cfg={"voice": False})
        self.assertEqual(c.tick(), "wrote")
        self.assertEqual(self.said, [])
        self.assertEqual(store.unspoken(), [])                       # written for reading: nothing waits to be said later

    def test_quiet_hours_silence_the_voice_too(self):
        c = self.make(now=at(23))
        engine.post(content.ABOUT_YOU[0])
        self.assertFalse(c.deliver(self.now, self.cfg))
        self.assertTrue(c.deliver(self.now, self.cfg, launch=True) is True)       # you opened Seven yourself: that is you being here

    def test_it_remembers_when_you_were_last_here(self):
        c = self.make()
        c.tick()
        self.assertEqual(store.get_state("last_seen"), self.now.strftime(store.FMT))

    def test_the_old_silence_watcher_is_no_longer_started(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main_modules", "startup", "voice_loop.py"),
                   encoding="utf-8").read()
        self.assertNotIn("SilenceWatcher(", src)
        self.assertIn("companion", src)


class Routes(CompanionTest):
    def setUp(self):
        super().setUp()
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend.routes import companion as routes
        except Exception:
            self.skipTest("needs fastapi")
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)

    def test_state_has_everything_the_screen_needs(self):
        engine.post(content.ABOUT_YOU[0])
        body = self.client.get("/api/companion/state").json()
        self.assertEqual(body["conversation_id"], engine.conversation_id())
        self.assertEqual(body["unread"], 1)
        self.assertEqual(body["settings"]["pace"], "auto")
        self.assertIn(body["today"]["target"], (3, 5, 7))
        self.assertIsNone(body["snoozed_until"])

    def test_read_snooze_and_nudge(self):
        engine.post(content.ABOUT_YOU[0])
        self.assertEqual(self.client.post("/api/companion/read").json()["read"], 1)
        self.assertEqual(self.client.get("/api/companion/state").json()["unread"], 0)
        until = self.client.post("/api/companion/snooze", json={"minutes": 60}).json()["snoozed_until"]
        self.assertTrue(until)
        self.assertEqual(self.client.get("/api/companion/state").json()["snoozed_until"], until)
        self.assertIsNone(self.client.post("/api/companion/snooze", json={"minutes": 0}).json()["snoozed_until"])
        self.assertEqual(self.client.post("/api/companion/snooze", json={"minutes": 99999}).status_code, 422)
        self.assertIn("message_id", self.client.post("/api/companion/nudge").json())


if __name__ == "__main__":
    unittest.main()
