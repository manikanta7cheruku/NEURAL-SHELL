"""
=============================================================================
brain_modules/identity_layer.py
PROJECT SEVEN -- Identity, Repetition, and TARS Personality Controls

WHAT THIS FILE DOES:
    Handles brain.py Layers 1 through 3 plus TARS slider controls.
    These layers return immediately -- no LLM needed.

    Layer 1: Name setting     ("my name is Mani" -> saves to memory + config)
    Layer 2: Repetition check (catches repeated questions, returns early)
    Layer 3: Identity queries ("who are you", greetings, farewells)
    Layer 4: TARS controls    ("set humor to 80", "what is your honesty?")

WHY THESE ARE GROUPED TOGETHER:
    All four layers share one characteristic: they return a response
    WITHOUT touching the LLM, memory search, or web search.
    They are the fast path -- sub-millisecond responses.
    Grouping them here keeps brain.py clean.

DESIGN PATTERN: Chain of Responsibility
    Each function tries to handle the input.
    Returns a string if it handles it.
    Returns None if it cannot handle it.
    brain.py tries each layer in order, stops at first non-None return.

    This is textbook Chain of Responsibility:
    Handler1 -> Handler2 -> Handler3 -> ... -> LLM (final fallback)

INTERVIEW TALKING POINT:
    "I use Chain of Responsibility for input processing. Each layer is
     a handler that either returns a response or passes the input down.
     The first 4 layers handle 60-70% of all inputs without LLM involvement.
     This is how production voice assistants achieve sub-100ms responses
     for common queries -- classify first, infer only when needed."

ALTERNATIVE PATTERN (interviewer might ask):
    "Could you use a decision tree or ML classifier instead?"
    Answer: "Yes, and that would scale better for 1000+ intent types.
     For Seven's current 50-60 intent types, rule-based classification
     is faster, more predictable, and debuggable without ML expertise.
     The tradeoff is manual maintenance of trigger lists vs. training data."
=============================================================================
"""

import os
import re
import random

import config
from colorama import Fore


# ---------------------------------------------------------------------------
# RECENT QUESTIONS TRACKER
# dict[speaker_id] = list of recent clean_in strings
# Used by Layer 2 to detect repeated questions.
# ---------------------------------------------------------------------------
RECENT_QUESTIONS = {}
MAX_RECENT = 10  # Keep last 10 questions per speaker


def reset_session():
    """
    Clear all session state.
    Called by brain.py when memory is wiped.
    Resets recent questions so repetition detection starts fresh.
    """
    global RECENT_QUESTIONS
    RECENT_QUESTIONS = {}


# =============================================================================
# LAYER 1: NAME SETTING
# =============================================================================

def handle_name_setting(prompt_text, clean_in, speaker_id, speaker_name,
                         seven_memory, USER_NAME):
    """
    Detect and handle name-setting commands.

    TRIGGERS:
        "my name is Mani"
        "call me Mani"
        "my name's Mani"
        "change my name to Mani"
        "rename me to Mani"

    WHAT IT DOES ON DETECTION:
        1. Extract the name from the utterance
        2. Save to ChromaDB memory (long-term)
        3. Save to config.json (persists across restarts)
        4. Update USER_NAME in brain.py globals immediately
        5. Return confirmation

    PERSISTENCE STRATEGY:
        Both ChromaDB AND config.json are updated.
        ChromaDB: "User's name is Mani" as a memory fact
        config.json: identity.user_name = "Mani"
        This dual-write ensures the name survives both memory wipe
        (config.json survives) and config reset (ChromaDB survives).

    ARGS:
        prompt_text:   original case (for name extraction)
        clean_in:      lowercased, punctuation-stripped
        speaker_id:    current speaker profile ID
        speaker_name:  current resolved speaker name
        seven_memory:  ChromaDB memory object
        USER_NAME:     current global USER_NAME from brain.py

    RETURNS:
        str  -- confirmation response ("Got it. Mani it is.")
        None -- if this is not a name-setting command
    """
    _name_triggers = (
        "my name is" in clean_in
        or "call me" in clean_in
        or "my name's" in clean_in
        or "change my name" in clean_in
        or "rename me" in clean_in
        or ("my name" in clean_in
            and any(w in clean_in for w in ["into", "to", "should be", "is now"]))
    )

    if not _name_triggers:
        return None

    # Extract name from different phrase patterns
    _pt_lower = prompt_text.lower()
    raw = ""

    if "my name is" in _pt_lower:
        raw = _pt_lower.split("my name is")[-1].strip()
    elif "my name's" in _pt_lower:
        raw = _pt_lower.split("my name's")[-1].strip()
    elif "call me" in _pt_lower:
        raw = _pt_lower.split("call me")[-1].strip()
    elif "change my name" in _pt_lower:
        for sep in ["into", "to", "as"]:
            after = _pt_lower.split("change my name")[-1]
            if sep in after:
                raw = after.split(sep)[-1].strip()
                break
        else:
            raw = _pt_lower.split("change my name")[-1].strip()
    elif "rename me" in _pt_lower:
        raw = _pt_lower.split("rename me")[-1].strip()
        for sep in ["to", "as", "into"]:
            if raw.startswith(sep + " "):
                raw = raw[len(sep):].strip()
                break
    else:
        raw = _pt_lower.split("my name")[-1].strip()
        for sep in ["into", "to", "is", "should be", "is now"]:
            if raw.startswith(sep + " "):
                raw = raw[len(sep):].strip()
                break

    # Remove correction phrases like "not ray" or "okay"
    raw = re.split(r'\bnot\b|\bokay\b|\bplease\b|\bright\b|\bok\b', raw)[0]
    raw = raw.strip().rstrip(".,!?").strip()

    # Filter filler words from name
    filler     = {"please", "okay", "ok", "right", "now", "actually", "just"}
    name_words = [w for w in raw.split() if w.lower() not in filler]
    new_name   = " ".join(name_words[:2]).strip()  # Max 2 words for a name
    new_name   = new_name.title()  # Capitalize properly

    if not new_name:
        return "I did not catch the name. Say it again?"

    # Save to memory and config based on speaker context
    if speaker_id != "default" and speaker_id != "unknown":
        # Multi-user: save under this speaker's profile
        seven_memory.store_fact(
            f"Speaker {speaker_id}'s name is {new_name}",
            category="identity",
            user_id=speaker_id
        )
    else:
        # Default speaker: update global USER_NAME
        seven_memory.store_fact(
            f"User's name is {new_name}",
            category="identity"
        )
        # Sync to config.json so Settings UI shows it and restarts pick it up
        try:
            current_identity = config.KEY.get('identity', {})
            current_identity['user_name'] = new_name
            config.update_config({'identity': current_identity})
            print(Fore.GREEN + f"[IDENTITY] Name '{new_name}' synced to config")
        except Exception as _cfg_err:
            print(Fore.YELLOW + f"[IDENTITY] Could not sync name to config: {_cfg_err}")

    # Return (new_name, confirmation) -- brain.py updates its USER_NAME global
    return new_name, f"Got it. {new_name} it is."


# =============================================================================
# LAYER 2: REPETITION DETECTOR
# =============================================================================

# Groups of semantically similar questions
# If user asks anything from the same group twice, we detect it
SIMILAR_GROUPS = [
    ["introduce yourself", "tell me what you can do", "what can you do",
     "what you can do", "what are your capabilities", "tell me about yourself",
     "what do you do", "list your capabilities"],
    ["whats your name", "who are you", "what should i call you", "tell me your name",
     "your name", "yuor name"],
    ["whats my name", "who am i", "do you know my name", "do you know me"],
    ["who created you", "who made you", "who built you", "who is your creator"],
]


def handle_repetition(clean_in, speaker_id, speaker_name,
                       is_command, is_greeting, seven_memory, config):
    """
    Detect repeated questions and return early with acknowledgment.

    ALGORITHM:
        1. Check if clean_in matches any recent question exactly
        2. Check if clean_in belongs to a "similar group" where user
           already asked something from that group
        3. If repeated: return short acknowledgment + same answer
        4. If not repeated: add to RECENT_QUESTIONS and return None

    WHY TRACK REPETITIONS:
        Without this, if user asks "who are you?" 10 times in a row,
        Seven goes to the LLM each time -- 10 seconds of wasted compute.
        With this, second time: "Still Seven." -- instant.

    SIDE EFFECT:
        Updates RECENT_QUESTIONS[speaker_id] with the new question.
        This is intentional -- we want to track for future calls.

    RETURNS:
        str  -- quick repeat response
        None -- if not a repeated question
    """
    speaker_questions = RECENT_QUESTIONS.get(speaker_id, [])

    # Check similar group membership
    similar_detected = False
    for group in SIMILAR_GROUPS:
        if any(g in clean_in for g in group):
            asked_similar = any(
                any(g in prev for g in group)
                for prev in speaker_questions
            )
            if asked_similar and not is_command and not is_greeting:
                similar_detected = True
                break

    # Exact repeat check
    if clean_in in speaker_questions and not is_command and not is_greeting:
        # Identity question repeats -- answer immediately without LLM
        if "your name" in clean_in or "who are you" in clean_in:
            return random.choice([
                "Seven. Same as before.",
                "Still Seven.",
                "I am Seven. That has not changed.",
            ])

        if "my name" in clean_in or "who am i" in clean_in:
            if (speaker_id not in ("default", "unknown")
                    and speaker_name == speaker_id.title()):
                return "You have not told me your name yet."
            return random.choice([
                f"You are {speaker_name}.",
                f"Still {speaker_name}.",
                f"{speaker_name}, same as before.",
            ])

        if "what are you" in clean_in:
            return "Still Seven, your personal AI assistant."

        if "call you" in clean_in:
            return "Seven. Same as always."

        if "created you" in clean_in or "made you" in clean_in:
            creator = config.KEY['identity']['creator']
            return random.choice([
                f"{creator}. Same answer.",
                f"Still {creator}.",
            ])

        # Check if there is new memory for this repeated question
        try:
            search_uid   = (speaker_id if speaker_id not in ("default", "unknown")
                            else config.KEY.get("identity", {}).get(
                                "user_name", "default").lower() or "default")
            fresh_memory = seven_memory.search(clean_in, user_id=search_uid)
            if fresh_memory:
                # New memories found -- let the LLM handle it with fresh context
                return None
        except Exception:
            pass

        repeat_count = speaker_questions.count(clean_in)
        if repeat_count >= 2:
            return "You have asked me this multiple times. My answer has not changed."
        return "You just asked me that. Same answer."

    # Not a repeat -- record this question for future detection
    if not is_command and not is_greeting:
        if speaker_id not in RECENT_QUESTIONS:
            RECENT_QUESTIONS[speaker_id] = []
        RECENT_QUESTIONS[speaker_id].append(clean_in)
        # Keep only last MAX_RECENT questions
        if len(RECENT_QUESTIONS[speaker_id]) > MAX_RECENT:
            RECENT_QUESTIONS[speaker_id].pop(0)

    # Return modified prompt if similar_detected (add note for LLM)
    if similar_detected:
        return "__SIMILAR_DETECTED__"  # brain.py injects the note

    return None


# =============================================================================
# LAYER 3: IDENTITY OVERRIDES
# =============================================================================

def handle_identity(clean_in, words, speaker_id, speaker_name, config):
    """
    Handle direct identity questions and simple social inputs.
    Returns immediately without touching LLM, memory, or web.

    COVERS:
        - "What's your name?" / "Who are you?"
        - "What's my name?" / "Who am I?"
        - Greetings: "hi", "hey", "hello", "good morning"
        - Farewells: "bye", "goodbye", "good night"
        - "What are you?" / "What should I call you?"
        - Schedule alert confirmations (yes/no after alarm)
        - "How/why do you know that?" (memory how questions)
        - "What did I just say?" (session recall)
        - TARS setting queries (read-only -- writes handled by handle_tars_controls)

    RETURNS:
        str  -- identity response
        None -- if not an identity question
    """
    first_word = words[0] if words else ""

    # --- SEVEN'S NAME ---
    if "your name" in clean_in:
        if len(words) <= 6 and "how" not in clean_in and "did" not in clean_in:
            return "I am Seven. You can call me Seven."

    if clean_in == "who are you":
        return "I am Seven, your personal AI assistant."

    # --- USER'S NAME ---
    if "my name" in clean_in or "who am i" in clean_in:
        is_direct = (
            "is" not in clean_in
            and "how many" not in clean_in
            and "why" not in clean_in
            and "did" not in clean_in
            and "times" not in clean_in
            and "about" not in clean_in
            and "friend" not in clean_in
        )
        if is_direct:
            if (speaker_id not in ("default", "unknown")
                    and speaker_name == speaker_id.title()):
                return "You haven't told me your name yet."
            return f"You are {speaker_name}."

    # --- GREETINGS ---
    greeting_words = ["hi", "hello", "hey", "hi seven", "hello seven", "hey seven",
                      "good morning", "good afternoon", "good evening",
                      "heyy", "heyyy", "heyyyy", "hii", "hiii", "yo", "sup",
                      "wassup", "whatsup", "what's up"]
    _is_greeting_like = (
        clean_in in greeting_words
        or (len(words) <= 2 and first_word in ["hi", "hey", "hello", "yo", "sup"])
    )
    if _is_greeting_like:
        greetings = [
            "Yeah?",
            "What's up?",
            "Go ahead.",
            "Hey.",
            "What do you need?",
        ]
        if speaker_name and speaker_name.lower() not in ("there", "admin", "default"):
            greetings += [
                f"What is it, {speaker_name}?",
                f"Yeah, {speaker_name}?",
                f"What's up, {speaker_name}?",
            ]
        return random.choice(greetings)

    # --- FAREWELLS ---
    farewell_words = ["bye", "goodbye", "bye seven", "goodbye seven", "see you",
                      "see ya", "later", "good night", "goodnight"]
    if clean_in in farewell_words:
        return f"Later, {speaker_name}."

    # --- SCHEDULE ALERT CONFIRMATIONS ---
    _confirm_words = {"yes", "yeah", "yep", "got it", "okay", "ok",
                      "understood", "noted", "done", "sure", "yup"}
    _deny_words    = {"no", "nope", "didn't", "missed", "again",
                      "repeat", "what", "remind me again"}

    if clean_in in _confirm_words:
        try:
            import json as _js
            _ap = os.path.join(os.environ.get('APPDATA', ''),
                               'SEVEN', 'schedule_alert.json')
            if os.path.exists(_ap):
                _alert = _js.load(open(_ap))
                if _alert.get("active"):
                    from backend.api_server import dismiss_schedule_alert_sync
                    dismiss_schedule_alert_sync()
                    return random.choice(["Good. Dismissed.", "Got it. Cleared.", "Noted."])
        except Exception:
            pass

    if clean_in in _deny_words and len(words) <= 3:
        try:
            import json as _js
            _ap = os.path.join(os.environ.get('APPDATA', ''),
                               'SEVEN', 'schedule_alert.json')
            if os.path.exists(_ap):
                _alert = _js.load(open(_ap))
                if _alert.get("active"):
                    return "Want me to remind you again? Say how long."
        except Exception:
            pass

    # --- WHAT ARE YOU ---
    if clean_in == "what are you":
        return "I am Seven, your personal AI assistant."

    # --- WHAT SHOULD I CALL YOU ---
    if "call you" in clean_in or "should i call" in clean_in:
        return "You can call me Seven."

    # "instead of seven" / "other than seven" -- name alternatives
    if (("instead of" in clean_in or "other than" in clean_in
         or "besides" in clean_in) and "seven" in clean_in):
        return "Seven is my name. That is the only one I have."
    
    # --- HOW TO USE SEVEN QUESTIONS ---
    _how_commands = (
        "add command" in clean_in
        or "add to commands" in clean_in
        or ("how" in clean_in and "command" in clean_in)
        or ("how" in clean_in and "add" in clean_in and 
            any(w in clean_in for w in ["path", "app", "file", "folder", "url"]))
        or "commands section" in clean_in
        or "how do i add" in clean_in
    )
    if _how_commands:
        return (
            "Go to the Commands section in the right sidebar. "
            "There you can add file paths, folder paths, URLs, and name them anything. "
            "Then just say that name and I open it instantly."
        )

    _how_plans = (
        ("upgrade" in clean_in or "plan" in clean_in or "pro" in clean_in)
        and any(w in clean_in for w in ["how", "where", "what"])
    )
    if _how_plans:
        return (
            "Go to Plans in the sidebar. "
            "You can see your current plan and upgrade options there."
        )

    # --- VAGUE OPINION QUESTIONS ---
    _opinion_triggers = (
        clean_in in ["what you think", "what do you think", "your thoughts",
                     "what are your thoughts", "your opinion", "what is your opinion",
                     "what do you think about it", "thoughts"]
        or (clean_in.startswith("what") and "think" in clean_in and len(words) <= 5)
    )
    if _opinion_triggers:
        return random.choice([
            "About what specifically?",
            "Need more context. Think about what?",
            "That is a broad question. Narrow it down.",
            "You will need to be more specific.",
        ])

    # --- MEMORY HOW QUESTIONS ---
    # "how do you know my name?", "how did you know that?"
    _memory_how = (
        ("how" in clean_in or "why" in clean_in)
        and ("know" in clean_in or "knew" in clean_in or "remember" in clean_in)
        and any(w in clean_in for w in ["that", "my name", "this", "me", "about me"])
    )
    if _memory_how:
        _humor = config.KEY.get('brain', {}).get('tars_humor', 75)
        if _humor >= 60:
            return random.choice([
                "You told me. I listened.",
                "You mentioned it. I remembered. That is my job.",
                "I pay attention. It is one of my better qualities.",
                "Memory. I have one.",
                "You said it. I stored it. Not complicated.",
            ])
        return random.choice([
            "You told me earlier. I stored it in memory.",
            "I remembered what you told me in a previous conversation.",
            "It is in my local memory from when you shared it with me.",
        ])

    # --- SESSION RECALL ---
    # "What did I just say?", "What was my last message?"
    _session_recall = (
        ("what did i" in clean_in
         and any(w in clean_in for w in ["say", "ask", "said"]))
        or "what was my last" in clean_in
        or "repeat what i" in clean_in
        or clean_in in ["what did i say", "what i said",
                         "my last message", "what did i just say"]
    )
    if _session_recall:
        # Import here to avoid circular -- context_manager is in same package
        from brain_modules.context_manager import get_history
        history   = get_history(speaker_id)
        user_msgs = [h for h in history if h.startswith("User:")]

        if len(user_msgs) >= 2:
            last_msg = user_msgs[-2].replace("User:", "").strip()
            if "===" in last_msg or "CAPABILITIES" in last_msg:
                last_msg = (last_msg.split("User asked:")[-1].strip()
                            if "User asked:" in last_msg
                            else "I could not recall cleanly. Ask me again?")
            return f'You said: "{last_msg}"'
        elif len(user_msgs) == 1:
            last_msg = user_msgs[0].replace("User:", "").strip()
            if "===" in last_msg:
                last_msg = (last_msg.split("User asked:")[-1].strip()
                            if "User asked:" in last_msg
                            else "I could not recall cleanly.")
            return f'You said: "{last_msg}"'
        return "Nothing recorded in this session yet."

    return None


# =============================================================================
# LAYER 4: TARS PERSONALITY CONTROLS
# =============================================================================

def handle_tars_controls(clean_in, words, config):
    """
    Handle user commands to read or adjust TARS personality sliders.

    TARS SLIDERS:
        Humor   (0-100): controls how dry/witty Seven is
        Honesty (0-100): controls how blunt/diplomatic Seven is

    OPERATIONS:
        SET:   "set your humor to 80" -> saves to config, returns confirmation
        QUERY: "what is your humor level?" -> reads from config, returns current

    WHY USER-ADJUSTABLE:
        TARS in Interstellar had configurable humor: "Humor 75%".
        Seven mirrors this. Users who want clinical responses set humor=0.
        Users who want banter set humor=100.
        The prompt_builder.py reads these values and changes the system
        prompt accordingly.

    CONFIG PERSISTENCE:
        Values saved to config.json immediately.
        Next session, prompt_builder reads them from config.
        Settings UI shows them in the Brain section sliders.

    RETURNS:
        str  -- confirmation or current level string
        None -- if not a TARS control command
    """
    # --- DETECT INTENT ---
    _humor_set = (
        any(w in clean_in for w in ["set", "change", "make", "put"])
        and any(w in clean_in for w in ["humor", "humour", "funny", "sarcasm"])
    )
    _honesty_set = (
        any(w in clean_in for w in ["set", "change", "make", "put"])
        and any(w in clean_in for w in ["honesty", "honest", "direct", "brutal"])
    )
    _humor_query  = (
        any(w in clean_in for w in ["humor", "humour"])
        and any(w in clean_in for w in ["what", "current", "your", "level", "how"])
    )
    _honesty_query = (
        any(w in clean_in for w in ["honesty", "honest"])
        and any(w in clean_in for w in ["what", "current", "your", "level", "how"])
    )

    # --- SET OPERATIONS ---
    if _humor_set or _honesty_set:
        _num_match = re.search(r'\b(\d{1,3})\b', clean_in)
        if _num_match:
            _val = max(0, min(100, int(_num_match.group(1))))
            try:
                _bcfg = config.KEY.get('brain', {})

                if _humor_set:
                    _bcfg['tars_humor'] = _val
                    config.update_config({'brain': _bcfg})
                    _label = (
                        "deadpan"        if _val <= 10 else
                        "mostly serious" if _val <= 30 else
                        "dry wit"        if _val <= 60 else
                        "TARS mode"      if _val <= 85 else
                        "maximum sarcasm"
                    )
                    return f"Humor set to {_val}%. {_label.capitalize()}."

                if _honesty_set:
                    _bcfg['tars_honesty'] = _val
                    config.update_config({'brain': _bcfg})
                    _label = (
                        "diplomatic"  if _val <= 20 else
                        "tactful"     if _val <= 50 else
                        "direct"      if _val <= 80 else
                        "blunt"       if _val <= 95 else
                        "no filter"
                    )
                    return f"Honesty set to {_val}%. {_label.capitalize()}."

            except Exception as _err:
                print(Fore.YELLOW + f"[TARS] Setting save failed: {_err}")
                return "Could not save that setting."
        else:
            if _humor_set:
                return "Give me a number. What percentage humor do you want?"
            return "Give me a number. What percentage honesty do you want?"

    # --- QUERY OPERATIONS ---
    if _humor_query:
        _cur = config.KEY.get('brain', {}).get('tars_humor', 75)
        _label = (
            "deadpan"        if _cur <= 10 else
            "mostly serious" if _cur <= 30 else
            "dry wit"        if _cur <= 60 else
            "TARS default"   if _cur <= 85 else
            "maximum sarcasm"
        )
        return f"Humor is at {_cur}%. {_label.capitalize()}."

    if _honesty_query:
        _cur = config.KEY.get('brain', {}).get('tars_honesty', 85)
        _label = (
            "diplomatic"  if _cur <= 20 else
            "tactful"     if _cur <= 50 else
            "direct"      if _cur <= 80 else
            "blunt"       if _cur <= 95 else
            "no filter"
        )
        return f"Honesty is at {_cur}%. {_label.capitalize()}."

    return None