"""
PROJECT SEVEN - brain.py (The Orchestrator)
Version: 2.2 - Stable Monolith Interface
"""

import os
import sys
import re
from colorama import Fore
import colorama
colorama.init(autoreset=True)

import config

# Top-level safe memory imports
try:
    from memory import seven_memory
    from memory.mood import mood_engine
except Exception as _mem_imp_err:
    seven_memory = None
    mood_engine = None

from brain_modules.pipeline import run as run_pipeline
from brain_modules.context import BrainContext

try:
    from brain_modules.model_selector import select_model
    MODEL_NAME = select_model()
except Exception as _model_err:
    print(f"[BRAIN] Model selector failed: {_model_err}. Reading from config.")
    try:
        MODEL_NAME = config.KEY['brain']['model_name']
    except Exception:
        MODEL_NAME = "tinyllama"

print(f"[BRAIN] Active model: {MODEL_NAME}")

USER_NAME = "Admin"


def load_name_from_memory():
    """Load user name from configuration or stored memory facts."""
    global USER_NAME

    try:
        import json
        _cfg_path = os.path.join(os.environ.get('APPDATA', ''), 'SEVEN', 'config.json')
        if os.path.exists(_cfg_path):
            with open(_cfg_path, 'r', encoding='utf-8') as _f:
                _cfg_data = json.load(_f)
            cfg_name = _cfg_data.get('identity', {}).get('user_name', '').strip()
            if cfg_name and cfg_name.lower() not in ('admin', ''):
                USER_NAME = cfg_name
                print(Fore.GREEN + f"[BRAIN] Name from config: {USER_NAME}")
                return
    except Exception as _e:
        print(Fore.YELLOW + f"[BRAIN] Config name read failed: {_e}")

    try:
        if seven_memory and hasattr(seven_memory, 'user_facts'):
            all_facts = seven_memory.user_facts.get()
            if all_facts and all_facts.get('documents'):
                for doc in all_facts['documents']:
                    doc_lower = doc.lower()
                    if "user's name is" in doc_lower or "user wants to be called" in doc_lower:
                        name = (doc.split("is")[-1].strip().rstrip(".")
                                if "name is" in doc_lower
                                else doc.split("called")[-1].strip().rstrip("."))
                        if name:
                            USER_NAME = name
                            print(Fore.GREEN + f"[BRAIN] Name from memory: {USER_NAME}")
                            return
    except Exception as e:
        print(Fore.YELLOW + f"[BRAIN] Memory name load failed: {e}")

    USER_NAME = "there"


def reset_session():
    """Reset session history and identity cache."""
    global USER_NAME
    USER_NAME = "Admin"

    from brain_modules.context_manager import clear_history
    clear_history()

    from brain_modules.identity_layer import reset_session as identity_reset
    identity_reset()

    try:
        from brain_modules.conversation_thread import ConversationThread
        ConversationThread.clear("default")
        import config
        _save_user_id = config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
        ConversationThread.clear(_save_user_id)
    except Exception as _ct_err:
        print(Fore.YELLOW + f"[BRAIN] Session thread clear failed: {_ct_err}")

    print(Fore.YELLOW + "[BRAIN] Session reset.")


# Deferred load of name. Will be called during think() to prevent
# heavy memory/model loading during Python's import phase on boot.
_name_loaded = False


def ensure_name_loaded():
    global _name_loaded
    if not _name_loaded:
        load_name_from_memory()
        _name_loaded = True


_SKIP_GREETINGS = {"hi", "hello", "hey"}


def save_completed_turn(prompt_text, response_text, speaker_id, source="chat"):
    """
    Unified entry point to record a completed dialogue turn.
    Saves to ChromaDB, extracts facts, and writes to rolling session thread.
    Synchronizes streaming chat, voice, and non-streaming responses.
    """
    try:
        if not prompt_text or not response_text:
            return

        p_clean = prompt_text.strip()
        r_clean = re.sub(r'###\w+:\s*\S+', '', response_text).strip()

        if len(p_clean) <= 3 or not r_clean:
            return

        if p_clean.lower().strip() in _SKIP_GREETINGS:
            return

        # Unified thread ID resolution using dynamic memory state
        if speaker_id not in ("default", "unknown") and speaker_id:
            _save_user_id = speaker_id.strip().lower()
        elif USER_NAME and USER_NAME.strip().lower() not in ("admin", "default", "unknown", ""):
            _save_user_id = USER_NAME.strip().lower()
        else:
            _save_user_id = "default"

        # 1. Add to rolling thread buffer for repetition detection
        try:
            from brain_modules.conversation_thread import ConversationThread
            ConversationThread.add_turn(_save_user_id, p_clean, r_clean)
        except Exception as _ct_err:
            print(Fore.YELLOW + f"[BRAIN] Session thread save failed: {_ct_err}")

        # 2. Extract facts via idle worker
        try:
            from brain_modules.idle_worker import enqueue
            enqueue("extract_facts", {"text": p_clean, "speaker_id": _save_user_id})
        except Exception as _f_err:
            print(Fore.YELLOW + f"[BRAIN] Facts extraction enqueue failed: {_f_err}")

        # 3. Store conversation in ChromaDB
        if seven_memory:
            try:
                seven_memory.store_conversation(
                    user_input=p_clean,
                    seven_response=r_clean,
                    user_id=_save_user_id,
                    source=source,
                )
                print(Fore.GREEN + f"[BRAIN] Saved completed turn ({source}): '{p_clean[:35]}...'")
            except Exception as _mem_err:
                print(Fore.YELLOW + f"[BRAIN] ChromaDB store bypassed: {_mem_err}")

    except Exception as _err:
        print(Fore.YELLOW + f"[BRAIN] Unified save turn failed: {_err}")


def _save_conversation(prompt_text, result, speaker_id):
    """Save direct non-streaming conversation turn to ChromaDB memory."""
    if isinstance(result, tuple) and len(result) == 2 and result[0] == "__STREAM__":
        # Bypassed here; streaming handles its own saves on stream completion callback
        return
    save_completed_turn(prompt_text, result, speaker_id, source="chat")


def store_voice_turn(prompt_text, response_text, speaker_id, was_interrupted=False):
    """Save processed streaming voice turns into ChromaDB memory."""
    _clean = response_text
    if was_interrupted:
        _clean = f"[INTERRUPTED] {response_text}"
    save_completed_turn(prompt_text, _clean, speaker_id, source="voice")

def _execute_resolved_reference(resolved: dict) -> str:
    """
    Execute the action pointed to by a resolved reference.

    Handles resolver output shape (dialogue_manager v2.1):
        {"action": "open",       "target": {...}, "reason": "..."}
        {"action": "repeat",     "target": {...}, "reason": "..."}
        {"action": "ambiguous",  "options": [...],"reason": "..."}
        {"action": "none",       "reason": "..."}
    """
    import random

    if not resolved or not isinstance(resolved, dict):
        return None

    action = resolved.get("action")
    reason = resolved.get("reason", "")

    # -- No resolution possible: return graceful clarification --
    if action == "none":
        return random.choice([
            f"I lost track of what you meant. Could you say that again?",
            f"Not sure what to open. {reason.capitalize()}." if reason else "Not sure what you meant.",
            "Could you tell me which one you want?",
        ])

    # -- Ambiguous: ask which of the filtered options --
    if action == "ambiguous":
        options = resolved.get("options", [])
        count = len(options)
        return random.choice([
            f"I see {count} that match. Which one, top to bottom?",
            f"Got {count} matches. Tell me the number.",
            f"There are {count} of those. Which do you want?",
        ])

    # -- Open action: execute file or app open --
    if action in ("open", "repeat"):
        target = resolved.get("target") or {}
        path = target.get("path")
        name = target.get("name", "it")

        if not path:
            return None

        try:
            from hands.files import open_file
            ok = open_file(path)

            # Update working memory so subsequent "again" repeats THIS open
            try:
                from brain_modules.dialogue_manager import get_last_action, remember_action
                last = get_last_action()
                if last and target in last.get("results", []):
                    new_idx = last["results"].index(target)
                    remember_action(
                        last["type"],
                        last["query"],
                        last["results"],
                        opened_index=new_idx,
                    )
            except Exception as _mem_err:
                print(Fore.YELLOW + f"[BRAIN] Memory update after open skipped: {_mem_err}")

            if ok:
                if action == "repeat":
                    return random.choice([
                        "Opening it again.",
                        "Reopening now.",
                        "Got it, opening again.",
                    ])
                return random.choice([
                    "Opening it now.",
                    "Got it, opening.",
                    "Here you go.",
                    "Opened.",
                ])
            return f"I tried but could not open {name}."
        except Exception as e:
            return f"Ran into an issue opening it: {e}"

    return None

def think(prompt_text, speaker_id="default"):
    """Execute pipeline layers and generate assistant response."""
    global USER_NAME
    
    ensure_name_loaded()

    # Refresh user name from config on every call.
    # Config can change during runtime via Settings UI without backend restart.
    try:
        import json
        _cfg_path = os.path.join(os.environ.get('APPDATA', ''), 'SEVEN', 'config.json')
        if os.path.exists(_cfg_path):
            with open(_cfg_path, 'r', encoding='utf-8-sig') as _f:
                _cfg_data = json.load(_f)
            _fresh_name = _cfg_data.get('identity', {}).get('user_name', '').strip()
            if _fresh_name and _fresh_name.lower() not in ('admin', ''):
                USER_NAME = _fresh_name
    except Exception:
        pass

    # -- Dialogue state check --
    # If Seven is waiting for a clarification response (e.g. "close all chrome?"),
    # check if this input answers the pending question before running the pipeline.
    try:
        from brain_modules.dialogue_manager import has_pending, check_pending
        if has_pending():
            _dialogue_reply = check_pending(prompt_text)
            if _dialogue_reply:
                print(Fore.CYAN + f"[BRAIN] Dialogue handled: {prompt_text[:40]}")
                _save_conversation(prompt_text, _dialogue_reply, speaker_id)
                return _dialogue_reply
    except Exception as _dm_err:
        print(Fore.YELLOW + f"[BRAIN] Dialogue check skipped: {_dm_err}")

    # -- Working memory reference check --
    # If the user is referring to a recent action's results
    # ("open the second one", "the last file"), resolve directly and skip
    # the pipeline entirely. Sub-5ms response for referenced actions.
    try:
        from brain_modules.dialogue_manager import (
            looks_like_reference, resolve_reference
        )
        if looks_like_reference(prompt_text):
            print(Fore.CYAN + f"[BRAIN] Reference detected: '{prompt_text[:50]}'")
            _resolved = resolve_reference(prompt_text)
            print(Fore.CYAN + f"[BRAIN] Resolver returned: action={_resolved.get('action')}, reason={_resolved.get('reason','')}")
            if _resolved:
                _reply = _execute_resolved_reference(_resolved)
                if _reply:
                    print(Fore.GREEN + f"[BRAIN] Reference executed: {prompt_text[:40]}")
                    _save_conversation(prompt_text, _reply, speaker_id)
                    return _reply
                else:
                    print(Fore.YELLOW + f"[BRAIN] Executor returned None, falling through to pipeline")
    except Exception as _ref_err:
        import traceback
        print(Fore.RED + f"[BRAIN] Reference resolve error: {_ref_err}")
        traceback.print_exc()

    ctx = BrainContext(
        prompt_text=prompt_text,
        speaker_id=speaker_id,
        user_name=USER_NAME
    )

    deps = {
        "seven_memory": seven_memory,
        "mood_engine": mood_engine,
        "config": config,
        "model_name": MODEL_NAME,
    }

    result = run_pipeline(ctx, deps)

    if ctx.new_user_name:
        USER_NAME = ctx.new_user_name

    _save_conversation(prompt_text, result, speaker_id)

    return result


def inject_observation(text):
    pass