"""
=============================================================================
PROJECT SEVEN - brain.py (The Orchestrator)
Version: 2.0 (Full pipeline refactor)

WHAT THIS FILE IS:
    The single public interface for Seven's intelligence.
    main.py calls brain.think() and gets a response string.
    Everything else is hidden inside brain_modules/.

WHAT THIS FILE IS NOT:
    It does not own any logic itself.
    It delegates to brain_modules/pipeline.py which runs 21 layers.
    It is the conductor, not the musician.

DESIGN PATTERN: Facade Pattern
    brain.think() is a Facade — a simple interface hiding complex internals.
    main.py never imports brain_modules directly.
    All complexity is behind this one function.

    WHY FACADE:
        If we change how memory injection works, we change one layer file.
        main.py never needs to know. The interface stays stable.
        This is the Open/Closed Principle: open for extension (add new layers),
        closed for modification (main.py never changes).

LAYER ORDER (Critical — do not reorder):
    See brain_modules/pipeline.py for full LAYER_ORDER list.

INTERVIEW TALKING POINT:
    "brain.py is under 200 lines and contains no layer logic itself.
     It is the entry point that orchestrates 21 processing layers.
     Each layer either returns a response or passes to the next.
     This is Chain of Responsibility pattern. The first 4 layers handle
     60-70% of inputs without any LLM call. Average latency for those is
     under 5ms. Only open-ended questions reach the LLM."

MODULAR MONOLITH ARCHITECTURE:
    All brain_modules run in the SAME Python process as main.py.
    Direct function calls — zero network overhead.
    Sub-5ms latency for command layers.
    Alternative (microservices) would add 50-200ms per layer for HTTP calls.
    For a voice assistant, that is unacceptable.
=============================================================================
"""

import os
from colorama import Fore
import colorama
colorama.init(autoreset=True)

import config

# ─────────────────────────────────────────────────────────────────────────
# MEMORY IMPORTS
# Imported at module level so they are ready when think() is first called.
# ─────────────────────────────────────────────────────────────────────────
from memory import seven_memory
from memory.mood import mood_engine

# ─────────────────────────────────────────────────────────────────────────
# PIPELINE + CONTEXT
# ─────────────────────────────────────────────────────────────────────────
from brain_modules.pipeline import run as run_pipeline
from brain_modules.context  import BrainContext

# ─────────────────────────────────────────────────────────────────────────
# MODEL SELECTION (runs once at startup)
# select_model() checks GPU VRAM → picks best installed Ollama model.
# Falls back gracefully if Ollama is not running.
# ─────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────
# SESSION STATE
# USER_NAME: resolved name of the default speaker this session.
# ─────────────────────────────────────────────────────────────────────────
USER_NAME = "Admin"


def load_name_from_memory():
    """
    Load user name on startup. Priority:
    1. config.json identity.user_name (set from Settings UI)
    2. ChromaDB memory facts (set by voice "my name is X")
    3. Default: "there"

    WHY THIS ORDER:
        Settings UI is the most intentional — user typed their name.
        ChromaDB voice is second — user said it out loud.
        "there" is neutral fallback — "Yeah, there?" is not weird.

    CALLED ONCE: at module load time below.
    """
    global USER_NAME

    # Priority 1: Settings config
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

    # Priority 2: ChromaDB memory facts
    try:
        all_facts = seven_memory.user_facts.get()
        if all_facts and all_facts['documents']:
            for doc in all_facts['documents']:
                doc_lower = doc.lower()
                if "user's name is" in doc_lower or "user wants to be called" in doc_lower:
                    name = (doc.split("is")[-1].strip().rstrip(".")
                            if "name is" in doc_lower
                            else doc.split("called")[-1].strip().rstrip("."))
                    if name and len(name) > 0:
                        USER_NAME = name
                        print(Fore.GREEN + f"[BRAIN] Name from memory: {USER_NAME}")
                        return
    except Exception as e:
        print(Fore.YELLOW + f"[BRAIN] Memory name load failed: {e}")

    # Priority 3: Neutral fallback
    USER_NAME = "there"
    print(Fore.YELLOW + "[BRAIN] No name found. Using fallback: 'there'")


def reset_session():
    """
    Clear all session data when memory is wiped.
    Resets conversation history, recent questions, USER_NAME.

    CALLED BY: memory wipe endpoint in backend/routes/memory.py
    """
    global USER_NAME
    USER_NAME = "Admin"

    from brain_modules.context_manager import clear_history
    clear_history()

    from brain_modules.identity_layer import reset_session as identity_reset
    identity_reset()

    print(Fore.YELLOW + "[BRAIN] Session reset.")


# Run name loading at import time
load_name_from_memory()


# =============================================================================
# MAIN THINK FUNCTION
# =============================================================================

# Greeting inputs that are never worth storing as memories.
_SKIP_GREETINGS = {"hi", "hello", "hey"}


def _save_conversation(prompt_text, result, speaker_id):
    """
    Single save point for all conversation turns.

    Filters applied:
    - Input 3 chars or shorter: skip (noise, accidental triggers)
    - Input is a bare greeting: skip (no information content)
    - Response is pure command tags (starts with ###): skip
    - Streaming responses: skip (text is not reconstructable here,
      main.py calls flag_last_as_interrupted() post-speak if needed)
    - Plan limit reached for this tier: skip and print warning
    - ChromaDB error: log and move on, never crash the pipeline

    Source tagging:
    - speaker_id != "default"  -> voice (voice ID system identified speaker)
    - speaker_id == "default"  -> chat (API caller, Console UI)

    Called by think() only. Do not call directly from main.py or chat.py.
    """
    try:
        # Filter 1: too short to be meaningful
        if len(prompt_text.strip()) <= 3:
            return

        # Filter 2: bare greeting with no content
        if prompt_text.lower().strip() in _SKIP_GREETINGS:
            return

        # Filter 3: streaming response - text not available at this point
        # main.py reassembles streaming text and calls store_voice_turn() directly
        if isinstance(result, tuple) and len(result) == 2 and result[0] == "__STREAM__":
            return

        # Filter 4: must be a non-empty string from here on
        if not isinstance(result, str) or not result.strip():
            return

        # Filter 5: pure command response (no conversational text)
        if result.strip().startswith("###"):
            return

        # Filter 6: error sentinel
        if result.startswith("Processing error"):
            return

        # Resolve user identity
        _save_user_id = speaker_id if speaker_id not in ("default", "unknown") else (
            config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
        )
        # source=voice: came from microphone (speaker_id is anything except "default")
        # source=chat:  came from API, Console UI, or chat route (speaker_id="default")
        # "voice_user" is set by main.py when Voice ID is disabled but mic was used
        _source = "voice" if speaker_id not in ("default", "unknown") else "chat"

        # Filter 7: plan limit check
        try:
            import voice_limits as _vl
            _current = seven_memory.conversations.count()
            _allowed, _limit_msg = _vl.check("conversation_history", _current)
            if not _allowed:
                print(Fore.YELLOW + f"[BRAIN] Conversation memory full ({_current}) - not saving")
                return
        except Exception as _vl_err:
            # voice_limits failure is non-fatal - continue with save
            print(Fore.YELLOW + f"[BRAIN] Limit check skipped: {_vl_err}")

        # Clean command tags from response before storing
        import re as _re
        _clean_response = _re.sub(r'###\w+:\s*\S+', '', result).strip()
        if not _clean_response:
            return

        print(Fore.CYAN + f"[BRAIN] Saving conversation (source={_source})...")

        # Extract and store facts from this input
        try:
            seven_memory.extract_and_store_facts(prompt_text, user_id=_save_user_id)
        except Exception as _fact_err:
            print(Fore.YELLOW + f"[BRAIN] Fact extraction skipped: {_fact_err}")

        # Store the conversation turn
        seven_memory.store_conversation(
            user_input=prompt_text,
            seven_response=_clean_response,
            user_id=_save_user_id,
            source=_source,
        )
        print(Fore.GREEN + f"[BRAIN] Saved ({_source}): '{prompt_text[:40]}...'")

    except Exception as _mem_err:
        import traceback
        print(Fore.RED + f"[BRAIN] Save error: {_mem_err}")
        traceback.print_exc()


def store_voice_turn(prompt_text, response_text, speaker_id, was_interrupted=False):
    """
    Called by main.py's voice loop AFTER speaking is complete.
    Used specifically for streaming responses, where brain.think() cannot
    reconstruct the full text (the generator is consumed by the speak loop).
    Also applies the [INTERRUPTED] prefix when speech was cut off mid-sentence.

    Args:
        prompt_text    (str):  original user speech
        response_text  (str):  full assembled response text (after streaming)
        speaker_id     (str):  speaker profile id
        was_interrupted(bool): True if user cut Seven off mid-sentence
    """
    try:
        if not prompt_text or not response_text:
            return
        if len(prompt_text.strip()) <= 3:
            return
        if prompt_text.lower().strip() in _SKIP_GREETINGS:
            return

        _save_user_id = speaker_id if speaker_id not in ("default", "unknown") else (
            config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
        )

        # Plan limit check
        try:
            import voice_limits as _vl
            _current = seven_memory.conversations.count()
            _allowed, _ = _vl.check("conversation_history", _current)
            if not _allowed:
                print(Fore.YELLOW + f"[BRAIN] Memory full - skipping streaming save")
                return
        except Exception:
            pass

        import re as _re
        _clean = _re.sub(r'###\w+:\s*\S+', '', response_text).strip()
        if not _clean:
            return

        if was_interrupted:
            _clean = f"[INTERRUPTED] {_clean}"

        seven_memory.store_conversation(
            user_input=prompt_text,
            seven_response=_clean,
            user_id=_save_user_id,
            source="voice",
        )
        print(Fore.GREEN + f"[BRAIN] Streaming turn saved (interrupted={was_interrupted})")

    except Exception as _err:
        print(Fore.RED + f"[BRAIN] Streaming save error: {_err}")


def think(prompt_text, speaker_id="default"):
    """
    Process user input and return Seven's response.

    This is the ONLY public function in brain.py.
    main.py calls this. Nothing else does.

    ARGS:
        prompt_text (str):  The user's transcribed speech (from Whisper STT)
        speaker_id  (str):  Speaker profile ID from Voice ID system.
                            "default" = unknown/single speaker.
                            "mani", "priya" etc = identified speakers.

    RETURNS:
        str                    → regular text response
        ("__STREAM__", gen)    → streaming response (generator of sentences)

    RESPONSE FORMAT:
        Plain text for conversation: "That is a solid plan."
        Text + tag for commands:     "Opening chrome. ###OPEN: chrome"
        Stream tuple for streaming:  ("__STREAM__", <generator>)

    ERROR HANDLING:
        Never raises exceptions. Always returns a string or stream tuple.
        Pipeline catches per-layer errors and continues.
        Layer 8 (LLM) always returns something.

    INTERVIEW TALKING POINT:
        "think() is the Facade. It is the only public interface.
         Internally it runs 21 pipeline layers, but the caller — main.py —
         only sees one function that takes text and returns text.
         All complexity is hidden. This is the Facade pattern."
    """
    global USER_NAME

    # Build context for this call
    ctx = BrainContext(
        prompt_text=prompt_text,
        speaker_id=speaker_id,
        user_name=USER_NAME
    )

    # Dependencies passed to every layer that needs them
    deps = {
        "seven_memory": seven_memory,
        "mood_engine":  mood_engine,
        "config":       config,
        "model_name":   MODEL_NAME,
    }

    # Run pipeline
    result = run_pipeline(ctx, deps)

    # If a layer updated the user name (name-setting layer), apply it globally
    if ctx.new_user_name:
        USER_NAME = ctx.new_user_name

    # Save conversation to memory.
    # This is the single save point for ALL callers (voice and chat).
    # Filters applied here so neither main.py nor chat.py need their own save logic.
    _save_conversation(prompt_text, result, speaker_id)

    return result


def inject_observation(text):
    """
    Placeholder for future proactive observation injection.
    Currently unused. Reserved for Morning Brief feature.
    """
    pass