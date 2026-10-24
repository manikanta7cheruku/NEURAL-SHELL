"""
PROJECT SEVEN - brain.py (The Orchestrator)
Version: 4.0

think() runs one user message through the layer pipeline and returns a string,
"" (intentional silence) or ("__STREAM__", generator).

NEW IN 4.0:
    - Real conversations: every call belongs to a conversation id (client
      supplied or the current one). Short-term context is keyed by
      "<speaker>#<conversation>", so a NEW CHAT is clean while long-term facts
      stay available. The user message is saved to the transcript FIRST; if
      storage fails the caller is told instead of being lied to.
    - Compound messages: a name statement followed by more ("My name is 77.
      Remember that ...") no longer drops the rest; acknowledgements are
      prefixed to the final reply.
    - Action receipts feed back: results update working memory, outcomes are
      recorded, and a failed-then-corrected launch can become a confirmed alias.
    - Risky actions can ask for confirmation (request_confirmation).
"""

import logging
import os
import random
import re
import threading

import colorama
from colorama import Fore

colorama.init(autoreset=True)

import config

try:
    from memory import seven_memory
    from memory.mood import mood_engine
except Exception:
    seven_memory = None
    mood_engine = None

from brain_modules import conversation_state, session, speech_acts
from brain_modules.context import BrainContext
from brain_modules.pipeline import run as run_pipeline

_log = logging.getLogger("seven.brain")

try:
    if os.environ.get("SEVEN_TEST") == "1":
        MODEL_NAME = "test-model"
    else:
        from brain_modules.model_selector import select_model
        MODEL_NAME = select_model()
except Exception as _model_err:
    _log.warning("Model selector failed (%s). Reading from config.", _model_err)
    try:
        MODEL_NAME = config.KEY["brain"]["model_name"]
    except Exception:
        MODEL_NAME = "tinyllama"

print(f"[BRAIN] Active model: {MODEL_NAME}")


def _configured_model() -> str:
    try:
        return (config.KEY.get("brain", {}).get("model_name") or "auto").strip()
    except Exception:
        return "auto"


_model_cfg_seen = _configured_model()


def current_model() -> str:
    """
    The model for this message. MODEL_NAME is chosen at startup; when Settings
    or a chat request changes brain.model_name, re-select it here so the change
    applies to the next reply instead of after a restart.
    """
    global MODEL_NAME, _model_cfg_seen
    cfg = _configured_model()
    if cfg == _model_cfg_seen:
        return MODEL_NAME
    _model_cfg_seen = cfg
    if os.environ.get("SEVEN_TEST") == "1":          # no Ollama in tests
        MODEL_NAME = cfg if cfg.lower() != "auto" else "test-model"
        return MODEL_NAME
    try:
        from brain_modules.model_selector import select_model
        MODEL_NAME = select_model()
    except Exception as exc:
        _log.warning("model re-selection failed (%s); using the configured name", exc)
        if cfg.lower() != "auto":
            MODEL_NAME = cfg
    _model_cfg_seen = _configured_model()      # an "auto" pick is written back to config
    _log.info("model switched to %s", MODEL_NAME)
    try:
        from brain_modules import ollama_client, self_model
        self_model.set_active_model(MODEL_NAME)
        threading.Thread(target=ollama_client.warmup, args=(MODEL_NAME,), daemon=True,
                         name="ModelSwitchWarmup").start()
    except Exception as exc:
        _log.debug("warm-up after model switch skipped: %s", exc)
    return MODEL_NAME

USER_NAME = "Admin"
EXTRA_DEPS: dict = {}     # dependency injection point (tests inject a fake web provider here)
_name_loaded = False
_CAP_OF_TAG = {"OPEN": "apps", "CLOSE": "apps", "WINDOW": "windows", "SYS": "system", "SCHED": "reminders",
               "TASK": "tasks"}


def load_name_from_memory():
    global USER_NAME
    USER_NAME = session.get_user_name() or "there"


def ensure_name_loaded():
    global _name_loaded
    if not _name_loaded:
        load_name_from_memory()
        _name_loaded = True


def _refresh_user_name():
    global USER_NAME
    name = session.get_user_name()
    if name:
        USER_NAME = name


def reset_session():
    """Forget short-term state for every chat (history, streaks, pending questions). Facts are kept."""
    global USER_NAME
    USER_NAME = "Admin"
    try:
        from brain_modules import chat_history, learning, social_engine
        from brain_modules.conversation_thread import ConversationThread
        chat_history.clear()
        social_engine.reset()
        learning.clear_cache()
        conversation_state.reset()
        ConversationThread._threads.clear()
    except Exception as exc:
        _log.warning("session reset incomplete: %s", exc)


def new_conversation(speaker_id: str = "default", title=None) -> str:
    """Start a clean chat. The old one stays saved; long-term memory is untouched."""
    from memory import conversation_store
    ensure_name_loaded()
    return conversation_store.create_conversation(session.resolve_key(speaker_id, USER_NAME), title)


def resolve_conversation(speaker_id: str = "default", conversation_id=None) -> str:
    """The conversation a message will belong to (client id if valid, else the current chat)."""
    from memory import conversation_store
    ensure_name_loaded()
    return conversation_store.ensure(session.resolve_key(speaker_id, USER_NAME), conversation_id)


def get_trace(speaker_id: str, conversation_id: str) -> dict:
    key = session.resolve_key(speaker_id, USER_NAME)
    return dict(conversation_state.get(f"{key}#{conversation_id}").trace)


def save_completed_turn(prompt_text, response_text, speaker_id, source="chat", persist=True,
                        conversation_id=None, thread_key=None):
    """
    Record a finished exchange: transcript (always), session thread (for
    repetition and follow-ups) and, when persist=True, the legacy Chroma
    conversation document used by the Memory page (written on the worker).
    """
    try:
        if not prompt_text or not response_text:
            return
        p = prompt_text.strip()
        r = re.sub(r"###\w+:\s*\S+", "", response_text).strip()
        key = session.resolve_key(speaker_id, USER_NAME)
        tkey = thread_key or (f"{key}#{conversation_id}" if conversation_id else key)
        if conversation_id and r:
            try:
                from memory import conversation_store
                conversation_store.add_message(conversation_id, "assistant", r, source=source)
                if os.environ.get("SEVEN_TEST") != "1":
                    from brain_modules import chat_title
                    chat_title.maybe_retitle(conversation_id, current_model())
            except Exception as exc:
                _log.warning("assistant message not saved: %s", exc)
                conversation_state.get(tkey).trace["storage_error"] = str(exc)
        if len(p) <= 3 or not r or speech_acts.is_greeting(speech_acts.normalize(p)):
            return
        from brain_modules.conversation_thread import ConversationThread
        ConversationThread.add_turn(tkey, p, r)
        try:
            from brain_modules.followup_detector import detect_followup
            followup = detect_followup(r)
            if followup:
                ConversationThread.set_metadata(tkey, "followup_hint", followup)
        except Exception as exc:
            _log.debug("follow-up detection skipped: %s", exc)
        if persist:
            from brain_modules import idle_worker
            idle_worker.enqueue("store_conversation", {
                "user_input": p, "response": r, "speaker_key": key, "source": source})
    except Exception as exc:
        _log.warning("save_completed_turn failed: %s", exc)


def store_voice_turn(prompt_text, response_text, speaker_id, was_interrupted=False):
    save_completed_turn(prompt_text, response_text, speaker_id, source="voice", persist=not was_interrupted)


# ---- actions: receipts, learning from outcomes, confirmation -------------

def note_receipts(speaker_id: str, conversation_id: str, receipts: list):
    """
    Feed action receipts back into Seven. Records outcomes (tool reliability),
    updates working memory (for "did that work?"), and offers to learn an
    alias when a failed launch was followed by a verified different one.
    Returns an optional follow-up question to append to the reply.
    """
    key = session.resolve_key(speaker_id, USER_NAME)
    tkey = f"{key}#{conversation_id}"
    st = conversation_state.get(tkey)
    st.last_receipts = [r.to_dict() if hasattr(r, "to_dict") else r for r in receipts]
    question = None
    try:
        from memory import learning_store
        for r in st.last_receipts:
            cap = _CAP_OF_TAG.get(r["kind"].upper(), r["kind"].lower())
            learning_store.record_outcome(key, "action", cap, r["status"], f"{r['kind']} {r['target']} {r['detail']}",
                                          conversation_id)
            if r["kind"].upper() == "OPEN":
                if r["status"] == "failed":
                    st.last_failed_open = (r["target"], st.turn)
                elif r["status"] == "success" and r.get("verified") and st.last_failed_open:
                    bad, turn = st.last_failed_open
                    if st.turn - turn <= 3 and bad.lower() != r["target"].lower():
                        conversation_state.set_pending(st, "alias_confirm", {"alias": bad, "target": r["target"]}, 3)
                        question = f"By the way, want me to remember that \"{bad}\" means {r['target']}?"
                    st.last_failed_open = None
    except Exception as exc:
        _log.debug("receipt learning skipped: %s", exc)
    return question


def needs_confirmation(kind: str, arg: str) -> bool:
    """High-risk actions pause for a yes (configurable under agent.confirm_risky)."""
    if not config.KEY.get("agent", {}).get("confirm_risky", True):
        return False
    return (kind == "CLOSE" and arg.strip().upper().startswith("ALL_")) or (
        kind == "SYS" and ("airplane_on" in arg or "empty_recycle_bin" in arg))


def request_confirmation(speaker_id: str, conversation_id: str, tags: str, description: str) -> str:
    key = session.resolve_key(speaker_id, USER_NAME)
    st = conversation_state.get(f"{key}#{conversation_id}")
    conversation_state.set_pending(st, "confirm_action", {"tags": tags}, ttl=2)
    return f"{description} Say yes to confirm."


# ---- references to earlier results (unchanged behavior) ------------------

def _execute_resolved_reference(resolved: dict):
    if not resolved or not isinstance(resolved, dict):
        return None
    action, reason = resolved.get("action"), resolved.get("reason", "")
    if action == "none":
        return random.choice(["I lost track of what you meant. Could you say that again?",
                              f"Not sure what to open. {reason.capitalize()}." if reason else "Not sure what you meant.",
                              "Could you tell me which one you want?"])
    if action == "ambiguous":
        count = len(resolved.get("options", []))
        return random.choice([f"I see {count} that match. Which one, top to bottom?",
                              f"Got {count} matches. Tell me the number."])
    if action in ("open", "repeat"):
        target = resolved.get("target") or {}
        path, name = target.get("path"), target.get("name", "it")
        if not path:
            return None
        try:
            from hands.files import open_file
            ok = open_file(path)
            try:
                from brain_modules.dialogue_manager import get_last_action, remember_action
                last = get_last_action()
                if last and target in last.get("results", []):
                    remember_action(last["type"], last["query"], last["results"],
                                    opened_index=last["results"].index(target))
            except Exception as exc:
                _log.debug("memory update after open skipped: %s", exc)
            if ok:
                return random.choice(["Opening it again.", "Reopening now."] if action == "repeat"
                                     else ["Opening it now.", "Got it, opening.", "Here you go.", "Opened."])
            return f"I tried but could not open {name}."
        except Exception as exc:
            return f"Ran into an issue opening it: {exc}"
    return None


def _migrate_speaker_key(old: str, new: str) -> None:
    """The owner just set a name: keep everything learned so far (the key is derived from the name)."""
    try:
        from memory import conversation_store, fact_service, facts_store, learning_store
        moved = facts_store.rename_speaker(old, new)
        conversation_store.rename_speaker(old, new)
        learning_store.rename_speaker(old, new)
        if moved:
            from brain_modules import idle_worker
            idle_worker.enqueue("reindex", {})
    except Exception as exc:
        _log.warning("speaker key migration failed: %s", exc)


# ---- the main entry point ------------------------------------------------

def _prefix_stream(acks: str, gen):
    yield acks + " "
    for piece in gen:
        yield piece


def _with_prefix(ctx, result):
    acks = " ".join(ctx.prefix_acks).strip()
    if not acks:
        return result
    if isinstance(result, tuple):
        return (result[0], _prefix_stream(acks, result[1]))
    return f"{acks} {result}".strip()


def think(prompt_text, speaker_id="default", stream_mode="sentence", conversation_id=None, documents=None):
    """
    Run the pipeline for one message.

    stream_mode: "sentence" (voice), "token" (console), "text" (a string).
    conversation_id: the chat this message belongs to (None = current chat).
    documents: library ids attached to this message; they stay attached to the chat.
    """
    global USER_NAME
    ensure_name_loaded()
    _refresh_user_name()
    key = session.resolve_key(speaker_id, USER_NAME)
    # The voice loop asks for sentences; the console and API ask for tokens or text.
    source = "voice" if stream_mode == "sentence" else "chat"

    conv_id, storage_error, user_msg_id = "", "", None
    try:
        from memory import conversation_store
        conv_id = conversation_store.ensure(key, conversation_id)
        user_msg_id = conversation_store.add_message(
            conv_id, "user", prompt_text, source=source)
    except Exception as exc:
        storage_error = str(exc)
        _log.warning("transcript not saved: %s", exc)
    tkey = f"{key}#{conv_id}" if conv_id else key

    try:
        from brain_modules.correction_detector import detect_correction
        from brain_modules.tone_tracker import observe as observe_tone
        observe_tone(key, prompt_text, bool(detect_correction(prompt_text)))
    except Exception as exc:
        _log.debug("tone tracking skipped: %s", exc)

    def _done(reply):
        save_completed_turn(prompt_text, reply, speaker_id, source=source, persist=False,
                            conversation_id=conv_id, thread_key=tkey)
        conversation_state.get(tkey).trace = {"answered_by": "dialogue", "storage_error": storage_error}
        return reply

    try:
        from brain_modules.dialogue_manager import check_pending, has_pending
        if has_pending():
            reply = check_pending(prompt_text)
            if reply:
                return _done(reply)
    except Exception as exc:
        _log.debug("dialogue check skipped: %s", exc)
    try:
        from brain_modules.dialogue_manager import looks_like_reference, resolve_reference
        if looks_like_reference(prompt_text):
            resolved = resolve_reference(prompt_text)
            reply = _execute_resolved_reference(resolved) if resolved else None
            if reply:
                return _done(reply)
    except Exception as exc:
        _log.warning("reference resolve error: %s", exc)

    ctx = BrainContext(prompt_text=prompt_text, speaker_id=speaker_id, user_name=USER_NAME)
    ctx.stream_mode, ctx.speaker_key = stream_mode, key
    ctx.conversation_id, ctx.thread_key = conv_id, tkey
    ctx.user_msg_id, ctx.storage_error = user_msg_id, storage_error
    if documents:
        ctx.documents = list(documents)
        try:
            from knowledge import store
            store.attach(conv_id, ctx.documents)
        except Exception as exc:
            _log.warning("documents not attached: %s", exc)
    deps = {"seven_memory": seven_memory, "mood_engine": mood_engine, "config": config, "model_name": current_model()}
    deps.update(EXTRA_DEPS)

    result = _with_prefix(ctx, run_pipeline(ctx, deps))
    if ctx.new_user_name:
        USER_NAME = ctx.new_user_name
        new_key = session.resolve_key(speaker_id, USER_NAME)
        if new_key != key:
            _migrate_speaker_key(key, new_key)
    st = conversation_state.get(tkey)
    if isinstance(result, tuple):
        st.trace.setdefault("storage_error", storage_error)
        return result
    if ctx.answered_by != "layer_08_llm":
        st.trace = {"answered_by": ctx.answered_by, "intent": getattr(ctx.intent, "label", None),
                    "detail": getattr(ctx, "answered_detail", None),
                    "storage_error": storage_error, "confirmed": ctx.confirmed}
        save_completed_turn(prompt_text, result, speaker_id, source=source, persist=False,
                            conversation_id=conv_id, thread_key=tkey)
        conversation_state.observe_reply(st, result or "")
        try:
            from brain_modules import followups
            followups.remember(st, result or "")
        except Exception as exc:
            _log.debug("follow-up memory skipped: %s", exc)
    return result


_warmed = False


def warm_up():
    """Load the model, probe hardware, refresh the app map and (later) the embedder in the background."""
    global _warmed
    if _warmed or os.environ.get("SEVEN_TEST") == "1":
        return
    _warmed = True
    try:
        from brain_modules import app_map, ollama_client, self_model
        self_model.set_active_model(MODEL_NAME)
        self_model.prime_async()
        ollama_client.warmup(MODEL_NAME)
        threading.Thread(target=app_map.refresh_if_stale, daemon=True, name="AppMapRefresh").start()
    except Exception as exc:
        _log.debug("warm-up skipped: %s", exc)

    def _warm_memory():
        try:
            from memory import core as memory_core
            memory_core._get_instance()
        except Exception as exc:
            _log.debug("memory warm-up skipped: %s", exc)

    timer = threading.Timer(25.0, _warm_memory)
    timer.daemon = True
    timer.start()


def inject_observation(text):
    """Reserved for the perception phase (screen understanding)."""


warm_up()
