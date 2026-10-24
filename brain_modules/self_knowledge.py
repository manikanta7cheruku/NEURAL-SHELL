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
import re
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


def app_help_answer(text: str) -> Optional[str]:
    if time.time() - _last_refresh["t"] > 60:
        _last_refresh["t"] = time.time()
        try:
            app_map.refresh_if_stale()
        except Exception:
            pass
    hits = app_map.search(text)
    if not hits:
        return None              # not about the app after all ("what's the temperature outside"): let it continue
    return app_map.describe(hits[0])


def model_can_phrase(name: str = "") -> bool:
    """Models of 3B and up phrase an answer from given facts well; the 1B model drifts, so it gets a template."""
    from brain_modules import model_catalog
    name = name or _active_model()
    entry = model_catalog.get(name)
    if entry:
        return entry["size_gb"] >= 2.0
    return bool(re.search(r"\b(?:[3-9]|[1-9]\d)(?:\.\d)?b\b", (name or "").lower()))


def capability_list_answer(norm: str, state=None, ctx=None) -> str:
    toks = set(norm.split())
    if toks & {"app", "apps", "programs", "applications", "open"}:
        cap = capabilities.get("apps")
        base = capabilities.describe(cap)
        return base + " I don't keep a list of every app. If it's installed, say \"open\" and its name and I'll find it."
    if re.search(r"\b(?:list|bullet|bullets|points|one by one|step by step|everything)\b", norm):
        return capabilities.overview_list()
    # Asked again in the same chat: a short reply, not the same paragraph word for word.
    turn = getattr(state, "turn", None)
    last = getattr(state, "last_overview_turn", None)
    brief = turn is not None and last is not None and turn - last <= 8
    asked = (getattr(state, "overview_count", 0) or 0) + 1
    if state is not None and turn is not None:
        try:
            state.last_overview_turn, state.overview_count = turn, asked
        except Exception:
            pass
    if ctx is not None and getattr(ctx, "stream_mode", "") != "sentence" and model_can_phrase():
        # The facts come from the registry; the model only says them, so it reads like a person, not a script.
        ctx.inject_capabilities = True
        if brief:
            ctx.hints.append("The user asked what you can do a moment ago. Answer in one or two sentences, worded "
                             "differently, and point them to the Guide page for clickable examples.")
        return None
    return capabilities.overview(brief=brief, variant=asked)


def value_answer() -> str:
    return ("Because it puts your whole computer one sentence away, without giving your data to anyone. "
            "Say what you want and Seven does it on this PC: opens and arranges apps, changes settings, finds files, "
            "brings back your workspace and keeps your reminders, in milliseconds. It runs entirely on this computer, "
            "works offline, remembers what you tell it and shows you everything it knows. "
            "And it never says something worked unless it did.")


def share_answer() -> str:
    """Something the user can send a friend, written in their voice, not Seven's."""
    return ("Here's something you can send them:\n\n\"Try Seven. It's an assistant that runs on your own PC, not in "
            "the cloud. You say or type what you want and it does it: opens apps, finds your files, arranges windows, "
            "brings back your whole study or work setup in one sentence, and answers from your own notes and PDFs with "
            "page numbers. It works offline and keeps everything on your computer.\"")


def symbol_answer() -> str:
    return ("The orb on the home screen. It's how I show what I'm doing: calm while I wait, and it changes when I'm "
            "listening, thinking or speaking. Around it is the SEVEN wordmark. Underneath, I'm a layer between you "
            "and this computer, running entirely on this machine.")


# ── Seven explaining itself: model, context, memory, learning, reasoning ─────────────────────────
# Asked for, never volunteered. Every number is read live, so the answer is true for this install.

def _active_model() -> str:
    try:
        from brain_modules import self_model
        return self_model.get_runtime_state()["model_name"]
    except Exception:
        return "an unknown model"


def _words(tokens: int) -> str:
    return f"{int(round(tokens * 0.75, -2)):,}"


def model_answer(ctx, config) -> str:
    """What model runs Seven, and what it is good and less good at."""
    from brain_modules import model_catalog
    name = _active_model()
    entry = model_catalog.get(name)
    if not entry:
        return (f"I'm running {name} on this computer through Ollama. It isn't one of the models I know the "
                "details of, so I can't tell you its strengths. Settings, Brain lists the ones I do.")
    text = (f"I'm running {entry['name']} by {entry['maker']}, {entry['params']} parameters, on this computer "
            f"through Ollama. It's good at {entry['good_at']}, and less suited to {entry['weak_at']}. "
            f"It reads about {_words(model_catalog.context_window(name))} words of our conversation at a time.")
    try:
        from brain_modules import system_info
        snap = system_info.snapshot()
        gpu = snap.get("gpu") or {}
        rec = model_catalog.recommend(float(gpu.get("vram_gb") or 0), float((snap.get("ram") or {}).get("total_gb") or 0),
                                      bool(gpu.get("name")))
        better = model_catalog.get(rec["id"])
        if better and better["size_gb"] > entry["size_gb"]:
            text += (f" If you want sharper answers, {better['name']} suits this PC; you can download and switch "
                     "to it in Settings, Brain.")
    except Exception:
        pass
    return text


def context_answer(ctx, config) -> str:
    """How much Seven reads at once versus how much it keeps."""
    from brain_modules import chat_history, model_catalog
    ttl = int(_cfg(config, "brain.history_ttl_seconds", 1800) or 1800)
    span = f"{ttl // 3600} hour{'s' if ttl >= 7200 else ''}" if ttl >= 3600 else f"{max(1, ttl // 60)} minutes"
    try:
        from memory import conversation_store, facts_store
        key = getattr(ctx, "speaker_key", None)
        stored = (f" So far that's {facts_store.count_facts(key)} things about you and "
                  f"{conversation_store.count_conversations(key)} conversations.")
    except Exception:
        stored = ""
    return ("Think of it as two kinds of memory. In the moment, the model reads about "
            f"{_words(model_catalog.context_window(_active_model()))} words at once: roughly the last "
            f"{chat_history.MAX_TURNS} exchanges of this chat from the past {span}. Beyond that, nothing is "
            "thrown away. Every conversation and everything you tell me is kept on this computer, limited only by "
            f"disk space.{stored} I look those up when they matter, like when you ask about yourself or say "
            '"last time", instead of rereading everything for every reply. That keeps me fast.')


def learning_answer() -> str:
    return ("Yes, in the ways that matter for you. I learn from what you tell me and from how things go: facts "
            "about you and your corrections (keeping the history), your goals, which app you mean by a name, which "
            "actions tend to fail, and how you like me to talk. What I don't do is retrain the model itself, so my "
            "general intelligence stays the same while what I know about you and this computer keeps growing. "
            "All of it stays on this machine, and you can see or delete it on the Memory page.")


_HOW = {
    "layer_03_identity": "That's built into me. Facts about myself, the time and your PC are read directly, not "
                         "generated, so they can't be made up.",
    "layer_025_social": "Just a quick reply. Small talk doesn't need the AI model, so it's answered instantly.",
    "layer_05_memory": "From what you told me earlier, stored on this computer. No guessing involved.",
    "layer_06_personal_filter": "I didn't have anything stored about that, so I said so rather than guess.",
    "layer_035_router": "From my own knowledge of this app and what you've told me, not from the AI model.",
    "layer_034_settings": "That was a settings change. I made it directly and confirmed the new value.",
    "layer_56_live_guard": "That needed live information I couldn't get, so I told you instead of guessing.",
}


def reasoning_answer(ctx) -> str:
    """Why Seven answered the previous message the way it did, from that turn's trace."""
    trace = dict(getattr(getattr(ctx, "state", None), "trace", None) or {})
    by = trace.get("answered_by") or ""
    if not by:
        return "I don't have a record of my last answer in this chat yet. Ask me something and then ask again."
    if by == "layer_08_llm":
        model = trace.get("model") or _active_model()
        from brain_modules import model_catalog
        entry = model_catalog.get(model)
        who = entry["name"] if entry else model
        src = [s.replace("_", " ") for s in trace.get("sources") or []]
        used = (f", using {', '.join(src)} as evidence" if src
                else ", from its general knowledge. Nothing you told me was involved")
        extra = ""
        if trace.get("mode") == "deep":
            extra += " I treated it as a harder question and took more care over it."
        if trace.get("uncertainty"):
            extra += " Part of it was uncertain, and I was told to say so rather than guess."
        return f"That reply was written by the language model, {who}, running on this computer{used}.{extra}"
    if trace.get("detail") == "pc":
        return ("I read it live from Windows. The graphics driver, processor and memory report those numbers "
                "directly, so nothing was guessed, and none of it left this computer.")
    if by.startswith(("layer_45", "layer_43", "layer_036", "layer_38", "layer_59")):
        return ("That was a direct command. I handled it instantly in code, without the AI model, and then checked "
                "whether the action actually worked before telling you.")
    return _HOW.get(by, "That came from one of my built-in skills rather than the AI model, so it's exact.")


def answer(label: str, ctx, config) -> Optional[str]:
    """Dispatch a routed self-knowledge intent. None means 'not mine, let the pipeline continue'."""
    norm = ctx.norm_in
    if label == "capability_list":
        return capability_list_answer(norm, getattr(ctx, "state", None), ctx)
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
    if label == "self_value":
        return value_answer()
    if label == "self_model":
        return model_answer(ctx, config)
    if label == "self_context":
        return context_answer(ctx, config)
    if label == "self_learning":
        return learning_answer()
    if label == "self_reasoning":
        return reasoning_answer(ctx)
    if label == "self_share":
        return share_answer()
    if label == "self_symbol":
        return symbol_answer()
    return None
