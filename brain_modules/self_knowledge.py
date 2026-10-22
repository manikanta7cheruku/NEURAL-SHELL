"""
brain_modules/self_knowledge.py

Grounded answers about Seven itself: what it can do right now, how the app
works, where data lives and what leaves the machine, and current status.

Every answer is BUILT from live sources (capability registry + status, the
generated app map, the real configuration, the last action receipts), never
from a canned paragraph, so two related questions cannot contradict each other
("stored in a database" versus "not on my device").
"""

import os
import time
from typing import Any, Dict, List, Optional

from brain_modules import action_receipts, app_map, capabilities, speech_acts, web_provider

_last_refresh = {"t": 0.0}


def _cfg(config, path: str, default: Any = None) -> Any:
    cur: Any = getattr(config, "KEY", config)
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def data_folder() -> str:
    try:
        from memory import facts_store
        return os.path.dirname(facts_store.get_db_path())
    except Exception:
        return "your SEVEN data folder"


def outbound_flows(config) -> List[str]:
    """Everything that can leave this machine, given the CURRENT settings."""
    flows = []
    if _cfg(config, "web.enabled", True):
        flows.append("when I look something up online, the search text goes to the search provider (only for "
                     "questions that need live information)")
    flows.append("license checks send your license key and a device id to Seven's license server")
    if _cfg(config, "privacy.telemetry_enabled", True):
        flows.append("usage statistics (a device id, your email if you gave one, your country and how long Seven "
                     "is active) go to Seven's server; you can turn this off in Settings")
    if _cfg(config, "updates.auto_check", True):
        flows.append("update checks contact the release server on GitHub")
    return flows


def data_flow_answer(norm: str, config) -> str:
    """One consistent story, shaped by what was asked."""
    folder = data_folder()
    storage = (f"Your conversations, the facts I remember and the search index are stored on this computer, in "
               f"{folder}.")
    inference = "I run the language model locally through Ollama, so what you say to me is not sent to an AI service."
    out = outbound_flows(config)
    exceptions = ("Some things do use the internet: " + "; ".join(out) + ".") if out else \
        "Nothing leaves this machine right now."
    toks = set(norm.split())
    if toks & {"where", "stored", "saved", "keep", "kept", "store"} and not toks & {"send", "share", "cloud", "private"}:
        return storage
    if toks & {"device", "locally", "local", "computer", "pc", "machine"}:
        return f"Yes. {storage} {exceptions}"
    return f"{inference} {storage} {exceptions}"


def status_answer(norm: str, ctx, config) -> Optional[str]:
    toks = set(norm.split())
    state = getattr(ctx, "state", None)
    if toks & {"worked", "succeed", "succeeded", "open", "opened", "work"} and (
            "that" in toks or "it" in toks or "last" in toks):
        return action_receipts.summarize(getattr(state, "last_receipts", []) or [])
    if toks & {"internet", "online"}:
        on = web_provider.is_online()
        return "Yes, I can reach the internet right now." if on else \
            "No. I have no internet right now, so live lookups like weather and news are unavailable."
    if "web" in toks or "search" in toks:
        if not _cfg(config, "web.enabled", True):
            return "Web search is switched off in Settings."
        return "Web search is on and I'm online." if web_provider.is_online() else \
            "Web search is on, but I'm offline, so it can't run right now."
    if "model" in toks:
        from brain_modules import self_model
        return f"I'm using {self_model.get_runtime_state()['model_name']}, running locally through Ollama."
    if "streaming" in toks:
        return "Streaming is on." if _cfg(config, "brain.streaming", True) else "Streaming is off."
    if toks & {"memory", "remember", "conversations"}:
        try:
            from memory import conversation_store, facts_store
            facts = facts_store.count_facts(getattr(ctx, "speaker_key", None))
            chats = conversation_store.count_conversations(getattr(ctx, "speaker_key", None))
            return f"I'm keeping {facts} facts about you and {chats} saved conversations. All of it is stored on this computer."
        except Exception:
            return None
    return None


def app_help_answer(text: str) -> str:
    if time.time() - _last_refresh["t"] > 60:
        _last_refresh["t"] = time.time()
        try:
            app_map.refresh_if_stale()
        except Exception:
            pass
    hits = app_map.search(text)
    if not hits:
        return "I don't have notes on that part of the app yet."
    return app_map.describe(hits[0])


def capability_list_answer(norm: str) -> str:
    toks = set(norm.split())
    if toks & {"app", "apps", "programs", "applications", "open"}:
        cap = capabilities.get("apps")
        base = capabilities.describe(cap)
        return base + " I don't keep a list of every app. If it's installed, say \"open\" and its name and I'll find it."
    return capabilities.overview()


def answer(label: str, ctx, config) -> Optional[str]:
    """Dispatch a routed self-knowledge intent. None means 'not mine, let the pipeline continue'."""
    norm = ctx.norm_in
    if label == "capability_list":
        return capability_list_answer(norm)
    if label == "capability_check":
        reply = capabilities.answer_can_you(norm)
        if reply:
            return reply
        hits = capabilities.find(norm, 1)
        return capabilities.describe(hits[0]) if hits else None
    if label == "app_help":
        return app_help_answer(ctx.prompt_text)
    if label == "data_flow":
        return data_flow_answer(norm, config)
    if label == "status_check":
        return status_answer(norm, ctx, config)
    return None
