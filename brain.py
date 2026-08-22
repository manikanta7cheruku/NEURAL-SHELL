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

    print(Fore.YELLOW + "[BRAIN] Session reset.")


load_name_from_memory()

_SKIP_GREETINGS = {"hi", "hello", "hey"}


def _save_conversation(prompt_text, result, speaker_id):
    """Save direct conversation turn to ChromaDB memory."""
    try:
        if not prompt_text or len(prompt_text.strip()) <= 3:
            return

        if prompt_text.lower().strip() in _SKIP_GREETINGS:
            return

        if isinstance(result, tuple) and len(result) == 2 and result[0] == "__STREAM__":
            return

        if not isinstance(result, str) or not result.strip():
            return

        if result.strip().startswith("###") or result.startswith("Processing error"):
            return

        _save_user_id = speaker_id if speaker_id not in ("default", "unknown") else (
            config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
        )
        _source = "voice" if speaker_id not in ("default", "unknown") else "chat"

        # Enforce memory quotas directly to avoid background API context failures
        try:
            if seven_memory and hasattr(seven_memory, 'conversations'):
                _current = seven_memory.conversations.count()
                _tier = config.KEY.get("license", {}).get("tier", "free")
                
                _limits = {
                    "free": 7,
                    "pro": 77,
                    "ultimate": -1
                }
                _max_allowed = _limits.get(_tier, 7)

                if _max_allowed != -1 and _current >= _max_allowed:
                    print(Fore.YELLOW + f"[BRAIN] Quota reached ({_current}/{_max_allowed}) for tier '{_tier}' - skipping conversation save.")
                    return
        except Exception as _q_err:
            print(Fore.YELLOW + f"[BRAIN] Quota verification bypassed: {_q_err}")

        _clean_response = re.sub(r'###\w+:\s*\S+', '', result).strip()
        if not _clean_response:
            return

        if seven_memory:
            try:
                seven_memory.extract_and_store_facts(prompt_text, user_id=_save_user_id)
            except Exception:
                pass

            seven_memory.store_conversation(
                user_input=prompt_text,
                seven_response=_clean_response,
                user_id=_save_user_id,
                source=_source,
            )
            print(Fore.GREEN + f"[BRAIN] Saved turn ({_source}): '{prompt_text[:35]}...'")

    except Exception as _mem_err:
        print(Fore.YELLOW + f"[BRAIN] Auto-save skipped: {_mem_err}")


def store_voice_turn(prompt_text, response_text, speaker_id, was_interrupted=False):
    """Save processed streaming voice turns into ChromaDB memory."""
    try:
        if not prompt_text or not response_text:
            return
        if len(prompt_text.strip()) <= 3 or prompt_text.lower().strip() in _SKIP_GREETINGS:
            return

        _save_user_id = speaker_id if speaker_id not in ("default", "unknown") else (
            config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
        )

        _clean = re.sub(r'###\w+:\s*\S+', '', response_text).strip()
        if not _clean:
            return

        if was_interrupted:
            _clean = f"[INTERRUPTED] {_clean}"

        # Resolve seven_memory instance safely
        mem = seven_memory
        if not mem:
            try:
                from memory import seven_memory as _lazy_mem
                mem = _lazy_mem
            except Exception:
                mem = None

        if mem:
            mem.store_conversation(
                user_input=prompt_text,
                seven_response=_clean,
                user_id=_save_user_id,
                source="voice",
            )
            print(Fore.GREEN + f"[BRAIN] Voice conversation saved to memory (interrupted={was_interrupted})")

    except Exception as _err:
        print(Fore.YELLOW + f"[BRAIN] Voice memory save skipped: {_err}")


def think(prompt_text, speaker_id="default"):
    """Execute pipeline layers and generate assistant response."""
    global USER_NAME

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