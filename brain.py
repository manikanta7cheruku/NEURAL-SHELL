"""
=============================================================================
PROJECT SEVEN - brain.py (The Orchestrator)
Version: 1.3 (Modular Monolith Refactor)

WHAT THIS FILE IS:
    The single public interface for Seven's intelligence.
    main.py calls brain.think() and gets a response string.
    Everything else is hidden inside brain_modules/.

WHAT THIS FILE IS NOT:
    It does not own any logic itself.
    It delegates to brain_modules/ for everything.
    It is the conductor, not the musician.

DESIGN PATTERN: Facade Pattern
    brain.think() is a Facade -- a simple interface hiding complex internals.
    main.py never imports brain_modules directly.
    All complexity is behind this one function.

    WHY FACADE:
        If we change how memory injection works, we change one brain_modules
        file. main.py never needs to know. The interface stays stable.
        This is the Open/Closed Principle: open for extension (add new layers),
        closed for modification (main.py never changes).

LAYER ORDER (Critical -- do not reorder):
    Layer 1: Name setting         -- "my name is X" -> saves, returns immediately
    Layer 2: Repetition detection -- repeated question -> short ack, returns
    Layer 3: Identity overrides   -- "who are you", greetings -> returns immediately
    Layer 4: TARS controls        -- "set humor to 80" -> saves, returns immediately
    Layer 4.5: Command routing    -- open/close/volume/window/schedule -> tag + speech
    Layer 5: Memory search        -- ChromaDB similarity search
    Layer 5.3: Knowledge search   -- local knowledge base
    Layer 5.5: Web search         -- DuckDuckGo live data
    Layer 6: Personal Q filter    -- "what sport do I play?" with no memory -> returns
    Layer 7: Fact extraction      -- learn from user statements
    Layer 8: LLM inference        -- Ollama generates final response

INTERVIEW TALKING POINT:
    "brain.py is ~120 lines and contains no logic itself.
     It is the entry point that orchestrates 8 processing layers.
     Each layer either returns a response or passes the input to the next.
     This is the Chain of Responsibility pattern. The first 4 layers handle
     60-70% of inputs without any LLM call. Average latency for those is
     under 5ms. Only open-ended questions reach the LLM."

MODULAR MONOLITH ARCHITECTURE:
    All brain_modules run in the SAME Python process as main.py.
    Direct function calls -- zero network overhead.
    This is why latency is sub-5ms for command layers.
    Alternative (microservices) would add 50-200ms per layer for HTTP calls.
    For a voice assistant, that is unacceptable.
=============================================================================
"""

import os
import re
import random
import requests
import time as _time

import config
import colorama
from colorama import Fore
colorama.init(autoreset=True)

# ---------------------------------------------------------------------------
# MEMORY IMPORTS
# Imported at module level so they are ready when think() is first called.
# ---------------------------------------------------------------------------
from memory import seven_memory
from memory.mood import mood_engine

# ---------------------------------------------------------------------------
# MODEL SELECTION (runs once at startup)
# select_model() checks GPU VRAM -> picks best installed Ollama model.
# Falls back gracefully if Ollama is not running.
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# OLLAMA ENDPOINT
# Defined here for the non-streaming path.
# ollama_client.py owns the streaming path.
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# ---------------------------------------------------------------------------
# SESSION STATE
# USER_NAME: resolved name of the default speaker this session.
# LAST_SYSTEM_DOMAIN: tracks last volume/brightness for pronoun resolution.
# ---------------------------------------------------------------------------
USER_NAME = "Admin"


def load_name_from_memory():
    """
    Load user name on startup. Priority:
    1. config.json identity.user_name (set from Settings UI)
    2. ChromaDB memory facts (set by voice "my name is X")
    3. Default: "there"

    WHY THIS ORDER:
        Settings UI is the most intentional -- user typed their name.
        ChromaDB voice is second -- user said it out loud.
        "there" is neutral fallback -- "Yeah, there?" is not weird.

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

    # Clear conversation history
    from brain_modules.context_manager import clear_history
    clear_history()

    # Clear repetition tracker
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
        str                    -- regular text response
        ("__STREAM__", gen)    -- streaming response (generator of sentences)

    RESPONSE FORMAT:
        Plain text for conversation: "That is a solid plan."
        Text + tag for commands:     "Opening chrome. ###OPEN: chrome"
        Stream tuple for streaming:  ("__STREAM__", <generator>)

    ERROR HANDLING:
        Never raises exceptions. Always returns a string.
        If Ollama crashes: "My brain hiccupped. Try again."
        If memory fails: silently continues without memory context.
        This guarantees Seven always has something to say.

    INTERVIEW TALKING POINT:
        "think() is the Facade. It is the only public interface.
         Internally it runs 8 layers, but the caller -- main.py --
         only sees one function that takes text and returns text.
         All complexity is hidden. This is the Facade pattern."
    """
    global USER_NAME

    # ------------------------------------------------------------------
    # RESOLVE SPEAKER NAME
    # If Voice ID identified a speaker, look up their real name from memory.
    # Otherwise use the session USER_NAME (loaded from config/memory at startup).
    # ------------------------------------------------------------------
    if speaker_id not in ("default", "unknown"):
        speaker_name = speaker_id.title()  # Default: capitalize profile ID
        try:
            all_facts = seven_memory.user_facts.get(where={"user_id": speaker_id})
            if all_facts and all_facts['documents']:
                for doc in all_facts['documents']:
                    doc_lower = doc.lower()
                    if "name is" in doc_lower:
                        found_name = doc.split("is")[-1].strip().rstrip(".")
                        if found_name:
                            speaker_name = found_name
                            break
                    elif "called" in doc_lower:
                        found_name = doc.split("called")[-1].strip().rstrip(".")
                        if found_name:
                            speaker_name = found_name
                            break
        except Exception:
            pass
    else:
        speaker_name = USER_NAME if USER_NAME else 'there'

    # ------------------------------------------------------------------
    # CLEAN INPUT
    # Lowercase, strip punctuation, strip leading filler words.
    # "And open chrome please" -> "open chrome"
    # ------------------------------------------------------------------
    clean_in = prompt_text.lower().strip()
    clean_in = clean_in.replace("?", "").replace(".", "").replace("!", "")
    clean_in = clean_in.replace("'", "").replace(",", "")

    # Strip leading filler so "and open chrome" becomes "open chrome"
    _filler_starts = ["and ", "also ", "now ", "then ", "please ",
                      "can you ", "could you ", "hey "]
    for _filler in _filler_starts:
        if clean_in.startswith(_filler):
            clean_in = clean_in[len(_filler):].strip()
            break

    words      = clean_in.split()
    first_word = words[0] if words else ""

    # Words that are NEVER app names — always file/folder references
    # Defined here once — used by is_command check AND Layer 4.3
    _FILE_WORDS = {
        "resume", "cv", "folder", "pdf", "document", "photo",
        "image", "screenshot", "video", "report", "invoice",
        "contract", "presentation", "spreadsheet", "edit",
        "itinerary", "trip", "travel", "gokarna", "file",
    }
    _has_file_word = any(w in _FILE_WORDS for w in words)

    # Pre-classify to skip unnecessary layers for commands/greetings
    # REMOVED from is_command: volume, mute, unmute, brightness, play, pause,
    # skip, next, previous, stop — these are SYSTEM commands handled by
    # _build_system_tag(). Having them here set is_command=True which
    # blocked the SYS layer entirely. That was why "volume 10" did nothing.
    # File type words — "open resume" should go to file search, not app launcher
    _always_file_words = {
        "resume", "cv", "folder", "pdf", "document", "photo",
        "image", "screenshot", "video", "report", "invoice",
        "contract", "presentation", "spreadsheet", "edit",
    }
    # If any word in the command is a file word, it is a file request not an app command
    _cmd_words      = clean_in.split()
    _has_file_word  = any(w in _always_file_words for w in _cmd_words)

    # If command contains a file word, it is a file request not an app launch
    # "open resume" → file search. "open chrome" → app launch.
    is_command = (
        first_word in ["open", "close", "start", "kill", "launch",
                       "minimize", "maximize", "maximise", "restore", "snap"]
        and not _has_file_word
    )
    is_greeting = first_word in ["hi", "hey", "hello", "bye", "goodbye", "good"]

    # ------------------------------------------------------------------
    # LAYER 1: NAME SETTING
    # ------------------------------------------------------------------
    from brain_modules.identity_layer import handle_name_setting
    name_result = handle_name_setting(
        prompt_text, clean_in, speaker_id, speaker_name, seven_memory, USER_NAME
    )
    if name_result is not None:
        if isinstance(name_result, tuple):
            new_name, response = name_result
            USER_NAME    = new_name
            speaker_name = new_name
        else:
            response = name_result
        return response

    # ------------------------------------------------------------------
    # LAYER 2: REPETITION DETECTION
    # ------------------------------------------------------------------
    from brain_modules.identity_layer import handle_repetition
    repeat_result = handle_repetition(
        clean_in, speaker_id, speaker_name,
        is_command, is_greeting, seven_memory, config
    )
    if repeat_result == "__SIMILAR_DETECTED__":
        # Inject note into prompt for LLM to handle differently
        prompt_text = (
            f"[The user asked a similar question before. "
            f"Acknowledge briefly then answer differently.] {prompt_text}"
        )
    elif repeat_result is not None:
        return repeat_result

    # ------------------------------------------------------------------
    # LAYER 3: IDENTITY OVERRIDES
    # ------------------------------------------------------------------
    from brain_modules.identity_layer import handle_identity
    identity_result = handle_identity(clean_in, words, speaker_id, speaker_name, config)
    if identity_result is not None:
        return identity_result
    

    # ------------------------------------------------------------------
    # LAYER 3.8: FILE SEARCH ROOT REGISTRATION
    # "add M:\adobe2 to search folders", "remember to look in M:\edit"
    # ------------------------------------------------------------------
    _add_root_triggers = [
        "add to search", "add to your search", "remember to search",
        "search in", "also search", "look in", "search folder",
        "add search folder", "include folder", "include in search",
    ]
    _has_add_root = any(t in clean_in for t in _add_root_triggers)

    # Also catch drive paths directly: "add M:\adobe2"
    import re as _re_path
    _path_match = _re_path.search(r'[a-zA-Z]:\\[^\s]+', prompt_text)

    if _has_add_root and _path_match:
        _new_root = _path_match.group(0).rstrip('.,!?')
        if os.path.exists(_new_root):
            try:
                _current_roots = config.KEY.get("file_search_roots", [])
                if _new_root not in _current_roots:
                    _current_roots.append(_new_root)
                    config.update_config({"file_search_roots": _current_roots})
                    # Rebuild search roots immediately
                    from hands.files import _build_search_roots
                    _build_search_roots()
                    return (f"Got it. I will search {_new_root} from now on. "
                            f"That folder is now in my search list.")
                else:
                    return f"Already searching {_new_root}."
            except Exception as _root_err:
                print(Fore.YELLOW + f"[BRAIN] Root registration failed: {_root_err}")
                return "Could not save that folder. Try again."
        else:
            return f"That path does not exist: {_new_root}. Check the spelling."

    # ------------------------------------------------------------------
    # LAYER 4: TARS PERSONALITY CONTROLS
    # ------------------------------------------------------------------
    from brain_modules.identity_layer import handle_tars_controls
    tars_result = handle_tars_controls(clean_in, words, config)
    if tars_result is not None:
        return tars_result


    # ------------------------------------------------------------------
    # FILE TYPE WORDS — defined here so both Layer 4.3 and Layer 6 can use it
    # Layer 4.3 uses it to detect file intent
    # Layer 6 uses it to avoid blocking file questions as personal questions
    # ------------------------------------------------------------------
    # Use _FILE_WORDS defined at top of think() — same set, defined once
    _file_type_words = _FILE_WORDS

    # ------------------------------------------------------------------
    # LAYER 4.3: FILE SEARCH INTENT
    # Catches "open my resume", "show resume to friends", "find my cv"
    # before the LLM sees it. Uses hands/files.py filesystem crawler.
    # ------------------------------------------------------------------
    _file_intent_triggers = [
        "my resume", "my cv", "my document", "my file", "my photo",
        "my image", "my video", "my pdf", "my report", "my project",
        "show resume", "find resume", "open resume", "open cv",
        "show my", "find my", "where is my",
    ]
    _open_intents = [
        "open", "show", "find", "display", "launch", "pull up",
        "bring up", "view", "look at", "see my", "access"
    ]
    _has_file_intent = any(t in clean_in for t in _file_intent_triggers)
    _has_open_intent = any(t in clean_in for t in _open_intents)

    _has_file_query = (
        any(fw in clean_in for fw in _file_type_words)
        and any(q in clean_in for q in [
            "how many", "do i have", "any", "list", "show all",
            "find all", "what files", "search for"
        ])
    )

    _cmd_paths_check   = config.KEY.get("commands", {}).get("app_paths", {})
    _cmd_aliases_check = config.KEY.get("commands", {}).get("app_aliases", {})
    _is_configured     = any(k in clean_in for k in _cmd_paths_check) or \
                         any(k in clean_in for k in _cmd_aliases_check)

    _has_file_type = any(fw in clean_in for fw in _file_type_words)

    # File intent overrides is_command when the phrase clearly refers to a file
    # "open my resume" — "my resume" is a file phrase, not an app name
    # "open cv folder" — "folder" signals filesystem, not app launcher
    # Words that are NEVER app names — always file/folder references
    _always_file_words = {
        "resume", "cv", "folder", "pdf", "document", "photo",
        "image", "screenshot", "video", "report", "invoice",
        "contract", "presentation", "spreadsheet",
    }
    _clear_file_phrase = _has_file_intent or _has_file_query or (
        _has_file_type and (
            any(w in clean_in for w in ["my ", "folder", "file"]) or
            any(w in clean_in for w in _always_file_words)
        )
    )
    if _has_file_type and _clear_file_phrase and not _is_configured:
        try:
            from hands.files import search_files, open_file, format_results_for_speech, format_results_for_chat

            _search_terms = [fw for fw in _file_type_words if fw in clean_in]
            _orig_words = prompt_text.split()
            _proper = [w.lower() for w in _orig_words
                       if w[0].isupper() and w.lower() not in
                       {"open", "show", "find", "my", "the", "a", "can", "you"}]
            _search_query = " ".join(_search_terms + _proper) or clean_in

            _uname = config.KEY.get("identity", {}).get("user_name", "")
            results = search_files(_search_query, user_name=_uname)

            try:
                from backend.api_server import set_state as _api_set_file
                chat_data = format_results_for_chat(results, _search_query)
                _api_set_file("file_search_results", chat_data)
            except Exception:
                pass

            if not results:
                return (
                    f"I searched Desktop, Documents, Downloads, and OneDrive "
                    f"but found nothing matching '{_search_query}'. "
                    f"Add the exact path in Commands if you know where it is."
                )

            # Build voice response listing actual file names found
            _names = [r["name"] for r in results]
            _count = len(results)

            if _count == 1:
                _list_str = f"one file: {_names[0]}"
            elif _count == 2:
                _list_str = f"two files: {_names[0]} and {_names[1]}"
            else:
                _list_str = f"{_count} files: {', '.join(_names[:3])}"
                if _count > 3:
                    _list_str += f" and {_count - 3} more"

            # Open if user asked to open
            if _has_open_intent or _has_file_intent:
                open_file(results[0]["path"])
                if _count == 1:
                    return f"Found and opened {_names[0]}. Path is in the chat."
                else:
                    return (
                        f"Found {_list_str}. "
                        f"Opened the top match: {_names[0]}. "
                        f"All paths are in the chat."
                    )

            # Count/list query — just report
            return (
                f"Found {_list_str}. "
                f"Full paths and details are in the chat below."
            )

        except Exception as _file_err:
            import traceback
            print(Fore.YELLOW + f"[BRAIN] File search failed: {_file_err}")
            traceback.print_exc()
            # Fall through to LLM only on actual error

    # ------------------------------------------------------------------
    # LAYER 4.5: COMMAND ROUTING (Python-first, bypasses LLM)
    # ------------------------------------------------------------------
    from brain_modules.command_router import (
        _build_window_tag, _build_sched_tag, _build_system_tag,
        get_last_system_domain, set_last_system_domain
    )

    # Mood analysis (affects LLM response tone, not commands)
    mood_engine.analyze_input(prompt_text)

    # --- SCHEDULER COMMANDS ---
    import re as _re_sched
    _has_after_dur = bool(_re_sched.search(
        r'\bafter\s+\d+\s*(second|seconds|minute|minutes|hour|hours)\b', clean_in
    ))
    _has_in_dur = bool(_re_sched.search(
        r'\bin\s+\d+\s*(second|seconds|minute|minutes|hour|hours)\b', clean_in
    ))

    SCHED_TRIGGER_PHRASES = [
        "remind me", "remember me to", "reminder to", "reminder for",
        "dont let me forget", "don't let me forget", "remind me to",
        "remind me about", "tell me to", "let me know when", "let me know to",
        "alert me", "notify me", "ping me", "wake me up", "wake me at",
        "set a timer", "set an alarm", "set timer", "set alarm", "start a timer",
        "schedule a meeting", "add meeting", "add event", "cancel my",
        "cancel the", "cancel all", "delete the alarm", "delete the timer",
        "delete the reminder", "remove the alarm", "remove the timer",
        "remove the reminder", "clear all timers", "clear all reminders",
        "clear all alarms", "what reminders", "what alarms", "what timers",
        "show my schedule", "show schedule", "any alarms", "any reminders",
        "any timers", "whats scheduled", "how much time left", "time remaining",
        "timer status", "list reminders", "list alarms", "list timers",
        "my schedule", "my reminders", "my alarms", "cancel everything",
        "clear all schedules", "how long left", "time left on timer",
    ]

    _has_sched = (
        any(t in clean_in for t in SCHED_TRIGGER_PHRASES)
        or any(t in words for t in ["remind", "reminder", "alarm", "timer", "countdown"])
        or _has_after_dur
        or _has_in_dur
    )
    _sched_guard = is_command or "what time is it" in clean_in

    if _has_sched and not _sched_guard:
        sched_tag = _build_sched_tag(clean_in, words)
        if sched_tag:
            is_command = True

            if sched_tag == "action=timer_ask":
                return "How long should I set the timer for?"
            if sched_tag == "action=alarm_ask":
                return "What time should I set the alarm for?"
            if sched_tag == "action=reminder_ask":
                return "What should I remind you about, and when?"

            _sched_acks = {
                "reminder":      ["On it.", "Locked in.", "I have it.",
                                  "Leave it with me.", "Got it. I will remind you."],
                "timer":         ["Clock is running.", "Counting down.",
                                  "Timer set.", "On the clock."],
                "alarm":         ["Alarm set.", "I will wake you.", "Set."],
                "event":         ["On the calendar.", "Locked in.", "Noted."],
                "cancel":        ["Cancelled.", "Done. Removed.", "Cleared."],
                "list":          [],
                "timer_remaining": [],
            }
            _action  = (sched_tag.split("action=")[1].split(" ")[0]
                        if "action=" in sched_tag else "")
            _ack_list = _sched_acks.get(_action, ["On it."])
            _ack      = random.choice(_ack_list) if _ack_list else ""

            return f"{_ack} ###SCHED: {sched_tag}" if _ack else f"###SCHED: {sched_tag}"

    # --- BATTERY FAST PATH ---
    _battery_q = (
        any(p in clean_in for p in ["battery", "how much charge", "battery level",
                                     "battery percentage", "is it charging", "plugged in"])
        and not is_command
    )
    if _battery_q:
        return random.choice(["Checking.", "On it.", "One moment."]) + " ###SYS: action=battery"

    # --- SYSTEM COMMANDS ---
    SYSTEM_TRIGGER_WORDS = [
        "volume", "mute", "unmute", "louder", "quieter", "softer",
        "brightness", "brighter", "dimmer", "dim", "battery", "charging",
        "plugged", "wifi", "bluetooth", "play", "pause", "skip",
        "next track", "next song", "previous track", "previous song",
        "stop music", "stop playing", "resume music", "dark mode",
        "light mode", "dark theme", "light theme", "night light",
        "blue light", "night mode", "do not disturb", "dnd",
        "focus assist", "airplane mode", "flight mode",
    ]
    _has_sys = any(t in clean_in for t in SYSTEM_TRIGGER_WORDS)

    import re as _re_mod
    _has_context_ref = (
        get_last_system_domain() is not None
        and (
            (any(w in clean_in for w in ["it", "that", "this"])
             and bool(_re_mod.search(r'\d+', clean_in)))
            or clean_in in ["more", "less", "higher", "lower",
                             "increase", "decrease"]
        )
    )

    # Use _is_app_cmd_only instead of is_command so system words like
    # "volume", "mute" are not blocked by the app-command classifier.
    _is_app_cmd_only = first_word in ["open", "close", "start", "kill", "launch"]
    if (_has_sys and not _is_app_cmd_only) or _has_context_ref:
        sys_tag = _build_system_tag(clean_in)
        if sys_tag:
            is_command = True

            # Track domain for pronoun resolution
            if "volume" in sys_tag:
                set_last_system_domain("volume")
            elif "brightness" in sys_tag:
                set_last_system_domain("brightness")

            # Parse tag for context-aware speech
            _parts  = {}
            for _p in sys_tag.split():
                if "=" in _p:
                    _k, _v = _p.split("=", 1)
                    _parts[_k] = _v
            _action = _parts.get("action", "")
            _value  = _parts.get("value", "")

            # Map actions to TARS-style speech responses
            _sys_speech_map = {
                "volume_up":       lambda: random.choice(["Turning it up.", "Louder.", "Volume up."]),
                "volume_down":     lambda: random.choice(["Turning it down.", "Quieter.", "Volume down."]),
                "volume_set":      lambda: f"{_value}%.",
                "volume_mute":     lambda: random.choice(["Muted.", "Going silent.", "Sound off."]),
                "volume_unmute":   lambda: random.choice(["Unmuted.", "Sound on.", "You are live."]),
                "volume_get":      lambda: "",
                "brightness_up":   lambda: random.choice(["Brightening up.", "More brightness.", "Screen brighter."]),
                "brightness_down": lambda: random.choice(["Dimming.", "Less brightness.", "Screen dimmer."]),
                "brightness_set":  lambda: f"Brightness to {_value}%.",
                "brightness_get":  lambda: "",
                "battery":         lambda: "",
                "wifi_on":         lambda: "Enabling WiFi.",
                "wifi_off":        lambda: "Disabling WiFi.",
                "wifi_status":     lambda: "",
                "bluetooth_on":    lambda: "Enabling Bluetooth.",
                "bluetooth_off":   lambda: "Disabling Bluetooth.",
                "bluetooth_status": lambda: "",
                "media_play_pause": lambda: random.choice(["Toggled.", "Done.", ""]),
                "media_next":      lambda: random.choice(["Next track.", "Skipping.", "Next."]),
                "media_prev":      lambda: random.choice(["Previous track.", "Going back.", "Previous."]),
                "media_stop":      lambda: "Stopping playback.",
                "dark_mode_on":    lambda: random.choice(["Going dark.", "Dark mode.", "Switching to dark."]),
                "dark_mode_off":   lambda: random.choice(["Going light.", "Light mode.", "Switching to light."]),
                "night_light_on":  lambda: random.choice(["Night light on.", "Easy on the eyes.", "Warming the screen."]),
                "night_light_off": lambda: "Night light off.",
                "dnd_on":          lambda: random.choice(["Do not disturb.", "Going quiet.", "Notifications silenced."]),
                "dnd_off":         lambda: "Notifications back on.",
                "airplane_on":     lambda: random.choice(["Airplane mode on.", "Going offline.", "All radios off."]),
                "airplane_off":    lambda: random.choice(["Airplane mode off.", "Back online.", "Radios on."]),
            }

            speech_fn = _sys_speech_map.get(_action)
            speech    = speech_fn() if speech_fn else "On it."

            return f"{speech} ###SYS: {sys_tag}" if speech else f"###SYS: {sys_tag}"

    # --- WINDOW COMMANDS ---
    window_verbs   = ["minimize", "maximise", "maximize", "restore", "snap",
                      "switch to", "focus", "bring up", "center", "centre",
                      "pin", "unpin", "fullscreen", "full screen", "swap"]
    put_pattern    = "put " in clean_in and any(
        p in clean_in for p in ["on the left", "on the right", "on left", "on right",
                                 "top left", "top right", "bottom left", "bottom right"]
    )
    layout_triggers = ["side by side", "split screen", "split view",
                        "stack", "quad", "tile", "arrange"]
    is_layout      = any(t in clean_in for t in layout_triggers)

    desktop_phrases = [
        "show desktop", "hide all windows", "minimize everything",
        "minimize all", "minimize all windows", "clear desktop",
        "hide everything", "show all windows", "restore all",
        "restore all windows", "view desktop", "show my desktop",
        "clear screen", "clear all windows", "go to desktop",
        "desktop", "hide windows"
    ]
    notarget_phrases = [
        "undo that", "undo last", "undo window", "put it back",
        "revert that", "undo", "whats open", "what is open",
        "what windows are open", "list windows", "show windows",
        "what's running", "whats running"
    ]
    is_desktop_cmd  = clean_in in desktop_phrases
    is_notarget_cmd = (clean_in in notarget_phrases
                       or any(p in clean_in for p in notarget_phrases))

    switch_verbs   = ["switch to", "bring up", "go to", "focus on", "focus",
                      "show me", "pull up", "jump to", "open up"]
    is_switch      = any(sv in clean_in for sv in switch_verbs)
    is_move_monitor = "move" in clean_in and "monitor" in clean_in
    is_swap        = "swap" in clean_in and ("and" in clean_in or "," in clean_in)
    is_window_close = ("close this" in clean_in or "close the window" in clean_in
                       or "close active" in clean_in)
    is_transparent = ("transparent" in clean_in or "see through" in clean_in
                      or "translucent" in clean_in)
    is_solid       = ("solid" in clean_in or "opaque" in clean_in
                      or "not transparent" in clean_in)
    is_pin         = ("pin " in clean_in
                      or ("keep" in clean_in and "on top" in clean_in)
                      or "always on top" in clean_in)
    is_unpin       = ("unpin" in clean_in or "remove from top" in clean_in
                      or "not on top" in clean_in)
    is_window_verb = any(wv in clean_in for wv in window_verbs)

    is_any_window  = (is_desktop_cmd or is_notarget_cmd or is_layout or put_pattern
                      or is_window_verb or is_switch or is_move_monitor or is_swap
                      or is_window_close or is_transparent or is_solid
                      or is_pin or is_unpin)

    if is_any_window:
        is_command = True
        tag_params = _build_window_tag(
            clean_in, is_desktop_cmd, is_notarget_cmd, is_layout, put_pattern,
            is_switch, is_move_monitor, is_swap, is_window_close,
            is_transparent, is_solid, is_pin, is_unpin
        )
        if tag_params:
            _parts   = {}
            for _p in tag_params.split():
                if "=" in _p:
                    _k, _v = _p.split("=", 1)
                    _parts[_k] = _v

            _action   = _parts.get("action", "")
            _target   = _parts.get("target", "").replace(",", " and ")
            _position = _parts.get("position", "")
            _mode     = _parts.get("mode", "")

            # Map window actions to TARS-style speech
            _win_speech_map = {
                "focus":       lambda: random.choice([f"Switching to {_target}.", f"Bringing up {_target}.", f"{_target}, coming up."]),
                "minimize":    lambda: random.choice([f"Minimizing {_target}.", f"Putting {_target} away.", f"{_target}, out of sight."]),
                "maximize":    lambda: random.choice([f"Maximizing {_target}.", f"Full size on {_target}.", f"{_target}, going big."]),
                "restore":     lambda: random.choice([f"Restoring {_target}.", f"Bringing {_target} back."]),
                "snap":        lambda: random.choice([f"Snapping {_target} to the {_position}.", f"{_target}, {_position} side."]),
                "center":      lambda: f"Centering {_target}.",
                "layout":      lambda: (f"Putting {_target} side by side." if _mode == "split"
                                        else f"Stacking {_target}." if _mode == "stack"
                                        else f"Four corners, {_target}." if _mode == "quad"
                                        else f"Arranging {_target}."),
                "minimize_all": lambda: random.choice(["Clearing the deck.", "Everything down.", "Desktop, clear."]),
                "show_desktop": lambda: random.choice(["Showing desktop.", "All clear.", "Desktop."]),
                "swap":        lambda: random.choice([f"Swapping {_target}.", f"{_target}, switching places."]),
                "pin":         lambda: random.choice([f"Pinning {_target} on top.", f"{_target} stays on top now."]),
                "unpin":       lambda: random.choice([f"Unpinning {_target}.", f"{_target}, back to normal."]),
                "fullscreen":  lambda: random.choice([f"Fullscreen on {_target}.", f"{_target}, going fullscreen."]),
                "solid":       lambda: random.choice([f"Making {_target} solid again.", f"{_target}, back to full opacity."]),
                "close_window": lambda: "Closing this window.",
                "undo":        lambda: random.choice(["Undoing that.", "Putting it back.", "Reverting."]),
                "list":        lambda: "",
            }

            if _action == "transparent":
                _opacity = _parts.get("opacity", "0.8")
                if _opacity == "more":
                    speech = random.choice([f"Making {_target} more transparent.", f"{_target}, a bit more see-through."])
                elif _opacity == "less":
                    speech = random.choice([f"Making {_target} less transparent.", f"Brightening {_target} up."])
                else:
                    try:
                        pct = int(float(_opacity) * 100)
                        speech = (f"Making {_target} slightly transparent." if pct >= 90
                                  else f"Making {_target} very transparent." if pct <= 40
                                  else f"Setting {_target} to {pct}% opacity.")
                    except Exception:
                        speech = f"Making {_target} transparent."
            else:
                speech_fn = _win_speech_map.get(_action)
                speech    = speech_fn() if speech_fn else "On it."

            return f"{speech} ###WINDOW: {tag_params}" if speech else f"###WINDOW: {tag_params}"

    # --- APP OPEN/CLOSE/SEARCH ---
    if first_word in ["open", "close", "start", "kill", "launch"]:
        command_verb = first_word
        remaining    = clean_in

        for verb in ["open", "close", "start", "kill", "launch"]:
            if remaining.startswith(verb):
                remaining = remaining[len(verb):].strip()
                break

        tag       = "OPEN" if command_verb in ["open", "start", "launch"] else "CLOSE"
        close_all = False

        if tag == "CLOSE" and remaining.startswith("all "):
            close_all = True
            remaining = remaining[4:].strip()

        for _art in ["the ", "a ", "an "]:
            if remaining.startswith(_art):
                remaining = remaining[len(_art):].strip()
                break

        # Self-referential open commands
        _self_words = {"seven", "yourself", "self", "you", "assistant", "ai"}
        if remaining.lower().strip() in _self_words and tag == "OPEN":
            return "I am already running. You are talking to me right now."

        if remaining:
            _normalized = remaining.replace(" and ", ",").replace(" & ", ",")
            apps        = [a.strip() for a in _normalized.split(",") if a.strip()]
            if not apps:
                apps = [remaining.strip()]

            # Known system apps always closeable without a configured path
            _ALWAYS_CLOSEABLE = {
                "chrome", "firefox", "edge", "notepad", "explorer", "calculator",
                "camera", "photos", "settings", "paint", "word", "excel",
                "powerpoint", "outlook", "teams", "discord", "spotify",
                "whatsapp", "telegram", "zoom", "obs", "vlc", "code",
                "vscode", "terminal", "cmd", "powershell", "copilot",
                "clock", "calendar", "mail", "maps", "store", "xbox",
                "brave", "opera", "skype", "slack", "notepad++", "winamp",
                "snipping tool", "task manager", "paint 3d", "media player",
            }

            _cmd_paths   = config.KEY.get("commands", {}).get("app_paths", {})
            _cmd_aliases = config.KEY.get("commands", {}).get("app_aliases", {})

            # Pronouns and garbage words that are never app names
            _INVALID_TARGETS = {
                "me", "it", "this", "that", "the", "a", "an",
                "and", "or", "all", "everything", "them", "those",
                "these", "here", "there", "now", "app", "window",
            }

            if tag == "OPEN":
                for _app in apps:
                    _app_clean = _app.lower().strip()
                    # Known configured app — allow through
                    if _app_clean in _cmd_paths or _app_clean in _cmd_aliases:
                        continue
                    # Common system app — allow through
                    if _app_clean in _ALWAYS_CLOSEABLE:
                        continue
                    # Everything else — block with human message
                    # (AppOpener async silently fails, user gets no feedback)
                    return (
                        f"I don't have '{_app}' in my commands. "
                        f"Go to Commands and add the path, "
                        f"then I can open it."
                    )

            if tag == "CLOSE":
                for _app in apps:
                    _app_clean = _app.lower().strip()

                    # Reject pronouns — "close me", "close it", "close that"
                    if _app_clean in _INVALID_TARGETS:
                        return (f"Close what exactly? I did not catch a specific app name.")

                    # Reject gibberish — no vowels and longer than 3 chars
                    _has_vowel = any(v in _app_clean for v in "aeiou")
                    if not _has_vowel and len(_app_clean) > 3:
                        return (f"That does not look like an app name. What did you want to close?")

                    # Reject very short unknown words
                    if len(_app_clean) < 3 and _app_clean not in _cmd_paths:
                        return (f"Close what? Be more specific.")

            tags     = " ".join([f"###{tag}: ALL_{a}" if close_all else f"###{tag}: {a}"
                                 for a in apps])
            app_list = ", ".join(apps)

            if tag == "OPEN":
                speech = random.choice([
                    f"Opening {app_list}.",
                    f"On it. {app_list} coming up.",
                    f"{app_list}, coming right up.",
                    f"Launching {app_list}.",
                ])
            else:
                speech = (
                    random.choice([f"Closing all {app_list}.",
                                   f"Shutting down every {app_list}.",
                                   f"Killing all {app_list} instances."])
                    if close_all else
                    random.choice([f"Closing {app_list}.",
                                   f"Shutting down {app_list}.",
                                   f"Done with {app_list}."])
                )
            return f"{speech} {tags}"

    # ------------------------------------------------------------------
    # LAYER 5: MEMORY SEARCH
    # ------------------------------------------------------------------
    memory_context = ""
    _is_action_cmd = first_word in [
        "open", "close", "start", "kill", "launch", "minimize", "maximize",
        "maximise", "restore", "snap", "mute", "unmute", "set", "volume",
        "brightness", "play", "pause", "skip", "next", "previous", "stop"
    ]

    if ("VISUAL_REPORT:" not in prompt_text
            and not is_command and not is_greeting and not _is_action_cmd):
        search_uid = (speaker_id if speaker_id not in ("default", "unknown")
                      else config.KEY.get("identity", {}).get(
                          "user_name", "default").lower() or "default")
        try:
            memory_context = seven_memory.search(prompt_text, user_id=search_uid)
        except Exception as _mem_err:
            print(Fore.YELLOW + f"[BRAIN] Memory search skipped: {_mem_err}")

        if memory_context:
            print(Fore.MAGENTA + "[MEMORY] Found relevant memories!")

    # ------------------------------------------------------------------
    # LAYER 5.3: KNOWLEDGE BASE SEARCH
    # ------------------------------------------------------------------
    knowledge_context = ""
    knowledge_triggers = ["what is", "what are", "who is", "who was", "who were",
                          "explain", "define", "how does", "how do", "how is",
                          "tell me about", "what does", "meaning of", "describe",
                          "history of", "why is", "why do", "why does", "when was",
                          "when did", "where is", "where was", "difference between"]
    personal_words     = ["my", "i ", "me ", "about me", "do i", "am i"]

    if (not is_command and not is_greeting and not _is_action_cmd
            and "VISUAL_REPORT:" not in prompt_text):
        is_knowledge_q = any(t in clean_in for t in knowledge_triggers)
        is_personal    = any(w in clean_in for w in personal_words)

        if is_knowledge_q and not is_personal and not memory_context:
            try:
                from knowledge import search_knowledge
                knowledge_context = search_knowledge(prompt_text)
                if knowledge_context:
                    print(Fore.CYAN + "[BRAIN] Knowledge base results found!")
            except ImportError:
                pass
            except Exception as e:
                print(Fore.YELLOW + f"[BRAIN] Knowledge search error: {e}")

    # ------------------------------------------------------------------
    # LAYER 5.5: WEB SEARCH
    # ------------------------------------------------------------------
    web_context  = ""
    web_searched = False

    if (not is_command and not is_greeting and not _is_action_cmd
            and "VISUAL_REPORT:" not in prompt_text):
        from web.classifier import needs_web_search
        from web.core       import web_search, web_news

        should_search, search_query = needs_web_search(prompt_text)

        if should_search and search_query:
            # Add location to weather queries
            _weather_words = ["weather", "temperature", "forecast", "rain",
                              "sunny", "cloudy", "humidity", "wind"]
            _is_weather = any(w in search_query.lower() for w in _weather_words)
            if _is_weather and "in " not in search_query.lower():
                try:
                    _city = config.KEY.get("identity", {}).get("city", "")
                    if not _city:
                        # Try to get from previous IP-based detection
                        _city = config.KEY.get("identity", {}).get("location", "")
                    if _city:
                        search_query = f"weather in {_city} today"
                    else:
                        search_query = "current weather today"
                except Exception:
                    pass

            print(Fore.CYAN + f"[BRAIN] Web search: '{search_query}'")
            news_words = ["news", "latest", "happened", "breaking", "update"]
            is_news    = any(w in clean_in for w in news_words)
            web_context = web_news(search_query) if is_news else web_search(search_query)

            if web_context:
                web_searched = True
                print(Fore.GREEN + "[BRAIN] Web results injected.")

    # ------------------------------------------------------------------
    # LAYER 5.7: CAPABILITY INJECTION
    # ------------------------------------------------------------------
    capability_triggers = ["what can you do", "what you can do", "your capabilities",
                           "what are you capable", "what do you do", "capable of",
                           "tell me what you can", "what are your abilities",
                           "list your capabilities", "what are your features"]
    is_capability_q = any(t in clean_in for t in capability_triggers)

    if is_capability_q:
        # Build capability facts block -- LLM answers naturally from these
        is_window_q = any(w in clean_in for w in ["window", "windows", "screen", "display"])
        is_app_q    = any(w in clean_in for w in ["app", "apps", "application", "program"])
        is_system_q = any(w in clean_in for w in ["system", "control", "volume", "brightness",
                                                    "battery", "wifi", "bluetooth", "media"])
        is_sched_q  = any(w in clean_in for w in ["schedule", "scheduler", "alarm", "reminder",
                                                    "timer", "calendar", "remind"])

        if is_window_q:
            cap_facts = [
                "I can minimize, maximize, restore, and center any window.",
                "I snap windows to any side or corner of the screen.",
                "I do split-screen layouts: side by side, stacked, or four corners.",
                "I can pin any window on top so it stays above everything.",
                "I adjust window transparency to any percentage.",
                "I swap two windows positions instantly.",
                "I toggle fullscreen on any window.",
                "I undo my last window action.",
                "I understand 'this' as whatever window is currently focused.",
                "I show desktop and minimize all windows.",
                "I move windows between monitors.",
            ]
        elif is_system_q:
            cap_facts = [
                "I control system volume: up, down, mute, unmute, set to specific percentage.",
                "I adjust screen brightness: up, down, set to specific percentage.",
                "I check battery status: percentage, plugged in, time remaining.",
                "I check and toggle WiFi on or off.",
                "I toggle Bluetooth on or off.",
                "I control media playback: play, pause, next track, previous track, stop.",
                "I switch between dark mode and light mode.",
                "I toggle night light and blue light filter.",
                "I toggle do not disturb and focus assist.",
                "I toggle airplane mode.",
            ]
        elif is_sched_q:
            cap_facts = [
                "I set alarms for specific times with optional recurring patterns.",
                "I set reminders with custom messages at specific times or after a delay.",
                "I set timers that count down and alert when done.",
                "I schedule calendar events and meetings.",
                "I support recurring schedules: daily, weekly, specific weekdays.",
                "I can list all active schedules and cancel them by voice.",
            ]
        elif is_app_q:
            cap_facts = [
                "I open any app by name.",
                "I close one instance or all instances of an app.",
                "I know aliases: browser means chrome, files means explorer.",
            ]
        else:
            cap_facts = [
                "I open and close apps by name with alias support.",
                "I control windows: snap, resize, minimize, maximize, pin, transparency, swap, fullscreen, undo.",
                "I do split-screen layouts with multiple windows.",
                "I remember conversations and facts about people long-term.",
                "I search the web for live data: prices, weather, news via DuckDuckGo.",
                "I control system settings: volume, brightness, battery, WiFi, Bluetooth, media playback, dark mode, night light, and do not disturb.",
                "I recognize different speakers by their voice.",
                "Users can interrupt me mid-sentence.",
                "Everything runs 100% locally. Nothing leaves this machine.",
                "I set alarms, reminders, timers, and calendar events. I handle recurring schedules.",
            ]

        facts_block = "=== YOUR CAPABILITIES (answer from these) ===\n"
        for fact in cap_facts:
            facts_block += f"- {fact}\n"
        facts_block += "=== END CAPABILITIES ===\nSummarize these naturally. Be concise."
        prompt_text = f"{facts_block}\n\nUser asked: {prompt_text}"

    # ------------------------------------------------------------------
    # LAYER 5.9: APP HISTORY QUERY
    # ------------------------------------------------------------------
    if (("what" in clean_in or "which" in clean_in)
            and ("app" in clean_in or "open" in clean_in)
            and ("today" in clean_in or "did i" in clean_in or "did you" in clean_in)):
        from memory.command_log import command_log
        stats  = command_log.get_stats()
        recent = stats.get('recent', [])
        if recent:
            app_list = ", ".join([f"{r['action']} {r['target']}" for r in recent[:5]])
            return f"Recent commands: {app_list}."
        return "No apps opened in this session yet."

    # ------------------------------------------------------------------
    # LAYER 6: PERSONAL QUESTION FILTER (no memory = no answer)
    # ------------------------------------------------------------------
    personal_question_words = ["my", "about me", "do i", "did i", "am i",
                               "i like", "i love", "i play", "i work", "i study"]
    is_personal_question    = any(w in clean_in for w in personal_question_words)
    question_starts         = ["what", "which", "who", "when", "where", "how",
                               "do you know"]
    is_question             = any(clean_in.startswith(w) for w in question_starts)

    # Guard: do not block file queries — "how many resumes do i have" is a
    # file system question, not a personal memory question
    _is_file_question = any(fw in clean_in for fw in _file_type_words)

    _is_file_question = any(fw in clean_in for fw in _file_type_words)
    if is_question and is_personal_question and not memory_context and not is_command and not _is_file_question:
        return "You haven't told me that yet."

    # ------------------------------------------------------------------
    # LAYER 7: FACT EXTRACTION
    # ------------------------------------------------------------------
    if ("VISUAL_REPORT:" not in prompt_text
            and not is_command and not is_greeting and not _is_action_cmd):
        search_uid = (speaker_id if speaker_id not in ("default", "unknown")
                      else config.KEY.get("identity", {}).get(
                          "user_name", "default").lower() or "default")
        try:
            seven_memory.extract_and_store_facts(prompt_text, user_id=search_uid)
        except Exception as _fact_err:
            print(Fore.YELLOW + f"[BRAIN] Fact extraction skipped: {_fact_err}")

    # ------------------------------------------------------------------
    # LAYER 8: LLM INFERENCE
    # ------------------------------------------------------------------
    # Store original user input in history (not modified prompt)
    _original_input = prompt_text
    if "===" in _original_input and "User asked:" in _original_input:
        _original_input = _original_input.split("User asked:")[-1].strip()

    if "VISUAL_REPORT:" not in _original_input and not _is_action_cmd:
        from brain_modules.context_manager import add_user_turn
        add_user_turn(speaker_id, _original_input)

    # Build system prompt with TARS personality
    _brain_cfg = config.KEY.get('brain', {})
    _humor     = int(_brain_cfg.get('tars_humor',   75))
    _honesty   = int(_brain_cfg.get('tars_honesty', 85))

    from brain_modules.prompt_builder  import build_system_prompt
    from brain_modules.context_manager import assemble_prompt

    _tier = config.KEY.get("license", {}).get("tier", "free")
    system_prompt = build_system_prompt(
        speaker_name = speaker_name,
        humor        = _humor,
        honesty      = _honesty,
        tier         = _tier,
    )

    full_prompt = assemble_prompt(
        system_prompt     = system_prompt,
        speaker_id        = speaker_id,
        web_context       = web_context,
        knowledge_context = knowledge_context,
        memory_context    = memory_context,
    )

    # Response length based on question type
    long_triggers = ["tell me", "explain", "describe", "what can you",
                     "list", "how does", "how do", "why", "story",
                     "detail", "everything", "all about", "continue",
                     "go on", "more about", "your capabilities",
                     "what are you capable", "what do you do",
                     "what you can do", "capable of"]
    count_triggers = ["count", "1 to", "one to", "from 1", "from one",
                      "list them", "name them", "enumerate"]

    needs_long  = any(t in clean_in for t in long_triggers)
    needs_count = any(t in clean_in for t in count_triggers)

    if needs_count:
        response_length = 200
    elif needs_long:
        response_length = 120
    elif web_searched:
        response_length = 80
    else:
        response_length = 50

    payload = {
        "model":   MODEL_NAME,
        "prompt":  full_prompt,
        "stream":  False,
        "options": {
            # 0.15 was too low — caused robotic fragmented output
            # "Hyderabad's Telanganas' pride" was repeat_penalty 1.6 destroying tokens
            "temperature":    0.3,
            "num_predict":    min(response_length, 150),
            "repeat_penalty": 1.2,
            "stop":           ["User:", "System:", "Seven:", "(Note", "(note",
                               "Note to self", "\n\n"],
            "num_ctx":        4096
        }
    }

    # --- STREAMING PATH ---
    use_streaming = config.KEY.get('brain', {}).get('streaming', False)

    if use_streaming:
        from brain_modules.ollama_client import stream_sentences
        start_time = _time.time()

        def _sentence_gen():
            full_reply = []
            for sentence in stream_sentences(full_prompt, payload):
                full_reply.append(sentence)
                yield sentence

            # After streaming: store complete response in history
            complete_reply = " ".join(full_reply)
            elapsed        = int((_time.time() - start_time) * 1000)

            try:
                from brain_manager import record_latency
                record_latency(elapsed)
            except Exception:
                pass

            if "VISUAL_REPORT:" not in prompt_text:
                from brain_modules.context_manager import add_seven_turn
                add_seven_turn(speaker_id, complete_reply)

        return ("__STREAM__", _sentence_gen())

    # --- NON-STREAMING PATH ---
    start_time = _time.time()

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)

        elapsed = int((_time.time() - start_time) * 1000)
        try:
            from brain_manager import record_latency
            record_latency(elapsed)
        except Exception:
            pass

        if r.status_code == 200:
            reply = r.json().get("response", "").strip() or "Listening."

            if "VISUAL_REPORT:" not in prompt_text:
                from brain_modules.context_manager import add_seven_turn
                add_seven_turn(speaker_id, reply)

            return reply

        print(Fore.RED + f"[BRAIN] Ollama status {r.status_code}")
        return "My brain hiccupped. Try again."

    except requests.exceptions.ConnectionError:
        print(Fore.RED + "[BRAIN] Cannot connect to Ollama.")
        return "I can't reach my brain. Run 'ollama serve' in a terminal first."
    except requests.exceptions.Timeout:
        print(Fore.RED + "[BRAIN] Ollama timeout.")
        return "My brain took too long. Try again."
    except Exception as e:
        print(Fore.RED + f"[BRAIN] Unexpected error: {e}")
        return "Something went wrong with my thinking."


def inject_observation(text):
    """
    Placeholder for future proactive observation injection.
    Currently unused. Reserved for Morning Brief feature.
    """
    pass