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

    # Save conversation to memory
    # Only save real responses — skip empty, stream tuples, and error strings
    try:
        if (
            result
            and isinstance(result, str)
            and len(result.strip()) > 0
            and not result.startswith("Processing error")
        ):
            # Extract facts from user input first
            seven_memory.extract_and_store_facts(prompt_text, user_id=speaker_id)
            # Save the full conversation turn
            seven_memory.store_conversation(
                user_input=prompt_text,
                seven_response=result,
                user_id=speaker_id,
            )
    except Exception as _mem_err:
        # Memory save failure must never break the response
        print(Fore.YELLOW + f"[BRAIN] Memory save failed: {_mem_err}")

    return result


def inject_observation(text):
    """
    Placeholder for future proactive observation injection.
    Currently unused. Reserved for Morning Brief feature.
    """
    pass