"""
Shared harness for brain tests. Everything external is isolated:

    - ollama:  a fake token stream (tests assert on the exact prompt sent)
    - web:     FakeWeb injected through brain.EXTRA_DEPS (never the real internet)
    - storage: fresh temporary databases per test
    - clock/network: web_provider.set_online_override

Import this module first in every test file.
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if not os.path.exists(os.path.join(ROOT, "brain_modules", "conversation_thread.py")):
    sys.path.append(os.path.join(ROOT, "tests", "stubs"))   # standalone run: only the folder was extracted
os.environ.update(SEVEN_TEST="1", SEVEN_DISABLE_CHROMA="1", SEVEN_DISABLE_MIGRATION="1")
_BASE = tempfile.mkdtemp(prefix="seven_t_")
os.environ["APPDATA"] = _BASE
os.environ["SEVEN_TASKS_DB"] = os.path.join(_BASE, "tasks.db")   # never the real seven_data/tasks.db
os.environ["SEVEN_TRIGGERS_DB"] = os.path.join(_BASE, "triggers.db")   # nor the real triggers and workspaces
os.environ["SEVEN_KNOWLEDGE_DIR"] = os.path.join(_BASE, "knowledge")   # nor the real document library

import config                                                    # noqa: E402
from brain_modules import (capabilities, chat_history, conversation_state, learning, ollama_client,  # noqa: E402
                           social_engine, web_provider)
from brain_modules.conversation_thread import ConversationThread  # noqa: E402
from memory import conversation_store, facts_store, learning_store, limits  # noqa: E402

LLM_CALLS = []
LLM_REPLY = ["It holds up. ", "Great movie."]


def _fake_stream(payload):
    LLM_CALLS.append(payload)
    for tok in LLM_REPLY:
        yield tok


ollama_client.stream_chat = _fake_stream
import brain                                                     # noqa: E402


class FakeWeb:
    """Controlled web provider: status ok | offline | disabled | error | empty | not_needed."""

    def __init__(self, status="not_needed", text="", needed=None):
        self.status, self.text = status, text
        self.needed = (status != "not_needed") if needed is None else needed
        self.queries = []

    def lookup(self, text, cfg):
        self.queries.append(text)
        return web_provider.WebOutcome(self.status, self.text if self.status == "ok" else "", text, self.needed)


class FakeTaskStore:
    """In-memory stand-in for the Dashboard's tasks database, with the same interface as SqliteTaskStore."""

    def __init__(self, *texts):
        self.rows = {}
        self._next = 1
        for t in texts:
            self.add(t)

    def add(self, text):
        self.rows[self._next] = {"id": self._next, "text": text, "completed": False}
        self._next += 1
        return self._next - 1

    def pending(self):
        return [dict(r) for r in self.rows.values() if not r["completed"]]

    def get(self, task_id):
        r = self.rows.get(task_id)
        return dict(r) if r else None

    def find(self, search):
        words = (search or "").lower().split()
        for r in self.rows.values():
            if not r["completed"] and all(w in r["text"].lower() for w in words):
                return dict(r)
        return None

    def complete(self, task_id):
        self.rows[task_id]["completed"] = True

    def delete(self, task_id):
        self.rows.pop(task_id, None)

    def open_texts(self):
        return [r["text"] for r in self.rows.values() if not r["completed"]]


def reset_config():
    d = config.get_defaults()
    config.update_config({k: d[k] for k in ("brain", "memory", "web", "identity") if k in d})
    config.update_config({"brain": {"curiosity_level": "normal", "reasoning_model": "", "streaming": True,
                                    "model_name": "auto"}, "commands": {"app_aliases": {}}})
    config.update_config({"privacy": {"telemetry_enabled": True}, "storage": {"max_mb": 0},
                          "updates": {"auto_check": True}, "agent": {"confirm_risky": True}})


class BrainTest(unittest.TestCase):
    """Base class: every test starts from a clean, isolated world."""

    def setUp(self):
        base = tempfile.mkdtemp(prefix="seven_case_", dir=_BASE)
        facts_store.set_db_path(os.path.join(base, "facts.db"))
        conversation_store.set_db_path(os.path.join(base, "conv.db"))
        learning_store.set_db_path(os.path.join(base, "learn.db"))
        reset_config()
        limits.reset_cache()
        for r in (conversation_state.reset, social_engine.reset, chat_history.clear, learning.clear_cache):
            r()
        ConversationThread._threads.clear()
        ConversationThread._metadata.clear()
        capabilities._overrides.clear()
        web_provider.set_online_override(True)
        brain.USER_NAME, brain._name_loaded = "there", True
        brain.EXTRA_DEPS.clear()
        brain.EXTRA_DEPS["web"] = FakeWeb()
        brain.EXTRA_DEPS["tasks"] = FakeTaskStore()
        LLM_CALLS.clear()
        social_engine.seed(5)
        self.conv = brain.resolve_conversation("default")

    def tearDown(self):
        web_provider.set_online_override(None)
        brain.EXTRA_DEPS.clear()

    def ask(self, text, conv=None, mode="text", speaker="default"):
        r = brain.think(text, speaker, mode, conv or self.conv)
        return "".join(r[1]) if isinstance(r, tuple) else r

    def tasks(self, *texts):
        """Install a fake task database holding these pending tasks."""
        brain.EXTRA_DEPS["tasks"] = FakeTaskStore(*texts)
        return brain.EXTRA_DEPS["tasks"]

    def run_tags(self, reply, store):
        """Execute the ###TASK tags in a reply with the real shared executor (what chat.py does in production)."""
        import re
        from brain_modules import lifecycle
        done = []
        for chunk in re.findall(r"###TASK:\s*(.*?)(?=###|$)", reply, re.DOTALL):
            params = dict(p.split("=", 1) for p in chunk.split() if "=" in p)
            done.append(lifecycle.execute_task_action(params, store))
        return done

    def web(self, status="not_needed", text=""):
        brain.EXTRA_DEPS["web"] = FakeWeb(status, text)
        return brain.EXTRA_DEPS["web"]

    def trace(self, conv=None):
        return brain.get_trace("default", conv or self.conv)

    def llm_user_message(self):
        return LLM_CALLS[-1]["messages"][-1]["content"]

    def llm_system(self):
        return LLM_CALLS[-1]["messages"][0]["content"]
