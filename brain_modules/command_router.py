"""
=============================================================================
brain_modules/command_router.py
PROJECT SEVEN -- Python-First Command Router

WHAT THIS FILE DOES:
    Parses natural language voice commands into structured tag strings.
    Completely bypasses the LLM for structured commands.
    Returns tag strings like:
        "action=volume_set value=50"
        "action=snap target=chrome position=left"
        "action=reminder time=at_5pm message=call_mom"

WHY PYTHON-FIRST (not LLM-first):
    LLM approach: "set volume to 50" -> Ollama -> 2-3 seconds -> maybe right tag
    Python approach: "set volume to 50" -> regex -> 1ms -> always right tag

    For structured commands, Python regex is:
        FASTER:       1ms vs 2000ms
        RELIABLE:     deterministic vs probabilistic
        OFFLINE-SAFE: works even if Ollama is slow or busy

    This is the same approach used by Alexa, Siri, and Google Assistant.
    They classify intent first, call NLU only for open-ended questions.

DESIGN PATTERN: Strategy Pattern
    Each builder function (_build_window_tag, _build_sched_tag,
    _build_system_tag) is a strategy for a different command domain.
    brain.py selects which strategy to run based on trigger detection.

INTERVIEW TALKING POINT:
    "I separated command parsing from the LLM inference path. Python
     handles structured commands deterministically in under 1ms. The LLM
     only handles conversation and open-ended questions. This reduces
     average response latency from 3 seconds to under 100ms for 70%
     of user commands."

WHAT EACH FUNCTION RETURNS:
    _build_window_tag() -> "action=snap target=chrome position=left" or None
    _build_sched_tag()  -> "action=reminder time=at_5pm message=X" or None
    _build_system_tag() -> "action=volume_set value=50" or None

    None means "this input is not a command of this type"
    brain.py treats None as "pass to next layer"

ERROR HANDLING:
    All functions return None on failure, never raise.
    The caller (brain.py) handles None gracefully.
    This prevents a parsing bug from crashing the voice loop.
=============================================================================
"""

import re
import random

# ---------------------------------------------------------------------------
# MODULE-LEVEL STATE
# Tracks last system domain for pronoun resolution.
# "set volume to 50" -> LAST_SYSTEM_DOMAIN = "volume"
# "make it 40"       -> resolves "it" to volume -> "action=volume_set value=40"
#
# WHY MODULE-LEVEL (not class):
#     brain.py imports these as functions, not a class instance.
#     Module-level state persists for the session -- correct behavior.
#     If this were inside a function, state would reset every call.
# ---------------------------------------------------------------------------
LAST_SYSTEM_DOMAIN = None  # "volume", "brightness", or None


def get_last_system_domain():
    """
    Returns the last system domain that was controlled.
    Used by brain.py to resolve pronouns like "it" and "that".
    Example: "set volume to 50" then "make it 40" -> volume_set 40
    """
    return LAST_SYSTEM_DOMAIN


def set_last_system_domain(domain):
    """
    Updates the last system domain.
    Called by _build_system_tag() when a domain is detected.
    """
    global LAST_SYSTEM_DOMAIN
    LAST_SYSTEM_DOMAIN = domain


# =============================================================================
# WINDOW COMMAND PARSER
# =============================================================================

def _build_window_tag(clean_in, is_desktop_cmd, is_notarget_cmd, is_layout,
                      put_pattern, is_switch, is_move_monitor, is_swap,
                      is_window_close, is_transparent, is_solid, is_pin, is_unpin):
    """
    Parse natural language into a WINDOW action tag parameter string.

    HOW IT WORKS:
        Takes pre-detected boolean flags from brain.py (which detected WHAT
        type of window command this is) and parses the DETAILS (target, position).

    ARGS:
        clean_in      -- lowercased, punctuation-stripped user input
        is_*          -- boolean flags, each True if that command type was detected

    RETURNS:
        str  -- param string like "action=snap target=chrome position=left"
        None -- if parsing fails or input is ambiguous

    CALLED BY: brain.py think() Layer 4.5

    INTERVIEW NOTE:
        "The window parser uses a cascade of if-elif blocks, each handling
         one command type. I pre-detect the command type in brain.py using
         simple keyword checks, then pass boolean flags here. Separating
         detection from parsing makes both easier to test and debug."
    """
    words = clean_in.split()

    # --- NO-TARGET COMMANDS (undo, list, etc) ---
    if is_notarget_cmd:
        if "undo" in clean_in or "put it back" in clean_in or "revert" in clean_in:
            return "action=undo"
        if (("what" in clean_in and "open" in clean_in)
                or "list windows" in clean_in
                or "show windows" in clean_in
                or "running" in clean_in):
            return "action=list"
        return None

    # --- DESKTOP COMMANDS (no target needed) ---
    if is_desktop_cmd:
        if "show desktop" in clean_in or "clear desktop" in clean_in:
            return "action=show_desktop"
        if ("hide all" in clean_in
                or "minimize all" in clean_in
                or "minimize everything" in clean_in):
            return "action=minimize_all"
        if "show all" in clean_in or "restore all" in clean_in:
            return "action=show_desktop"
        return "action=show_desktop"

    # --- SWAP COMMAND ---
    # "swap chrome and notepad" -> swap two windows
    if is_swap:
        noise = ["swap", "and", "with", "please", "can", "you", "the"]
        app_words = [w for w in clean_in.split() if w not in noise and len(w) > 1]
        if len(app_words) >= 2:
            targets = ",".join(app_words[:2])
            return f"action=swap targets={targets}"
        return None

    # --- WINDOW-LEVEL CLOSE ---
    # "close this window" -- kills the active window, not the process
    if is_window_close:
        if "this" in clean_in or "active" in clean_in or "the window" in clean_in:
            return "action=close_window target=this"
        return None

    # --- LAYOUT COMMANDS ---
    # "put chrome and code side by side" -> split layout
    # "stack chrome and code"            -> stack layout
    # "quad chrome code notepad explorer" -> 4-corner layout
    if is_layout:
        if "stack" in clean_in:
            mode = "stack"
        elif "quad" in clean_in:
            mode = "quad"
        else:
            mode = "split"

        # Extract app names by removing layout keywords
        noise = ["put", "and", "side", "by", "split", "screen", "view",
                 "stack", "quad", "tile", "arrange", "on", "the", "in",
                 "with", "next", "to", "beside", "layout"]
        apps = [w for w in words if w not in noise and len(w) > 1]

        if len(apps) >= 2:
            targets = ",".join(apps)
            return f"action=layout mode={mode} targets={targets}"
        return None

    # --- PUT PATTERN ---
    # "put chrome on the left" -> snap chrome to left
    if put_pattern:
        after_put = clean_in.split("put ", 1)[1] if "put " in clean_in else ""

        if " on " in after_put:
            target_part   = after_put.split(" on ")[0].strip()
            position_part = after_put.split(" on ")[1].strip()
        else:
            return None

        # Map position phrases to canonical position names
        pos_map = {
            "the left": "left",       "left": "left",       "left side": "left",
            "the right": "right",     "right": "right",     "right side": "right",
            "top left": "top-left",   "the top left": "top-left",
            "top right": "top-right", "the top right": "top-right",
            "bottom left": "bottom-left", "the bottom left": "bottom-left",
            "bottom right": "bottom-right", "the bottom right": "bottom-right",
            "top": "top",             "the top": "top",
            "bottom": "bottom",       "the bottom": "bottom",
        }

        position = None
        for phrase, pos in pos_map.items():
            if phrase in position_part:
                position = pos
                break

        if position and target_part:
            return f"action=snap target={target_part} position={position}"
        return None

    # --- SWITCH/FOCUS COMMANDS ---
    # "switch to chrome", "bring up notepad", "focus on code"
    if is_switch:
        for sv in ["switch to", "bring up", "go to", "focus on", "focus",
                   "show me", "pull up", "jump to", "open up"]:
            if sv in clean_in:
                sv_pos = clean_in.index(sv)
                target = clean_in[sv_pos + len(sv):].strip()
                if target:
                    return f"action=focus target={target}"
        return None

    # --- MOVE TO MONITOR ---
    # "move chrome to monitor 2" / "move chrome to second monitor"
    if is_move_monitor:
        ordinals = {
            "second": "1", "2": "1",
            "third":  "2", "3": "2",
            "first":  "0", "1": "0",
            "primary": "0"
        }
        after_move = clean_in.split("move ", 1)[1] if "move " in clean_in else ""
        if " to " in after_move:
            target       = after_move.split(" to ")[0].strip()
            monitor_part = after_move.split(" to ")[1].strip()
        else:
            return None

        monitor_idx = "1"  # Default to second monitor
        for word, idx in ordinals.items():
            if word in monitor_part:
                monitor_idx = idx
                break

        if target:
            return f"action=move_monitor target={target} monitor={monitor_idx}"
        return None

    # --- SIMPLE VERB + TARGET ---
    # "minimize chrome", "maximize notepad", "restore explorer"
    verb_map = {
        "minimize":    "minimize",
        "maximise":    "maximize",
        "maximize":    "maximize",
        "restore":     "restore",
        "center":      "center",
        "centre":      "center",
        "fullscreen":  "fullscreen",
        "full screen": "fullscreen",
    }

    for verb, action in verb_map.items():
        if verb in clean_in:
            verb_pos = clean_in.index(verb)
            target   = clean_in[verb_pos + len(verb):].strip()
            if target:
                return f"action={action} target={target}"
            return None

    # --- SNAP COMMANDS ---
    # "snap chrome left", "snap notepad to the right"
    if "snap " in clean_in:
        snap_pos   = clean_in.index("snap ")
        after_snap = clean_in[snap_pos + 5:].strip()
        pos_words  = ["left", "right", "top", "bottom",
                      "top-left", "top-right", "bottom-left", "bottom-right"]

        for pw in pos_words:
            if after_snap.endswith(pw):
                target = after_snap[:-(len(pw))].strip()
                target = target.rstrip(" to the").rstrip(" to").strip()
                if target:
                    return f"action=snap target={target} position={pw}"

        return f"action=snap target={after_snap} position=left"

    # --- PIN / ALWAYS ON TOP ---
    # "pin chrome", "keep notepad on top"
    if is_pin:
        noise = ["pin", "keep", "on", "top", "always", "please", "can",
                 "you", "the", "make", "set", "it"]
        target_words = [w for w in clean_in.split()
                        if w not in noise and len(w) > 1]
        if target_words:
            return f"action=pin target={' '.join(target_words)}"
        return None

    # --- UNPIN ---
    # "unpin chrome", "remove notepad from top"
    if is_unpin:
        noise = ["unpin", "remove", "from", "top", "not", "on", "please",
                 "can", "you", "the", "make", "it"]
        target_words = [w for w in clean_in.split()
                        if w not in noise and len(w) > 1]
        if target_words:
            return f"action=unpin target={' '.join(target_words)}"
        return None

    # --- TRANSPARENCY ---
    # "make chrome transparent"       -> default 80%
    # "make chrome 50% transparent"   -> exact 50%
    # "make chrome very transparent"  -> heavy 40%
    # "make chrome more transparent"  -> relative decrease
    if is_transparent:
        # Check for explicit percentage first
        pct_match = re.search(
            r'(\d+)\s*%?\s*(?:percent|transparent|transparency|opacity)?',
            clean_in
        )

        # Relative direction words
        is_more   = any(w in clean_in for w in ["more transparent", "more see through"])
        is_less   = any(w in clean_in for w in ["less transparent", "brighter",
                                                  "less see through", "more visible",
                                                  "more opaque"])
        is_slight = any(w in clean_in for w in ["a bit", "a little", "slightly",
                                                  "a touch", "just a bit"])
        is_very   = any(w in clean_in for w in ["very", "really", "super",
                                                  "extremely", "heavily", "fully"])

        # Determine opacity value
        if pct_match:
            pct     = max(10, min(100, int(pct_match.group(1))))
            opacity = pct / 100.0
        elif is_more:
            opacity = "more"   # hands/windows.py handles relative adjustment
        elif is_less:
            opacity = "less"
        elif is_slight:
            opacity = 0.9
        elif is_very:
            opacity = 0.4
        else:
            opacity = 0.8  # Default: visible but noticeably transparent

        # Extract target (remove all noise words)
        noise = ["make", "set", "transparent", "see", "through", "translucent",
                 "please", "can", "you", "the", "it", "a", "bit", "little",
                 "slightly", "very", "really", "super", "extremely", "heavily",
                 "more", "less", "much", "touch", "just", "keep", "put",
                 "percent", "opacity", "transparency", "to", "at", "on",
                 "brighter", "visible", "opaque", "fully"]
        target_words = [
            w for w in clean_in.split()
            if w not in noise and len(w) > 1 and not w.replace("%", "").isdigit()
        ]

        if target_words:
            return f"action=transparent target={' '.join(target_words)} opacity={opacity}"
        return None

    # --- MAKE SOLID / OPAQUE ---
    # "make chrome solid", "make notepad opaque"
    if is_solid:
        noise = ["make", "set", "solid", "opaque", "not", "transparent",
                 "please", "can", "you", "the", "it", "back", "normal",
                 "to", "fully", "completely", "100"]
        target_words = [
            w for w in clean_in.split()
            if w not in noise and len(w) > 1
            and not w.replace("%", "").isdigit()
        ]
        if target_words:
            return f"action=solid target={' '.join(target_words)}"
        return None

    return None


# =============================================================================
# SCHEDULER COMMAND PARSER
# =============================================================================

def _build_sched_tag(clean_in, words):
    """
    Parse natural language into a SCHED action tag parameter string.

    HANDLES:
        - Alarms:    "set an alarm for 7am", "wake me up at 6:30"
        - Reminders: "remind me to call mom at 5pm"
        - Timers:    "set a timer for 10 minutes"
        - Events:    "schedule a meeting tomorrow at 2pm"
        - List:      "what reminders do I have?"
        - Cancel:    "cancel the alarm", "clear all reminders"

    SPACE ENCODING:
        Values with spaces are encoded with underscores for tag transport.
        "call mom" -> "call_mom"
        hands/scheduler.py decodes underscores back to spaces.

        WHY: The tag string is space-delimited. "message=call mom" would
        parse as message=call and a stray "mom". Underscore encoding
        solves this without a more complex parser.

    RETURNS:
        str  -- param string like "action=reminder time=at_5pm message=call_mom"
        None -- if input is not a scheduler command

    CALLED BY: brain.py think() Layer 4.5
    """

    def _enc(text):
        """Encode spaces as underscores for tag value transport."""
        return text.strip().replace(" ", "_") if text else ""

    # -----------------------------------------------------------------
    # LIST / QUERY PHRASES
    # "what reminders do I have?", "show my schedule", "any alarms?"
    # -----------------------------------------------------------------

    LIST_PHRASES = [
        "what reminders", "what alarms", "what timers", "what events",
        "show my schedule", "show schedule", "show my reminders",
        "show my alarms", "show my timers", "list reminders",
        "list alarms", "list timers", "list schedules", "any alarms",
        "any reminders", "any timers", "what's scheduled", "whats scheduled",
        "what is scheduled", "what's coming up", "whats coming up",
        "upcoming reminders", "upcoming events", "do i have any reminders",
        "do i have any alarms", "my schedule", "my reminders", "my alarms"
    ]

    TIMER_REMAINING_PHRASES = [
        "how much time left", "how long left", "time remaining",
        "how much time on my timer", "how long on the timer",
        "timer status", "whats left on the timer", "whats left on my timer",
        "how much time is left", "time left on timer"
    ]

    for phrase in TIMER_REMAINING_PHRASES:
        if phrase in clean_in:
            return "action=timer_remaining"

    for phrase in LIST_PHRASES:
        if phrase in clean_in:
            # Narrow down list type if user specified one
            if any(w in clean_in for w in ["alarm", "alarms"]):
                return "action=list list_type=alarms"
            elif any(w in clean_in for w in ["timer", "timers"]):
                return "action=list list_type=timers"
            elif any(w in clean_in for w in ["reminder", "reminders"]):
                return "action=list list_type=reminders"
            elif any(w in clean_in for w in ["event", "events", "meeting", "meetings"]):
                return "action=list list_type=events"
            return "action=list"

    # -----------------------------------------------------------------
    # CANCEL / DELETE
    # "cancel my 5pm reminder", "delete the alarm", "clear all"
    # -----------------------------------------------------------------

    CANCEL_VERBS = ["cancel", "delete", "remove", "clear", "stop"]
    has_cancel   = any(w in words for w in CANCEL_VERBS)

    if has_cancel:
        # Cancel everything
        if any(p in clean_in for p in ["everything", "all schedules", "all reminders",
                                        "all alarms", "all timers", "clear all"]):
            if "alarm" in clean_in:
                return "action=cancel cancel_type=alarms"
            elif "timer" in clean_in:
                return "action=cancel cancel_type=timers"
            elif "reminder" in clean_in:
                return "action=cancel cancel_type=reminders"
            elif "event" in clean_in or "meeting" in clean_in:
                return "action=cancel cancel_type=events"
            return "action=cancel cancel_type=all"

        # Cancel specific type
        if any(w in clean_in for w in ["the alarm", "my alarm"]):
            return "action=cancel cancel_type=alarm"
        if any(w in clean_in for w in ["the timer", "my timer"]):
            return "action=cancel cancel_type=timer"
        if any(w in clean_in for w in ["the reminder", "my reminder"]):
            return "action=cancel cancel_type=reminder"

        # Cancel by match text -- "cancel my 5pm reminder"
        match_text = clean_in
        for verb in CANCEL_VERBS:
            match_text = match_text.replace(verb, "")
        match_text = match_text.replace("my", "").replace("the", "").strip()

        if match_text:
            return f"action=cancel match={_enc(match_text)}"

        return "action=cancel cancel_type=all"

    # -----------------------------------------------------------------
    # TIMER
    # "set a timer for 10 minutes", "5 minute timer"
    # -----------------------------------------------------------------

    TIMER_PHRASES = [
        "set a timer", "start a timer", "timer for", "countdown",
        "start timer", "set timer", "begin timer", "start a countdown",
        "timer of", "count down"
    ]

    is_timer = any(p in clean_in for p in TIMER_PHRASES)

    # Catch "5 minute timer", "10 min timer" suffix pattern
    timer_suffix = re.search(
        r'(\d+)\s*(?:minute|min|mins|hour|hr|hrs|second|sec|secs)\s*timer',
        clean_in
    )
    if timer_suffix:
        is_timer = True

    if is_timer:
        dur_match = re.search(
            r'(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)',
            clean_in
        )
        if dur_match:
            amount    = int(dur_match.group(1))
            unit      = dur_match.group(2).lower()

            # Convert all units to seconds for scheduler
            if unit.startswith("sec"):
                secs = amount
            elif unit.startswith("min"):
                secs = amount * 60
            elif unit.startswith("h"):
                secs = amount * 3600
            else:
                secs = amount * 60

            # Extract optional message after the duration
            after_pos     = dur_match.end()
            after_duration = clean_in[after_pos:].strip()
            after_duration = re.sub(r'^timer\s*', '', after_duration).strip()

            message = ""
            if after_duration:
                after_duration = re.sub(r'^(for|to|called|named)\s+', '', after_duration).strip()
                if after_duration and len(after_duration) > 1:
                    message = after_duration

            tag = f"action=timer duration={secs}"
            if message:
                tag += f" message={_enc(message)}"
            return tag

        return "action=timer_ask"

    # -----------------------------------------------------------------
    # ALARM
    # "set an alarm for 7am", "wake me up at 6:30"
    # -----------------------------------------------------------------

    ALARM_PHRASES = [
        "set an alarm", "set alarm", "alarm for", "alarm at",
        "wake me up", "wake me at"
    ]
    is_alarm = any(p in clean_in for p in ALARM_PHRASES)

    if is_alarm:
        # Extract time from everything after the alarm phrase
        time_text = clean_in
        for prefix in ["set an alarm for", "set alarm for", "alarm for",
                       "set an alarm at", "set alarm at", "alarm at",
                       "wake me up at", "wake me at"]:
            if prefix in clean_in:
                time_text = clean_in.split(prefix)[-1].strip()
                break

        # Recurrence detection
        recur = ""
        RECUR_WORDS = {
            "every day":     "daily",        "everyday":    "daily",
            "daily":         "daily",        "every morning": "daily",
            "every night":   "daily",        "every weekday": "weekdays",
            "weekdays":      "weekdays",
            "every monday":  "every_monday", "every tuesday":   "every_tuesday",
            "every wednesday": "every_wednesday",
            "every thursday": "every_thursday",
            "every friday":  "every_friday", "every saturday": "every_saturday",
            "every sunday":  "every_sunday"
        }
        for phrase, val in RECUR_WORDS.items():
            if phrase in clean_in:
                recur      = val
                time_text  = time_text.replace(phrase, "").strip()
                break

        if time_text:
            tag = f"action=alarm time={_enc(time_text)}"
            if recur:
                tag += f" recur={recur}"
            return tag

        return "action=alarm_ask"

    # -----------------------------------------------------------------
    # REMINDER
    # "remind me to call mom at 5pm", "remind me in 20 minutes to stretch"
    # -----------------------------------------------------------------

    REMINDER_PHRASES = [
        "remind me", "remember me to", "remember me",
        "reminder to", "reminder for",
        "dont let me forget", "don't let me forget",
        "remind me to", "remind me about", "remember to tell me",
        "tell me to", "let me know to", "let me know when",
        "alert me to", "notify me to", "ping me to",
        "alert me in", "notify me in", "ping me in",
    ]
    is_reminder = any(p in clean_in for p in REMINDER_PHRASES)

    if is_reminder:
        # Check for recurrence
        recur = ""
        for phrase, val in {
            "every day": "daily",   "everyday": "daily",   "daily": "daily",
            "every weekday": "weekdays",
            "every monday":    "every_monday",
            "every tuesday":   "every_tuesday",
            "every wednesday": "every_wednesday",
            "every thursday":  "every_thursday",
            "every friday":    "every_friday",
            "every saturday":  "every_saturday",
            "every sunday":    "every_sunday",
            "weekly":          "weekly"
        }.items():
            if phrase in clean_in:
                recur = val
                break

        # Strip reminder phrase from start to get remainder
        remainder = clean_in
        for prefix in REMINDER_PHRASES:
            if prefix in remainder:
                remainder = remainder.split(prefix, 1)[-1].strip()
                break

        # Remove recurrence phrase from remainder
        if recur:
            for phrase in ["every day", "everyday", "daily", "every weekday",
                           "every monday", "every tuesday", "every wednesday",
                           "every thursday", "every friday", "every saturday",
                           "every sunday", "weekly"]:
                remainder = remainder.replace(phrase, "").strip()

        message   = ""
        time_text = ""

        # Rewrite "after X seconds" -> "in X seconds" for unified parsing
        after_match = re.search(
            r'after\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)',
            remainder
        )
        if after_match:
            remainder = remainder.replace(
                after_match.group(0),
                f"in {after_match.group(1)} {after_match.group(2)}"
            )

        # "in X minutes/hours" pattern
        in_match = re.search(
            r'in\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)',
            remainder
        )
        if in_match:
            time_text    = in_match.group(0)
            before_match = remainder[:in_match.start()].strip()
            after_in     = remainder[in_match.end():].strip()

            if after_in:
                message = re.sub(r'^(to|about|that|for)\s+', '', after_in).strip()
            elif before_match:
                message = re.sub(r'^(to|about|that|for)\s+', '', before_match).strip()
        else:
            # "at [time]" pattern
            at_match = re.search(
                r'\b(at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
                remainder
            )
            if at_match:
                time_text = at_match.group(0)
                parts     = remainder.split(time_text)
                before    = parts[0].strip() if parts[0] else ""
                after     = parts[1].strip() if len(parts) > 1 and parts[1] else ""
                message   = before if before else after
                message   = re.sub(r'^(to|about|that)\s+', '', message).strip()
                message   = re.sub(r'(to|about|that)$',   '', message).strip()
            else:
                # "tomorrow", "next monday" patterns
                tw_match = re.search(
                    r'(tomorrow|next\s+\w+day|next\s+week|tonight)',
                    remainder
                )
                if tw_match:
                    time_text   = tw_match.group(0)
                    clock_after = remainder.split(tw_match.group(0))[-1].strip()
                    clock_match = re.match(
                        r'(at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?',
                        clock_after
                    )
                    if clock_match:
                        time_text  += " " + clock_match.group(0)
                        clock_after = clock_after[clock_match.end():].strip()

                    before  = remainder.split(tw_match.group(0))[0].strip()
                    message = before if before else clock_after
                    message = re.sub(r'^(to|about|that)\s+', '', message).strip()
                else:
                    # No time found -- message is everything
                    message = remainder
                    message = re.sub(r'^(to|about|that)\s+', '', message).strip()

        if message or time_text:
            tag = "action=reminder"
            if time_text:
                tag += f" time={_enc(time_text)}"
            tag += f" message={_enc(message) if message else 'reminder'}"
            if recur:
                tag += f" recur={recur}"
            return tag

        return "action=reminder_ask"

    # -----------------------------------------------------------------
    # EVENT / MEETING
    # "schedule a meeting tomorrow at 2pm", "add event team sync at 3"
    # -----------------------------------------------------------------

    EVENT_PHRASES = [
        "schedule a meeting", "schedule meeting", "add meeting",
        "schedule an event", "schedule event", "add event",
        "calendar event", "add to calendar", "put on calendar"
    ]
    is_event = any(p in clean_in for p in EVENT_PHRASES)

    if is_event:
        remainder = clean_in
        for prefix in EVENT_PHRASES:
            if prefix in remainder:
                remainder = remainder.split(prefix, 1)[-1].strip()
                break

        message   = ""
        time_text = ""

        at_match = re.search(r'\b(at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', remainder)
        on_match = re.search(r'\b(on\s+\w+day|on\s+\w+\s+\d+|tomorrow|next\s+\w+)', remainder)

        if at_match:
            time_part = at_match.group(0)
            before    = remainder[:at_match.start()].strip()
            after     = remainder[at_match.end():].strip()

            if on_match and on_match.start() < at_match.start():
                time_text = on_match.group(0) + " " + time_part
                message   = remainder[:on_match.start()].strip()
                if not message:
                    message = after
            else:
                time_text = time_part
                if on_match:
                    time_text = on_match.group(0) + " " + time_text
                message = before if before else after
        elif on_match:
            time_text = on_match.group(0)
            message   = remainder.replace(time_text, "").strip()
        else:
            message = remainder

        # Clean message
        message = re.sub(r'^(with|for|about|called|named)\s+', '', message).strip()
        message = re.sub(r'\s+(with|for|about)$',              '', message).strip()
        if not message:
            message = "meeting"

        tag = "action=event"
        if time_text:
            tag += f" time={_enc(time_text)}"
        if message:
            tag += f" message={_enc(message)}"
        return tag

    return None


# =============================================================================
# SYSTEM COMMAND PARSER
# =============================================================================

def _build_system_tag(clean_in):
    """
    Parse natural language into a SYS action tag parameter string.

    HANDLES:
        Volume:      up, down, mute, unmute, set to %, get current
        Brightness:  up, down, set to %, get current
        Battery:     status check
        WiFi:        on, off, status
        Bluetooth:   on, off, status
        Media:       play/pause, next, previous, stop
        Dark mode:   on, off
        Night light: on, off
        DND:         on, off
        Airplane:    on, off

    PRONOUN RESOLUTION ("it", "that"):
        When LAST_SYSTEM_DOMAIN is set, "make it 40" resolves to:
        volume_set 40 (if last domain was volume)
        brightness_set 40 (if last domain was brightness)

        This is context-aware NLP at the command level.
        No LLM needed -- just track the last domain touched.

    KEYWORD LOGIC (not phrase matching):
        We check for WORDS not EXACT PHRASES.
        "please set the volume up to 50" -> has_volume=True, num=50, is_up=True
        This is more robust than exact phrase matching.

    CALLED BY: brain.py think() Layer 4.5
    """
    words = clean_in.split()

    def _get_number():
        """Extract first standalone number from input. Ignores substrings."""
        for w in words:
            cleaned = w.replace("%", "")
            if cleaned.isdigit():
                return cleaned
        return None

    # =================================================================
    # VOLUME
    # =================================================================
    has_volume = any(w in words for w in ["volume", "sound", "audio"])

    # Standalone single-word commands
    if clean_in == "mute":
        set_last_system_domain("volume")
        return "action=volume_mute"
    if clean_in == "unmute":
        set_last_system_domain("volume")
        return "action=volume_unmute"
    if clean_in in ["louder", "softer", "quieter"]:
        set_last_system_domain("volume")
        return ("action=volume_up value=10" if clean_in == "louder"
                else "action=volume_down value=10")

    if has_volume or any(w in words for w in ["loud", "quiet"]):
        set_last_system_domain("volume")

        if "unmute" in clean_in:
            return "action=volume_unmute"
        if "mute" in clean_in:
            return "action=volume_mute"

        if any(w in words for w in ["what", "whats", "how", "check", "current",
                                     "level", "status"]):
            return "action=volume_get"

        num = _get_number()

        if any(w in words for w in ["max", "maximum", "full", "highest"]):
            return "action=volume_set value=100"
        if any(w in words for w in ["min", "minimum", "lowest", "zero"]):
            return "action=volume_set value=0"

        if num:
            has_set_intent = any(w in words for w in ["set", "to", "at", "keep",
                                                        "make", "put", "change"])
            if has_set_intent or len(words) <= 3:
                return f"action=volume_set value={num}"

        is_up   = any(w in words for w in ["up", "increase", "raise", "higher",
                                             "more", "louder", "crank", "bump", "boost"])
        is_down = any(w in words for w in ["down", "decrease", "lower", "reduce",
                                             "less", "quieter", "softer"])

        step = num if num else "10"
        if is_up:
            return f"action=volume_up value={step}"
        if is_down:
            return f"action=volume_down value={step}"
        if num:
            return f"action=volume_set value={num}"

    # =================================================================
    # BRIGHTNESS
    # =================================================================
    has_brightness   = any(w in words for w in ["brightness", "bright", "brighter", "brightest"])
    has_dim          = any(w in words for w in ["dim", "dimmer", "dimming"])
    has_screen_light = ("screen" in clean_in and "light" in words
                        and "night" not in clean_in and "mode" not in clean_in)

    if clean_in in ["brighter", "dimmer", "dim"]:
        set_last_system_domain("brightness")
        return ("action=brightness_up value=10" if clean_in == "brighter"
                else "action=brightness_down value=10")

    if has_brightness or has_dim or has_screen_light:
        set_last_system_domain("brightness")

        if any(w in words for w in ["what", "whats", "how", "check", "current",
                                     "level", "status"]):
            return "action=brightness_get"

        num = _get_number()

        if any(w in words for w in ["max", "maximum", "full", "highest", "brightest"]):
            return "action=brightness_set value=100"
        if any(w in words for w in ["min", "minimum", "lowest"]):
            return "action=brightness_set value=5"

        if num:
            has_set_intent = any(w in words for w in ["set", "to", "at", "keep",
                                                        "make", "put", "change"])
            if has_set_intent or len(words) <= 3:
                return f"action=brightness_set value={num}"

        is_up   = any(w in words for w in ["up", "increase", "raise", "higher",
                                             "more", "brighter"])
        is_down = any(w in words for w in ["down", "decrease", "lower", "reduce",
                                             "less", "dimmer", "darker", "dim"])

        step = num if num else "10"
        if is_up:
            return f"action=brightness_up value={step}"
        if is_down:
            return f"action=brightness_down value={step}"
        if num:
            return f"action=brightness_set value={num}"

    # =================================================================
    # BATTERY
    # =================================================================
    if (any(w in words for w in ["battery", "charge", "plugged", "charging"])
            or "power status" in clean_in):
        return "action=battery"

    # =================================================================
    # WIFI
    # =================================================================
    has_wifi = (
        any(w in words for w in ["wifi", "wi-fi"])
        or ("internet" in clean_in
            and any(w in words for w in ["connect", "status", "on", "off"]))
    )
    if has_wifi:
        if any(w in words for w in ["off", "disable", "disconnect", "kill", "stop"]):
            return "action=wifi_off"
        if any(w in words for w in ["on", "enable", "connect", "start"]):
            return "action=wifi_on"
        return "action=wifi_status"

    # =================================================================
    # BLUETOOTH
    # =================================================================
    if "bluetooth" in clean_in:
        if any(w in words for w in ["off", "disable", "disconnect", "kill", "stop"]):
            return "action=bluetooth_off"
        if any(w in words for w in ["on", "enable", "connect", "start"]):
            return "action=bluetooth_on"
        return "action=bluetooth_status"

    # =================================================================
    # MEDIA
    # Guard against: "open spotify", "play a game" -- not media commands
    # =================================================================
    app_context = any(w in words for w in ["open", "launch", "game",
                                            "video", "youtube", "movie", "film"])
    if not app_context:
        if clean_in in ["next", "skip"]:
            return "action=media_next"
        if any(p in clean_in for p in ["next track", "next song", "skip song",
                                        "skip track", "skip this"]):
            return "action=media_next"

        if clean_in in ["previous", "prev"]:
            return "action=media_prev"
        if any(p in clean_in for p in ["previous track", "previous song",
                                        "prev track", "prev song",
                                        "last track", "last song",
                                        "go back a song"]):
            return "action=media_prev"

        if any(p in clean_in for p in ["stop music", "stop playing", "stop the music",
                                        "stop playback", "stop the song"]):
            return "action=media_stop"

        has_music = any(w in words for w in ["music", "song", "track", "playback"])
        if clean_in in ["play", "pause", "resume", "unpause"]:
            return "action=media_play_pause"
        if has_music and any(w in words for w in ["play", "pause", "resume", "stop"]):
            return ("action=media_stop" if "stop" in words
                    else "action=media_play_pause")

    # =================================================================
    # DARK MODE / LIGHT MODE
    # =================================================================
    if "dark mode" in clean_in or "dark theme" in clean_in:
        return ("action=dark_mode_off" if any(w in words for w in ["off", "disable"])
                else "action=dark_mode_on")

    if "light mode" in clean_in or "light theme" in clean_in:
        return ("action=dark_mode_on" if any(w in words for w in ["off", "disable"])
                else "action=dark_mode_off")

    if clean_in in ["go dark", "switch to dark"]:
        return "action=dark_mode_on"
    if clean_in in ["go light", "switch to light"]:
        return "action=dark_mode_off"

    # =================================================================
    # NIGHT LIGHT / BLUE LIGHT
    # =================================================================
    if "night light" in clean_in or "blue light" in clean_in or "night mode" in clean_in:
        return ("action=night_light_off" if any(w in words for w in ["off", "disable"])
                else "action=night_light_on")

    # =================================================================
    # DO NOT DISTURB
    # =================================================================
    if "disturb" in clean_in or "dnd" in words or "focus assist" in clean_in:
        return ("action=dnd_off" if any(w in words for w in ["off", "disable"])
                else "action=dnd_on")

    if any(p in clean_in for p in ["silence notifications", "mute notifications",
                                    "no notifications", "quiet mode"]):
        return "action=dnd_on"
    if any(p in clean_in for p in ["enable notifications", "turn on notifications",
                                    "unmute notifications"]):
        return "action=dnd_off"

    # =================================================================
    # AIRPLANE MODE
    # =================================================================
    if "airplane" in clean_in or "flight mode" in clean_in:
        return ("action=airplane_off" if any(w in words for w in ["off", "disable"])
                else "action=airplane_on")

    return None