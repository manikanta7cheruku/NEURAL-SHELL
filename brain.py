"""
PROJECT SEVEN - brain.py (The Orchestrator)
Version: 3.0

think() runs one user message through the layer pipeline and returns either a
string, "" (intentional silence) or ("__STREAM__", generator).

WHAT CHANGED IN 3.0:
    - think(..., stream_mode="sentence"|"token"|"text"): the console asks for
      real tokens, voice asks for speakable sentences, tools ask for text.
    - One storage key per person (session.resolve_key) used everywhere.
    - Only completed LLM replies are persisted. Instant answers (commands,
      greetings, identity) are never written to conversation memory, and the
      duplicate fact-extraction enqueue (wrong payload key) is gone.
    - The model, the hardware probe and (later) the embedder are warmed in the
      background so the first real message is not the one that pays for them.
    - The user name is read through a cached lookup, not by parsing
      config.json on every message.
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

from brain_modules import session, speech_acts
from brain_modules.context import BrainContext
from brain_modules.pipeline import run as run_pipeline

_log = logging.getLogger("seven.brain")

try:
    from brain_modules.model_selector import select_model
    MODEL_NAME = select_model()
except Exception as _model_err:
    _log.warning("Model selector failed (%s). Reading from config.", _model_err)
    try:
        MODEL_NAME = config.KEY["brain"]["model_name"]
    except Exception:
        MODEL_NAME = "tinyllama"

print(f"[BRAIN] Active model: {MODEL_NAME}")

USER_NAME = "Admin"
_name_loaded = False


def load_name_from_memory():
    """Load the owner's name from config, falling back to 'there'."""
    global USER_NAME
    name = session.get_user_name()
    USER_NAME = name if name else "there"


def ensure_name_loaded():
    global _name_loaded
    if not _name_loaded:
        load_name_from_memory()
        _name_loaded = True


def _refresh_user_name():
    """Pick up a name change made in Settings without a restart (cached by file mtime)."""
    global USER_NAME
    name = session.get_user_name()
    if name:
        USER_NAME = name


def reset_session():
    """Forget session state: history, greeting streaks, caches. Facts are kept."""
    global USER_NAME
    key = session.resolve_key("default", USER_NAME)
    USER_NAME = "Admin"
    try:
        from brain_modules import chat_history, learning, social_engine
        from brain_modules.conversation_thread import ConversationThread
        chat_history.clear()
        social_engine.reset()
        learning.clear_cache()
        for k in {key, "default"}:
            ConversationThread.clear(k)
    except Exception as exc:
        _log.warning("session reset incomplete: %s", exc)
    print(Fore.YELLOW + "[BRAIN] Session reset.")


def save_completed_turn(prompt_text, response_text, speaker_id, source="chat", persist=True):
    """
    Record a completed exchange.

    Always updates the session thread (repetition and follow-up detection).
    Writes to long-term conversation storage only when persist=True, and does
    that on the background worker so the reply is never delayed by embedding.
    """
    try:
        if not prompt_text or not response_text:
            return
        p = prompt_text.strip()
        r = re.sub(r"###\w+:\s*\S+", "", response_text).strip()
        if len(p) <= 3 or not r:
            return
        if speech_acts.is_greeting(speech_acts.normalize(p)):
            return

        key = session.resolve_key(speaker_id, USER_NAME)

        from brain_modules.conversation_thread import ConversationThread
        ConversationThread.add_turn(key, p, r)

        try:
            from brain_modules.followup_detector import detect_followup
            followup = detect_followup(r)
            if followup:
                ConversationThread.set_metadata(key, "followup_hint", followup)
        except Exception as exc:
            _log.debug("follow-up detection skipped: %s", exc)

        if persist:
            from brain_modules import idle_worker
            idle_worker.enqueue("store_conversation", {
                "user_input": p, "response": r, "speaker_key": key, "source": source})
    except Exception as exc:
        _log.warning("save_completed_turn failed: %s", exc)


def _save_conversation(prompt_text, result, speaker_id):
    """Save a non-LLM string answer to the session thread only."""
    if isinstance(result, tuple):
        return
    save_completed_turn(prompt_text, result, speaker_id, source="chat", persist=False)


def store_voice_turn(prompt_text, response_text, speaker_id, was_interrupted=False):
    """Save a spoken turn. Interrupted replies are not persisted as knowledge."""
    save_completed_turn(prompt_text, response_text, speaker_id, source="voice",
                        persist=not was_interrupted)


def _execute_resolved_reference(resolved: dict):
    """Execute the action a resolved reference points to ("open the second one")."""
    if not resolved or not isinstance(resolved, dict):
        return None
    action, reason = resolved.get("action"), resolved.get("reason", "")

    if action == "none":
        return random.choice([
            "I lost track of what you meant. Could you say that again?",
            f"Not sure what to open. {reason.capitalize()}." if reason else "Not sure what you meant.",
            "Could you tell me which one you want?",
        ])
    if action == "ambiguous":
        count = len(resolved.get("options", []))
        return random.choice([
            f"I see {count} that match. Which one, top to bottom?",
            f"Got {count} matches. Tell me the number.",
            f"There are {count} of those. Which do you want?",
        ])
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
                if action == "repeat":
                    return random.choice(["Opening it again.", "Reopening now.", "Got it, opening again."])
                return random.choice(["Opening it now.", "Got it, opening.", "Here you go.", "Opened."])
            return f"I tried but could not open {name}."
        except Exception as exc:
            return f"Ran into an issue opening it: {exc}"
    return None


def think(prompt_text, speaker_id="default", stream_mode="sentence"):
    """
    Run the pipeline for one message.

    stream_mode:
        "sentence"  voice: generator of speakable sentences
        "token"     console: generator of raw tokens
        "text"      a finished string
    """
    global USER_NAME
    ensure_name_loaded()
    _refresh_user_name()
    key = session.resolve_key(speaker_id, USER_NAME)

    try:
        from brain_modules.correction_detector import detect_correction
        from brain_modules.tone_tracker import observe as observe_tone
        observe_tone(key, prompt_text, bool(detect_correction(prompt_text)))
    except Exception as exc:
        _log.debug("tone tracking skipped: %s", exc)

    # A pending clarification ("close all chrome windows?") takes the next input.
    try:
        from brain_modules.dialogue_manager import check_pending, has_pending
        if has_pending():
            reply = check_pending(prompt_text)
            if reply:
                _save_conversation(prompt_text, reply, speaker_id)
                return reply
    except Exception as exc:
        _log.debug("dialogue check skipped: %s", exc)

    # References to a recent action's results ("open the second one").
    try:
        from brain_modules.dialogue_manager import looks_like_reference, resolve_reference
        if looks_like_reference(prompt_text):
            resolved = resolve_reference(prompt_text)
            reply = _execute_resolved_reference(resolved) if resolved else None
            if reply:
                _save_conversation(prompt_text, reply, speaker_id)
                return reply
    except Exception as exc:
        _log.warning("reference resolve error: %s", exc)

    ctx = BrainContext(prompt_text=prompt_text, speaker_id=speaker_id, user_name=USER_NAME)
    ctx.stream_mode = stream_mode
    ctx.speaker_key = key
    deps = {"seven_memory": seven_memory, "mood_engine": mood_engine,
            "config": config, "model_name": MODEL_NAME}

    result = run_pipeline(ctx, deps)

    if ctx.new_user_name:
        USER_NAME = ctx.new_user_name
    if isinstance(result, tuple):
        return result
    if ctx.answered_by != "layer_08_llm":   # the LLM layer records its own turn
        _save_conversation(prompt_text, result, speaker_id)
    return result


_warmed = False


def warm_up():
    """Load the model, probe hardware and (later) the embedder in the background."""
    global _warmed
    if _warmed:
        return
    _warmed = True
    try:
        from brain_modules import ollama_client, self_model
        self_model.set_active_model(MODEL_NAME)
        self_model.prime_async()
        ollama_client.warmup(MODEL_NAME)
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
