"""
=============================================================================
PROJECT SEVEN - brain.py (The Intelligence)
Version: 1.1 (Smart Logic + Memory)
Version: 1.1.2 (Smart Logic + Memory + Mood + Polish)
Version: 1.2 (Smart Logic + Memory + Mood + Voice Identity)

LAYER ORDER (Critical):
    Layer 1: Name SETTING ("My name is Mani") — must be first
    Layer 2: Repetition detector — catches repeated questions
    Layer 3: Identity overrides — keyword detection for name questions
    Layer 4: Input classification — command vs question vs chat
    Layer 5: Memory search — only for questions
    Layer 6: Fact extraction — learns from user
    Layer 7: LLM inference — handles everything else
=============================================================================
"""

import requests
import json
import os
import random
import config
import colorama
from colorama import Fore
from memory import seven_memory
from memory.mood import mood_engine
#from memory.core import seven_memory

colorama.init(autoreset=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = config.KEY['brain']['model_name']
CONVO_HISTORY = {}
USER_NAME = "Admin"
LAST_USER_INPUT = ""
RECENT_QUESTIONS = {}
# V1.7: Track last system domain for "it" context resolution
# When user says "make it 40" after "set volume to 60", we know "it" = volume
LAST_SYSTEM_DOMAIN = None  # "volume", "brightness", etc.


def load_name_from_memory():
    """Load user's name from ChromaDB facts (single source of truth)."""
    global USER_NAME
    try:
        all_facts = seven_memory.user_facts.get()
        if all_facts and all_facts['documents']:
            for doc in all_facts['documents']:
                doc_lower = doc.lower()
                if "user's name is" in doc_lower or "user wants to be called" in doc_lower:
                    # Extract name from fact text
                    # "User's name is Mani" → "Mani"
                    if "name is" in doc_lower:
                        name = doc.split("is")[-1].strip().rstrip(".")
                    elif "called" in doc_lower:
                        name = doc.split("called")[-1].strip().rstrip(".")
                    else:
                        continue
                    if name and len(name) > 0:
                        USER_NAME = name
                        print(Fore.GREEN + f"[BRAIN] Loaded user name from memory: {USER_NAME}")
                        return
        print(Fore.YELLOW + "[BRAIN] No user name found in memory. Using default: Admin")
    except Exception as e:
        print(Fore.YELLOW + f"[BRAIN] Could not load name from memory: {e}")


def reset_session():
    """Clears session data when memory is wiped."""
    global RECENT_QUESTIONS, CONVO_HISTORY, USER_NAME
    RECENT_QUESTIONS = {}
    CONVO_HISTORY = {}
    USER_NAME = "Admin"


load_name_from_memory()

def _build_window_tag(clean_in, is_desktop_cmd, is_notarget_cmd, is_layout, put_pattern, is_switch, is_move_monitor, is_swap, is_window_close, is_transparent, is_solid, is_pin, is_unpin):
    """
    V1.6: Parse natural language into WINDOW tag params.
    Returns param string like 'action=snap target=chrome position=left'
    or None if parsing fails.
    """
    words = clean_in.split()

    # --- NO-TARGET COMMANDS (undo, list, etc) ---
    if is_notarget_cmd:
        if "undo" in clean_in or "put it back" in clean_in or "revert" in clean_in:
            return "action=undo"
        if ("what" in clean_in and "open" in clean_in) or "list windows" in clean_in or "show windows" in clean_in or "running" in clean_in:
            return "action=list"
        return None
    
    # --- DESKTOP COMMANDS (no target needed) ---
    if is_desktop_cmd:
        if "show desktop" in clean_in or "clear desktop" in clean_in:
            return "action=show_desktop"
        if "hide all" in clean_in or "minimize all" in clean_in or "minimize everything" in clean_in:
            return "action=minimize_all"
        if "show all" in clean_in or "restore all" in clean_in:
            return "action=show_desktop"  # Toggle
        return "action=show_desktop"
    

    # --- SWAP COMMAND ---
    if is_swap:
        # "swap chrome and notepad"
        noise = ["swap", "and", "with", "please", "can", "you", "the"]
        app_words = [w for w in clean_in.split() if w not in noise and len(w) > 1]
        if len(app_words) >= 2:
            targets = ",".join(app_words[:2])
            return f"action=swap targets={targets}"
        return None

    # --- WINDOW-LEVEL CLOSE ---
    if is_window_close:
        # "close this window" / "close the active window"
        if "this" in clean_in or "active" in clean_in or "the window" in clean_in:
            return "action=close_window target=this"
        return None
    
    # --- LAYOUT COMMANDS (multiple targets) ---
    if is_layout:
        # "put chrome and code side by side"
        # "split screen chrome and notepad"
        # "stack chrome and code"
        # "quad chrome code notepad explorer"
        
        # Determine mode
        if "stack" in clean_in:
            mode = "stack"
        elif "quad" in clean_in:
            mode = "quad"
        else:
            mode = "split"
        
        # Extract app names — everything that's not a layout keyword
        noise = ["put", "and", "side", "by", "split", "screen", "view",
                 "stack", "quad", "tile", "arrange", "on", "the", "in",
                 "with", "next", "to", "beside", "layout"]
        apps = [w for w in words if w not in noise and len(w) > 1]
        
        if len(apps) >= 2:
            targets = ",".join(apps)
            return f"action=layout mode={mode} targets={targets}"
        return None
    
    # --- PUT PATTERN: "put chrome on the left" ---
    if put_pattern:
        # Extract target: word(s) between "put" and "on"
        after_put = clean_in.split("put ", 1)[1] if "put " in clean_in else ""
        
        if " on " in after_put:
            target_part = after_put.split(" on ")[0].strip()
            position_part = after_put.split(" on ")[1].strip()
        else:
            return None
        
        # Parse position
        pos_map = {
            "the left": "left", "left": "left", "left side": "left",
            "the right": "right", "right": "right", "right side": "right",
            "top left": "top-left", "the top left": "top-left",
            "top right": "top-right", "the top right": "top-right",
            "bottom left": "bottom-left", "the bottom left": "bottom-left",
            "bottom right": "bottom-right", "the bottom right": "bottom-right",
            "top": "top", "the top": "top",
            "bottom": "bottom", "the bottom": "bottom",
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
    if is_move_monitor:
        # "move chrome to monitor 2" / "move chrome to second monitor"
        ordinals = {"second": "1", "2": "1", "third": "2", "3": "2",
                     "first": "0", "1": "0", "primary": "0"}
        
        # Extract target: between "move" and "to"
        after_move = clean_in.split("move ", 1)[1] if "move " in clean_in else ""
        if " to " in after_move:
            target = after_move.split(" to ")[0].strip()
            monitor_part = after_move.split(" to ")[1].strip()
        else:
            return None
        
        # Parse monitor number
        monitor_idx = "1"  # Default to second monitor
        for word, idx in ordinals.items():
            if word in monitor_part:
                monitor_idx = idx
                break
        
        if target:
            return f"action=move_monitor target={target} monitor={monitor_idx}"
        return None
    
    # --- SIMPLE VERB + TARGET ---
    # "minimize chrome", "can you maximize notepad", "please restore explorer"
    verb_map = {
        "minimize": "minimize",
        "maximise": "maximize",
        "maximize": "maximize",
        "restore": "restore",
        "center": "center",
        "centre": "center",
        "fullscreen": "fullscreen",
        "full screen": "fullscreen",
    }
    
    for verb, action in verb_map.items():
        if verb in clean_in:
            # Extract target: everything AFTER the verb
            verb_pos = clean_in.index(verb)
            target = clean_in[verb_pos + len(verb):].strip()
            if target:
                return f"action={action} target={target}"
            return None
    
    # --- SNAP COMMANDS ---
    # "snap chrome left", "can you snap notepad to the right"
    if "snap " in clean_in:
        snap_pos = clean_in.index("snap ")
        after_snap = clean_in[snap_pos + 5:].strip()
        # Try to split into target and position
        pos_words = ["left", "right", "top", "bottom",
                     "top-left", "top-right", "bottom-left", "bottom-right"]
        
        for pw in pos_words:
            if after_snap.endswith(pw):
                target = after_snap[:-(len(pw))].strip()
                target = target.rstrip(" to the").rstrip(" to").strip()
                if target:
                    return f"action=snap target={target} position={pw}"
        
        # No position found — default to left
        return f"action=snap target={after_snap} position=left"
    # --- PIN / ALWAYS ON TOP ---
    # "pin chrome", "keep chrome on top", "can you pin notepad"
    if is_pin:
        noise = ["pin", "keep", "on", "top", "always", "please", "can", 
                 "you", "the", "make", "set", "it"]
        target_words = [w for w in clean_in.split() if w not in noise and len(w) > 1]
        if target_words:
            target = " ".join(target_words)
            return f"action=pin target={target}"
        return None

    # "unpin chrome", "remove notepad from top"
    if is_unpin:
        noise = ["unpin", "remove", "from", "top", "not", "on", "please", 
                 "can", "you", "the", "make", "it"]
        target_words = [w for w in clean_in.split() if w not in noise and len(w) > 1]
        if target_words:
            target = " ".join(target_words)
            return f"action=unpin target={target}"
        return None

    # --- TRANSPARENCY ---
    # Supports:
    #   "make chrome transparent"          → default 80%
    #   "make chrome 50% transparent"      → exact 50%
    #   "make chrome a bit transparent"    → light 90%
    #   "make chrome very transparent"     → heavy 40%
    #   "make chrome more transparent"     → decrease current by 20%
    #   "make chrome less transparent"     → increase current by 20%
    #   "make chrome brighter"             → increase current by 20%
    #   "set chrome transparency to 60"    → exact 60%
    #   "keep 70% transparency on chrome"  → exact 70%
    if is_transparent:
        import re as _re
        
        # Step 1: Check for explicit percentage
        # Matches: "50%", "50 percent", "50 %", just "50" near "transparent"
        pct_match = _re.search(r'(\d+)\s*%?\s*(?:percent|transparent|transparency|opacity)?', clean_in)
        
        # Step 2: Check for relative words (more/less/bit/very)
        is_more = any(w in clean_in for w in ["more transparent", "more see through"])
        is_less = any(w in clean_in for w in ["less transparent", "brighter", 
                                               "less see through", "bit more visible",
                                               "more visible", "more opaque"])
        is_slight = any(w in clean_in for w in ["a bit", "a little", "slightly", 
                                                  "a touch", "just a bit"])
        is_very = any(w in clean_in for w in ["very", "really", "super", 
                                                "extremely", "heavily", "fully"])
        
        # Step 3: Determine opacity value
        if pct_match:
            # User gave explicit number
            pct = int(pct_match.group(1))
            # Clamp between 10% and 100%
            pct = max(10, min(100, pct))
            opacity = pct / 100.0
        elif is_more:
            # "more transparent" → relative decrease, handled by windows.py
            opacity = "more"
        elif is_less:
            # "less transparent" / "brighter" → relative increase
            opacity = "less"
        elif is_slight:
            # "a bit transparent" → barely noticeable (90%)
            opacity = 0.9
        elif is_very:
            # "very transparent" → heavily transparent (40%)
            opacity = 0.4
        else:
            # Default: noticeable but usable (80%)
            opacity = 0.8
        
        # Step 4: Extract target (remove all noise words including numbers)
        noise = ["make", "set", "transparent", "see", "through", "translucent",
                 "please", "can", "you", "the", "it", "a", "bit", "little",
                 "slightly", "very", "really", "super", "extremely", "heavily",
                 "more", "less", "much", "touch", "just", "keep", "put",
                 "percent", "opacity", "transparency", "to", "at", "on",
                 "brighter", "visible", "opaque", "fully"]
        # Also remove the percentage number from target
        words = clean_in.split()
        target_words = []
        for w in words:
            if w in noise or len(w) <= 1:
                continue
            # Skip if it's a number (percentage)
            if w.replace("%", "").isdigit():
                continue
            target_words.append(w)
        
        if target_words:
            target = " ".join(target_words)
            return f"action=transparent target={target} opacity={opacity}"
        return None

    # "make chrome solid", "make notepad opaque", "make chrome not transparent"
    # "make chrome normal", "make chrome back to normal"
    if is_solid:
        noise = ["make", "set", "solid", "opaque", "not", "transparent",
                 "please", "can", "you", "the", "it", "back", "normal",
                 "to", "fully", "completely", "100"]
        target_words = [w for w in clean_in.split() if w not in noise and len(w) > 1 
                        and not w.replace("%", "").isdigit()]
        if target_words:
            target = " ".join(target_words)
            return f"action=solid target={target}"
        return None

    # --- TRANSPARENCY ---
    if "transparent" in clean_in or "see through" in clean_in:
        noise = ["make", "set", "transparent", "see", "through", "please", "can", "you", "the"]
        target_words = [w for w in clean_in.split() if w not in noise and len(w) > 1]
        if target_words:
            target = " ".join(target_words)
            return f"action=transparent target={target} opacity=0.8"
        return None

    if "solid" in clean_in or "opaque" in clean_in or "not transparent" in clean_in:
        noise = ["make", "set", "solid", "opaque", "not", "transparent", "please", "can", "you", "the"]
        target_words = [w for w in clean_in.split() if w not in noise and len(w) > 1]
        if target_words:
            target = " ".join(target_words)
            return f"action=solid target={target}"
        return None
    
    return None

# =========================================================================
#   V1.7
# =========================================================================

def _build_system_tag(clean_in):
    """
    V1.7: Parse natural language into ###SYS: tag params.
    Uses keyword LOGIC instead of phrase matching.
    Returns param string like 'action=volume_up value=10' or None.
    """
    import re as _re
    
    words = clean_in.split()
    
    # Helper: extract number from input (whole word only, not substring)
    def _get_number():
        for w in words:
            cleaned = w.replace("%", "")
            if cleaned.isdigit():
                return cleaned
        return None
    
    global LAST_SYSTEM_DOMAIN
    
    # =========================================================================
    # VOLUME — detect "volume" or volume-related words anywhere
    # =========================================================================
    has_volume = any(w in words for w in ["volume", "sound", "audio"])
    
    # Standalone words (exact match — no other context needed)
    if clean_in == "mute":
        LAST_SYSTEM_DOMAIN = "volume"
        return "action=volume_mute"
    if clean_in == "unmute":
        LAST_SYSTEM_DOMAIN = "volume"
        return "action=volume_unmute"
    if clean_in in ["louder", "softer", "quieter"]:
        LAST_SYSTEM_DOMAIN = "volume"
        if clean_in == "louder":
            return "action=volume_up value=10"
        return "action=volume_down value=10"
    
    if has_volume or any(w in words for w in ["loud", "quiet"]):
        LAST_SYSTEM_DOMAIN = "volume"
        
        # Mute/unmute
        if "unmute" in clean_in:
            return "action=volume_unmute"
        if "mute" in clean_in:
            return "action=volume_mute"
        
        # Status check
        if any(w in words for w in ["what", "whats", "how", "check", "current", "level", "status"]):
            return "action=volume_get"
        
        num = _get_number()
        
        # Max/min (use whole word matching)
        if any(w in words for w in ["max", "maximum", "full", "highest"]):
            return "action=volume_set value=100"
        if any(w in words for w in ["min", "minimum", "lowest", "zero"]):
            return "action=volume_set value=0"
        
        # Set to specific value — if number exists with or without intent words
        if num:
            has_set_intent = any(w in words for w in ["set", "to", "at", "keep", "make", "put", "change"])
            # "volume 50" or "set volume to 50" or "volume to 50"
            if has_set_intent or len(words) <= 3:
                return f"action=volume_set value={num}"
        
        # Up/down direction
        is_up = any(w in words for w in ["up", "increase", "raise", "higher", "more", "louder", "crank", "bump", "boost"])
        is_down = any(w in words for w in ["down", "decrease", "lower", "reduce", "less", "quieter", "softer"])
        
        step = num if num else "10"
        if is_up:
            return f"action=volume_up value={step}"
        if is_down:
            return f"action=volume_down value={step}"
        
        # Last resort: just a number with volume
        if num:
            return f"action=volume_set value={num}"
    
    # =========================================================================
    # BRIGHTNESS — detect "bright", "dim", "light" (screen context)
    # =========================================================================
    has_brightness = any(w in words for w in ["brightness", "bright", "brighter", "brightest"])
    has_dim = any(w in words for w in ["dim", "dimmer", "dimming"])
    # "light" only counts if combined with screen context, not "night light" or "light mode"
    has_screen_light = ("screen" in clean_in and "light" in words and 
                        "night" not in clean_in and "mode" not in clean_in)
    
    # Standalone
    if clean_in in ["brighter", "dimmer", "dim"]:
        LAST_SYSTEM_DOMAIN = "brightness"
        if clean_in == "brighter":
            return "action=brightness_up value=10"
        return "action=brightness_down value=10"
    
    if has_brightness or has_dim or has_screen_light:
        LAST_SYSTEM_DOMAIN = "brightness"
        
        # Status check
        if any(w in words for w in ["what", "whats", "how", "check", "current", "level", "status"]):
            return "action=brightness_get"
        
        num = _get_number()
        
        # Max/min (whole word matching)
        if any(w in words for w in ["max", "maximum", "full", "highest", "brightest"]):
            return "action=brightness_set value=100"
        if any(w in words for w in ["min", "minimum", "lowest"]):
            return "action=brightness_set value=5"
        
        # Set to specific value
        if num:
            has_set_intent = any(w in words for w in ["set", "to", "at", "keep", "make", "put", "change"])
            if has_set_intent or len(words) <= 3:
                return f"action=brightness_set value={num}"
        
        # Up/down direction
        is_up = any(w in words for w in ["up", "increase", "raise", "higher", "more", "brighter"])
        is_down = any(w in words for w in ["down", "decrease", "lower", "reduce", "less", "dimmer", "darker", "dim"])
        
        step = num if num else "10"
        if is_up:
            return f"action=brightness_up value={step}"
        if is_down:
            return f"action=brightness_down value={step}"
        
        if num:
            return f"action=brightness_set value={num}"
    
    # =========================================================================
    # BATTERY — detect "battery" or "charge" or "plugged"
    # =========================================================================
    if any(w in words for w in ["battery", "charge", "plugged", "charging"]) or "power status" in clean_in:
        return "action=battery"
    
    # =========================================================================
    # WIFI — detect "wifi" or "wi-fi" or "internet" + context
    # =========================================================================
    has_wifi = any(w in words for w in ["wifi", "wi-fi"]) or (
                "internet" in clean_in and any(w in words for w in ["connect", "status", "on", "off"]))
    
    if has_wifi:
        if any(w in words for w in ["off", "disable", "disconnect", "kill", "stop"]):
            return "action=wifi_off"
        if any(w in words for w in ["on", "enable", "connect", "start"]):
            return "action=wifi_on"
        return "action=wifi_status"
    
    # =========================================================================
    # BLUETOOTH — detect "bluetooth"
    # =========================================================================
    if "bluetooth" in clean_in:
        if any(w in words for w in ["off", "disable", "disconnect", "kill", "stop"]):
            return "action=bluetooth_off"
        if any(w in words for w in ["on", "enable", "connect", "start"]):
            return "action=bluetooth_on"
        return "action=bluetooth_status"
    
    # =========================================================================
    # MEDIA — detect playback intent
    # =========================================================================
    # Guard: "open spotify" or "play a game" should NOT trigger media
    app_context = any(w in words for w in ["open", "launch", "game",
                                            "video", "youtube", "movie", "film"])
    
    if not app_context:
        # Next/skip — unambiguous
        if clean_in in ["next", "skip"]:
            return "action=media_next"
        if any(p in clean_in for p in ["next track", "next song", "skip song",
                                        "skip track", "skip this"]):
            return "action=media_next"
        
        # Previous
        if clean_in in ["previous", "prev"]:
            return "action=media_prev"
        if any(p in clean_in for p in ["previous track", "previous song", "prev track",
                                        "prev song", "last track", "last song",
                                        "go back a song"]):
            return "action=media_prev"
        
        # Stop (must have music/playing context)
        if any(p in clean_in for p in ["stop music", "stop playing", "stop the music",
                                        "stop playback", "stop the song"]):
            return "action=media_stop"
        
        # Play/pause — only if short or has music context
        has_music = any(w in words for w in ["music", "song", "track", "playback"])
        if clean_in in ["play", "pause", "resume", "unpause"]:
            return "action=media_play_pause"
        if has_music and any(w in words for w in ["play", "pause", "resume", "stop"]):
            if "stop" in words:
                return "action=media_stop"
            return "action=media_play_pause"
    
    # =========================================================================
    # DARK MODE — detect "dark mode" or "light mode"
    # =========================================================================
    if "dark mode" in clean_in or "dark theme" in clean_in:
        if any(w in words for w in ["off", "disable"]):
            return "action=dark_mode_off"
        return "action=dark_mode_on"
    
    if "light mode" in clean_in or "light theme" in clean_in:
        if any(w in words for w in ["off", "disable"]):
            return "action=dark_mode_on"
        return "action=dark_mode_off"
    
    if clean_in in ["go dark", "switch to dark"]:
        return "action=dark_mode_on"
    if clean_in in ["go light", "switch to light"]:
        return "action=dark_mode_off"
    
    # =========================================================================
    # NIGHT LIGHT — detect "night light" or "blue light"
    # =========================================================================
    if "night light" in clean_in or "blue light" in clean_in or "night mode" in clean_in:
        if any(w in words for w in ["off", "disable"]):
            return "action=night_light_off"
        return "action=night_light_on"
    
    # =========================================================================
    # DO NOT DISTURB — detect "disturb" or "dnd" or "focus assist"
    # =========================================================================
    if "disturb" in clean_in or "dnd" in words or "focus assist" in clean_in:
        if any(w in words for w in ["off", "disable"]):
            return "action=dnd_off"
        return "action=dnd_on"
    
    if any(p in clean_in for p in ["silence notifications", "mute notifications",
                                     "no notifications", "quiet mode"]):
        return "action=dnd_on"
    if any(p in clean_in for p in ["enable notifications", "turn on notifications",
                                     "unmute notifications"]):
        return "action=dnd_off"
    
    # =========================================================================
    # AIRPLANE MODE — detect "airplane" or "flight mode"
    # =========================================================================
    if "airplane" in clean_in or "flight mode" in clean_in:
        if any(w in words for w in ["off", "disable"]):
            return "action=airplane_off"
        return "action=airplane_on"
    
    return None


def think(prompt_text, speaker_id="default"):
    global CONVO_HISTORY, USER_NAME, LAST_USER_INPUT, RECENT_QUESTIONS

    # If we know who's speaking, use their name
    if speaker_id not in ("default", "unknown"):
        # Try to find this speaker's real name from memory
        speaker_name = speaker_id.title()  # Default: capitalize profile ID
        try:
            all_facts = seven_memory.user_facts.get(where={"user_id": speaker_id})
            if all_facts and all_facts['documents']:
                for doc in all_facts['documents']:
                    doc_lower = doc.lower()
                    if "name is" in doc_lower:
                        found_name = doc.split("is")[-1].strip().rstrip(".")
                        if found_name and len(found_name) > 0:
                            speaker_name = found_name
                            break
                    elif "called" in doc_lower:
                        found_name = doc.split("called")[-1].strip().rstrip(".")
                        if found_name and len(found_name) > 0:
                            speaker_name = found_name
                            break
        except:
            pass
    else:
        speaker_name = USER_NAME

    clean_in = prompt_text.lower().strip()
    clean_in = clean_in.replace("?", "").replace(".", "").replace("!", "").replace("'", "").replace(",", "")
    words = clean_in.split()

    # =========================================================================
    # LAYER 1: NAME SETTING (Must be absolute first)
    # =========================================================================
    # "My name is Mani" must save BEFORE any other check runs.
    # If we don't catch this first, "my name" triggers identity check instead.

    if "my name is" in clean_in:
        new_name = prompt_text.split("is")[-1].strip().rstrip(".")
        if speaker_id != "default" and speaker_id != "unknown":
            # Store name linked to this speaker's voice profile
            seven_memory.store_fact(f"Speaker {speaker_id}'s name is {new_name}", category="identity", user_id=speaker_id)
            speaker_name = new_name
        else:
            USER_NAME = new_name
            seven_memory.store_fact(f"User's name is {USER_NAME}", category="identity")
        return f"Understood. You are {new_name}."

       # =========================================================================
    # LAYER 2: REPETITION DETECTOR
    # =========================================================================

    # NEVER block commands — user might retry because first attempt failed
    first_word = words[0] if words else ""
    window_first_words = ["minimize", "maximise", "maximize", "restore", "snap",
                          "switch", "focus", "bring", "center", "centre", "put"]
    is_command = first_word in ["open", "close", "start", "kill", "launch"] + window_first_words
    is_greeting = first_word in ["hi", "hey", "hello", "bye", "goodbye", "good"]

    # Skip repetition for commands, greetings, AND requests
    is_request = False
    if first_word in ["sing", "open", "close"]:
        is_request = True
    
    speaker_questions = RECENT_QUESTIONS.get(speaker_id, [])
    # V1.4: Similar question detector (not just exact match)
    similar_groups = [
        ["introduce yourself", "tell me what you can do", "what can you do", 
         "what you can do", "what are your capabilities", "tell me about yourself",
         "what do you do", "list your capabilities"],
        ["whats your name", "who are you", "what should i call you", "tell me your name"],
        ["whats my name", "who am i", "do you know my name", "do you know me"],
        ["who created you", "who made you", "who built you", "who is your creator"],
    ]
    
    similar_detected = False
    for group in similar_groups:
        if any(g in clean_in for g in group):
            asked_similar = False
            for prev in speaker_questions:
                if any(g in prev for g in group):
                    asked_similar = True
                    break
            
            if asked_similar and not is_command and not is_greeting:
                similar_detected = True
                break

    if similar_detected:
        import random
        ack = random.choice([
            "You asked something similar just now.",
            "We just covered this.",
            "Similar question — but sure.",
            "You already asked that, but alright.",
        ])
        # Modify the prompt so LLM gives a DIFFERENT answer
        prompt_text = f"[The user asked a similar question before. Acknowledge briefly then answer differently than last time.] {prompt_text}"
        
    if clean_in in speaker_questions and not is_command and not is_greeting and not is_request:

        # Identity questions have FIXED answers — no need to check memory
        # These answers NEVER change, so always block on repeat
        if "your name" in clean_in or "who are you" in clean_in:
            
            responses = [
                "Seven. Same as before.",
                "Still Seven.",
                "I'm Seven. That hasn't changed.",
                "Seven — same answer as last time.",
            ]
            return random.choice(responses)
        if "my name" in clean_in or "who am i" in clean_in:
            if speaker_id not in ("default", "unknown") and speaker_name == speaker_id.title():
                return "You haven't told me your name yet."
            
            responses = [
                f"You're {speaker_name}.",
                f"Still {speaker_name}.",
                f"{speaker_name}, same as before.",
                f"{speaker_name} — hasn't changed.",
            ]
            return random.choice(responses)
        if "what are you" in clean_in:
            return "Still Seven, your personal AI assistant."
        if "call you" in clean_in:
            return "Seven. Same as always."
        if "created you" in clean_in or "made you" in clean_in or "who made" in clean_in:
            creator = config.KEY['identity']['creator']
            
            responses = [
                f"{creator}. Same answer.",
                f"Still {creator}.",
                f"{creator} built me. That hasn't changed.",
                f"{creator} — my creator.",
            ]
            return random.choice(responses)

        # For NON-identity questions, check if new memories exist
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        fresh_memory = seven_memory.search(prompt_text, user_id=search_uid)
        if fresh_memory:
            # New info available — don't block, let LLM answer with memory
            memory_context = fresh_memory
            print(Fore.MAGENTA + "[MEMORY] Found NEW memories for repeated question!")
            print(Fore.MAGENTA + memory_context)
        else:
            repeat_count = speaker_questions.count(clean_in)

            if repeat_count >= 2:
                return "You've asked me this multiple times now. My answer hasn't changed."

            return "You just asked me that. Same answer."

    if not is_command and not is_greeting:
        if speaker_id not in RECENT_QUESTIONS:
            RECENT_QUESTIONS[speaker_id] = []
        RECENT_QUESTIONS[speaker_id].append(clean_in)
        if len(RECENT_QUESTIONS[speaker_id]) > 10:
            RECENT_QUESTIONS[speaker_id].pop(0)

    # =========================================================================
    # LAYER 3: IDENTITY OVERRIDES (Smart Keyword Detection)
    # =========================================================================
    # Only reaches here on FIRST time asking. Repeats caught above.
    # Uses keyword detection — not exact matching.
    # Skips to LLM if question is ABOUT names but not asking directly.

    # --- USER ASKING SEVEN'S NAME ---
    # "What's your name?" / "Tell me your name" / "Who are you?"
    # BUT NOT: "How many times did I ask your name?" → LLM handles
    if "your name" in clean_in:
        if len(words) <= 6 and "how" not in clean_in and "did" not in clean_in:
            return "I am Seven. You can call me Seven."

    if clean_in == "who are you":
        return "I am Seven, your personal AI assistant."

    # --- USER ASKING THEIR NAME ---
    # "What's my name?" / "Do you know my name?"
    # BUT NOT: "What is my friend's name?" / "How many times did I ask my name?"
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
            if speaker_id not in ("default", "unknown") and speaker_name == speaker_id.title():
                return "You haven't told me your name yet."
            return f"You are {speaker_name}."
        
    # --- GREETINGS ---
    greeting_words = ["hi", "hello", "hey", "hi seven", "hello seven", "hey seven",
                      "good morning", "good afternoon", "good evening"]
    if clean_in in greeting_words:
        import random
        greetings = [
            f"Hey {speaker_name}! What can I do for you?",
            f"Hey {speaker_name}! How can I help?",
            f"{speaker_name}! What's on your mind?",
            f"Hey! What do you need, {speaker_name}?",
        ]
        return random.choice(greetings)
        
    # --- FAREWELLS ---
    farewell_words = ["bye", "goodbye", "bye seven", "goodbye seven", "see you",
                      "see ya", "later", "good night", "goodnight"]
    if clean_in in farewell_words:
        return f"Later, {speaker_name}."

    # --- WHAT ARE YOU ---
    if clean_in == "what are you":
        return "I am Seven, your personal AI assistant."
    

    # --- WHAT SHOULD I CALL YOU ---
    if "call you" in clean_in or "should i call" in clean_in:
        return "You can call me Seven."
    
    # --- CAPABILITIES (V1.6.1) ---
    # When user asks what Seven can do, inject capability facts into LLM context
    # so Seven answers naturally — NOT hardcoded responses
    capability_triggers = ["what can you do", "what you can do", "your capabilities",
                           "what are you capable", "what do you do", "capable of",
                           "tell me what you can", "what are your abilities",
                           "list your capabilities", "what are your features"]
    is_capability_q = any(t in clean_in for t in capability_triggers)
    
    if is_capability_q:
        # Build a facts block based on what domain they're asking about
        is_window_q = any(w in clean_in for w in ["window", "windows", "screen", "display"])
        is_app_q = any(w in clean_in for w in ["app", "apps", "application", "program"])
        is_system_q = any(w in clean_in for w in ["system", "control", "volume", "brightness",
                                                    "battery", "wifi", "bluetooth", "media",
                                                    "settings control"])
        
        # Capability facts — Seven's actual knowledge about itself
        # These get injected into the prompt so the LLM reasons from them
        cap_facts = []
        
        if is_window_q:
            # Only window facts
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
            # Only system facts
            cap_facts = [
                "I control system volume: up, down, mute, unmute, set to specific percentage.",
                "I adjust screen brightness: up, down, set to specific percentage.",
                "I check battery status: percentage, plugged in, time remaining.",
                "I check and toggle WiFi on or off, and show current network.",
                "I toggle Bluetooth on or off and check its status.",
                "I control media playback: play, pause, next track, previous track, stop.",
                "I switch between dark mode and light mode.",
                "I toggle night light and blue light filter.",
                "I toggle do not disturb and focus assist.",
                "I toggle airplane mode.",
            ]
        elif is_app_q:
            # Only app facts
            cap_facts = [
                "I open any app by name.",
                "I close one instance or all instances of an app.",
                "I know aliases: browser means chrome, files means explorer, music means spotify.",
                "I log every command I execute.",
            ]
        else:
            # Everything
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
            ]
        
        # Inject facts into the prompt — LLM will phrase the answer naturally
        facts_block = "=== YOUR CAPABILITIES (answer from these) ===\n"
        for fact in cap_facts:
            facts_block += f"- {fact}\n"
        facts_block += "=== END CAPABILITIES ===\n"
        facts_block += "Summarize these naturally. Be concise. Don't list them as bullet points."
        
        # Modify the prompt so the LLM sees these facts
        prompt_text = f"{facts_block}\n\nUser asked: {prompt_text}"
        
        # Modify the prompt so the LLM sees these facts
        prompt_text = f"{facts_block}\n\nUser asked: {prompt_text}"
    
    # --- APP HISTORY ---
    if ("what" in clean_in or "which" in clean_in) and ("app" in clean_in or "open" in clean_in) and ("today" in clean_in or "did i" in clean_in or "did you" in clean_in):
        from memory.command_log import command_log
        stats = command_log.get_stats()
        recent = stats.get('recent', [])
        if recent:
            app_list = ", ".join([f"{r['action']} {r['target']}" for r in recent[:5]])
            return f"Recent commands: {app_list}."
        else:
            return "No apps opened in this session yet."
    

     # --- USER TEACHING A FACT (acknowledge it, don't parrot it back) ---
    # "I love cricket" should get "Nice, I'll remember that." not "You play cricket."
    # teaching_triggers = ["i love", "i like", "i prefer", "my favorite", "my favourite",
    #                      "i work", "i study", "i am a", "i am an", "remember that"]
    # if any(trigger in clean_in for trigger in teaching_triggers):
    #     seven_memory.extract_and_store_facts(prompt_text)
    #     return "Noted. I'll remember that."

    
    # =========================================================================
    # LAYER 4: MOOD ANALYSIS (NEW IN V1.1.1)
    # =========================================================================
    mood_engine.analyze_input(prompt_text)
    mood_modifier = mood_engine.get_mood_prompt_modifier()

    # =========================================================================
    # LAYER 4.5: COMMAND DETECTION (Python-first, no LLM needed)
    # =========================================================================
    # If the first word is a command verb, generate tags directly in Python.
    # This is FASTER and more RELIABLE than asking the LLM to generate tags.
    
    # --- WINDOW COMMANDS (V1.6) ---
    # Detect window manipulation commands BEFORE app open/close.
    # "minimize chrome", "snap notepad left", "put chrome on the left"
    # "switch to chrome", "bring up notepad", "show desktop", "hide all windows"
    
    # Core window verbs — single words that appear at/near start
    window_verbs = ["minimize", "maximise", "maximize", "restore", "snap",
                    "switch to", "focus", "bring up", "center", "centre",
                    "pin", "unpin", "fullscreen", "full screen", "swap"]
    
    # "put X on the left/right" pattern
    put_pattern = "put " in clean_in and any(p in clean_in for p in 
                  ["on the left", "on the right", "on left", "on right",
                   "top left", "top right", "bottom left", "bottom right"])
    
    # "X and Y side by side" / "side by side X and Y"
    layout_triggers = ["side by side", "split screen", "split view",
                       "stack", "quad", "tile", "arrange"]
    is_layout = any(t in clean_in for t in layout_triggers)
    
    # "hide all windows" / "show desktop" / "minimize all" / "minimize everything"
    is_desktop_cmd = False
    # Desktop + no-target commands
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
    if clean_in in desktop_phrases:
        is_desktop_cmd = True
    is_notarget_cmd = clean_in in notarget_phrases or any(p in clean_in for p in notarget_phrases)
    
    # "switch to X" / "bring up X" / "go to X" / "focus X"
    # Also catches: "hey switch to chrome", "can you switch to chrome"
    switch_verbs = ["switch to", "bring up", "go to", "focus on", "focus",
                    "show me", "pull up", "jump to", "open up"]
    is_switch = any(sv in clean_in for sv in switch_verbs)
    
    # "move X to monitor 2" / "move X to second monitor"
    is_move_monitor = ("move" in clean_in and "monitor" in clean_in)
    # "swap chrome and notepad"
    is_swap = "swap" in clean_in and ("and" in clean_in or "," in clean_in)
    
    # "close this window" / "close the window" (window-level close, not process kill)
    is_window_close = ("close this" in clean_in or "close the window" in clean_in 
                       or "close active" in clean_in)
    
    # "make chrome transparent" / "make chrome see through"
    # Detects "transparent" or "see through" anywhere regardless of word order
    is_transparent = ("transparent" in clean_in or "see through" in clean_in 
                      or "translucent" in clean_in)
    
    # "make chrome solid" / "make chrome opaque" / "make chrome not transparent"
    is_solid = (("solid" in clean_in or "opaque" in clean_in) 
                and "not transparent" not in clean_in) or "not transparent" in clean_in
    # Fix: "not transparent" = make solid, "solid" = make solid, "opaque" = make solid
    is_solid = ("solid" in clean_in or "opaque" in clean_in or "not transparent" in clean_in)
    
    # "pin chrome" / "keep chrome on top" / "always on top"
    is_pin = ("pin " in clean_in or "keep" in clean_in and "on top" in clean_in 
              or "always on top" in clean_in)
    
    # "unpin chrome" / "remove from top"
    is_unpin = ("unpin" in clean_in or "remove from top" in clean_in 
                or "not on top" in clean_in)
    
    # --- SYSTEM COMMANDS (V1.7) ---
    # Detect system control commands BEFORE window/app commands.
    # These are Python-first — bypass LLM entirely.
    
    global LAST_SYSTEM_DOMAIN
    
    import re as _re_mod
    def _re_check_num(text):
        return bool(_re_mod.search(r'\d+', text))
    
    # All system trigger words (used for fast pre-check)
    SYSTEM_TRIGGER_WORDS = [
        "volume", "mute", "unmute", "louder", "quieter", "softer",
        "brightness", "brighter", "dimmer", "dim",
        "battery", "charging", "plugged",
        "wifi", "bluetooth",
        "play", "pause", "skip", "next track", "next song", "previous track",
        "previous song", "stop music", "stop playing", "resume music",
        "dark mode", "light mode", "dark theme", "light theme",
        "night light", "blue light", "night mode",
        "do not disturb", "dnd", "focus assist",
        "airplane mode", "flight mode"
    ]
    
    # Check for system trigger words
    # But guard against false positives: "play spotify" should NOT be media control
    _has_system_trigger = any(t in clean_in for t in SYSTEM_TRIGGER_WORDS)
    
    # Guard: if sentence contains app verbs + app names, it's NOT a system command
    _app_verbs_present = first_word in ["open", "close", "start", "kill", "launch"]
    
    # Also trigger if user says generic "it/that" + number and we have a recent system domain
    _has_context_ref = (LAST_SYSTEM_DOMAIN is not None and (
                        (any(w in clean_in for w in ["it", "that", "this"]) and _re_check_num(clean_in)) or
                        (clean_in in ["more", "less", "higher", "lower", "increase", "decrease"])
                        ))
    
    is_system_cmd = (_has_system_trigger and not _app_verbs_present) or _has_context_ref
    
    if is_system_cmd:
        sys_tag = _build_system_tag(clean_in)
        if sys_tag:
            is_command = True
            
            # V1.7: Track domain for "it" context resolution
            _parts_check = {}
            for _pc in sys_tag.split():
                if "=" in _pc:
                    _pk, _pv = _pc.split("=", 1)
                    _parts_check[_pk] = _pv
            _sys_action = _parts_check.get("action", "")
            if "volume" in _sys_action:
                LAST_SYSTEM_DOMAIN = "volume"
            elif "brightness" in _sys_action:
                LAST_SYSTEM_DOMAIN = "brightness"

            
            import random as _rand
            
            # Parse tag for speech generation
            _parts = {}
            for _p in sys_tag.split():
                if "=" in _p:
                    _k, _v = _p.split("=", 1)
                    _parts[_k] = _v
            
            _action = _parts.get("action", "")
            _value = _parts.get("value", "")
            
            # Context-aware speech
            if _action == "volume_up":
                speech = _rand.choice(["Turning it up.", "Louder.", "Volume up."])
            elif _action == "volume_down":
                speech = _rand.choice(["Turning it down.", "Quieter.", "Volume down."])
            elif _action == "volume_set":
                speech = f"Setting volume to {_value}%."
            elif _action == "volume_mute":
                speech = _rand.choice(["Muted.", "Going silent.", "Sound off."])
            elif _action == "volume_unmute":
                speech = _rand.choice(["Unmuted.", "Sound on.", "You're live."])
            elif _action == "volume_get":
                speech = ""  # Result will be spoken from returned data
            elif _action == "brightness_up":
                speech = _rand.choice(["Brightening up.", "More brightness.", "Screen brighter."])
            elif _action == "brightness_down":
                speech = _rand.choice(["Dimming.", "Less brightness.", "Screen dimmer."])
            elif _action == "brightness_set":
                speech = f"Brightness to {_value}%."
            elif _action == "brightness_get":
                speech = ""
            elif _action == "battery":
                speech = ""  # Result spoken from data
            elif _action.startswith("wifi"):
                if "on" in _action:
                    speech = "Enabling WiFi."
                elif "off" in _action:
                    speech = "Disabling WiFi."
                else:
                    speech = ""  # Status — result spoken
            elif _action.startswith("bluetooth"):
                if "on" in _action:
                    speech = "Enabling Bluetooth."
                elif "off" in _action:
                    speech = "Disabling Bluetooth."
                else:
                    speech = ""
            elif _action == "media_play_pause":
                speech = _rand.choice(["Play pause.", "Toggled.", ""])
            elif _action == "media_next":
                speech = _rand.choice(["Next track.", "Skipping.", "Next."])
            elif _action == "media_prev":
                speech = _rand.choice(["Previous track.", "Going back.", "Previous."])
            elif _action == "media_stop":
                speech = "Stopping playback."
            elif _action == "dark_mode_on":
                speech = _rand.choice(["Going dark.", "Dark mode.", "Switching to dark."])
            elif _action == "dark_mode_off":
                speech = _rand.choice(["Going light.", "Light mode.", "Switching to light."])
            elif _action == "night_light_on":
                speech = _rand.choice(["Night light on.", "Easy on the eyes.", "Warming the screen."])
            elif _action == "night_light_off":
                speech = "Night light off."
            elif _action == "dnd_on":
                speech = _rand.choice(["Do not disturb.", "Going quiet.", "Notifications silenced."])
            elif _action == "dnd_off":
                speech = "Notifications back on."
            elif _action == "airplane_on":
                speech = _rand.choice(["Airplane mode on.", "Going offline.", "All radios off."])
            elif _action == "airplane_off":
                speech = _rand.choice(["Airplane mode off.", "Back online.", "Radios on."])
            else:
                speech = "On it."
            
            if speech:
                return f"{speech} ###SYS: {sys_tag}"
            else:
                return f"###SYS: {sys_tag}"
    
    # Check if a window verb appears ANYWHERE in the sentence
    # "can you minimize chrome" → detects "minimize"
    # "please snap notepad left" → detects "snap"
    is_window_verb = any(wv in clean_in for wv in window_verbs)

    # Update is_command to include all window detections
    # Combine all window-related detections
    is_any_window = (is_desktop_cmd or is_notarget_cmd or is_layout or put_pattern 
                     or is_window_verb or is_switch or is_move_monitor or is_swap 
                     or is_window_close or is_transparent or is_solid or is_pin or is_unpin)
    
    # Update is_command so memory/LLM layers skip this
    if is_any_window:
        is_command = True

    if is_any_window:

        tag_params = _build_window_tag(clean_in, is_desktop_cmd, is_notarget_cmd,
                                        is_layout, put_pattern, is_switch, 
                                        is_move_monitor, is_swap, is_window_close,
                                        is_transparent, is_solid, is_pin, is_unpin)
        if tag_params:
            import random as _rand
            
            # --- BUILD CONTEXT-AWARE SPEECH ---
            # Jarvis doesn't say "On it." — he tells you WHAT he's doing
            # Parse the tag to understand the action
            _parts = {}
            for _p in tag_params.split():
                if "=" in _p:
                    _k, _v = _p.split("=", 1)
                    _parts[_k] = _v
            
            _action = _parts.get("action", "")
            _target = _parts.get("target", "").replace(",", " and ")
            _position = _parts.get("position", "")
            _mode = _parts.get("mode", "")
            
            # Generate natural speech based on what's happening
            if _action == "focus":
                speech = _rand.choice([
                    f"Switching to {_target}.",
                    f"Bringing up {_target}.",
                    f"{_target}, coming up.",
                ])
            elif _action == "minimize":
                if _target in ["this", "current", "active"]:
                    speech = "Minimizing this window."
                else:
                    speech = _rand.choice([
                        f"Minimizing {_target}.",
                        f"Putting {_target} away.",
                        f"{_target}, out of sight.",
                    ])
            elif _action == "maximize":
                speech = _rand.choice([
                    f"Maximizing {_target}.",
                    f"Full size on {_target}.",
                    f"{_target}, going big.",
                ])
            elif _action == "restore":
                speech = _rand.choice([
                    f"Restoring {_target}.",
                    f"Bringing {_target} back.",
                ])
            elif _action == "snap":
                speech = _rand.choice([
                    f"Snapping {_target} to the {_position}.",
                    f"{_target}, {_position} side.",
                    f"Putting {_target} on the {_position}.",
                ])
            elif _action == "center":
                speech = f"Centering {_target}."
            elif _action == "layout":
                if _mode == "split":
                    speech = f"Putting {_target} side by side."
                elif _mode == "stack":
                    speech = f"Stacking {_target}."
                elif _mode == "quad":
                    speech = f"Four corners, {_target}."
                else:
                    speech = f"Arranging {_target}."
            elif _action == "minimize_all":
                speech = _rand.choice([
                    "Clearing the deck.",
                    "Everything down.",
                    "Desktop, clear.",
                ])
            elif _action == "show_desktop":
                speech = _rand.choice([
                    "Showing desktop.",
                    "All clear.",
                    "Desktop.",
                ])
            elif _action == "swap":
                speech = _rand.choice([
                    f"Swapping {_target}.",
                    f"{_target}, switching places.",
                ])
            elif _action == "pin":
                speech = _rand.choice([
                    f"Pinning {_target} on top.",
                    f"{_target} stays on top now.",
                ])
            elif _action == "unpin":
                speech = _rand.choice([
                    f"Unpinning {_target}.",
                    f"{_target}, back to normal.",
                ])
            elif _action == "fullscreen":
                speech = _rand.choice([
                    f"Fullscreen on {_target}.",
                    f"{_target}, going fullscreen.",
                ])
            elif _action == "transparent":
                _opacity = _parts.get("opacity", "0.8")
                # Build context-aware speech based on opacity type
                if _opacity == "more":
                    speech = _rand.choice([
                        f"Making {_target} more transparent.",
                        f"{_target}, a bit more see-through.",
                    ])
                elif _opacity == "less":
                    speech = _rand.choice([
                        f"Making {_target} less transparent.",
                        f"Brightening {_target} up.",
                        f"{_target}, more visible now.",
                    ])
                else:
                    try:
                        pct = int(float(_opacity) * 100)
                        if pct >= 90:
                            speech = f"Making {_target} slightly transparent."
                        elif pct <= 40:
                            speech = f"Making {_target} very transparent."
                        else:
                            speech = f"Setting {_target} to {pct}% opacity."
                    except:
                        speech = f"Making {_target} transparent."
            elif _action == "solid":
                speech = _rand.choice([
                    f"Making {_target} solid again.",
                    f"{_target}, back to full opacity.",
                ])
            elif _action == "close_window":
                speech = "Closing this window."
            elif _action == "undo":
                speech = _rand.choice([
                    "Undoing that.",
                    "Putting it back.",
                    "Reverting.",
                ])
            elif _action == "list":
                # List action returns data — speech comes from the result
                speech = ""
            else:
                speech = "On it."
            
            # Return speech + tag (if no speech, just the tag)
            if speech:
                return f"{speech} ###WINDOW: {tag_params}"
            else:
                return f"###WINDOW: {tag_params}"

    if first_word in ["open", "close", "start", "kill", "launch"]:
        command_verb = first_word
        remaining = clean_in
        
        for verb in ["open", "close", "start", "kill", "launch"]:
            if remaining.startswith(verb):
                remaining = remaining[len(verb):].strip()
                break
        
        if command_verb in ["open", "start", "launch"]:
            tag = "OPEN"
        elif command_verb in ["close", "kill"]:
            tag = "CLOSE"
        else:
            tag = "OPEN"
        
        # V1.5: Detect "all" modifier for close commands
        close_all = False
        if tag == "CLOSE" and remaining.startswith("all "):
            close_all = True
            remaining = remaining[4:].strip()
        
        if remaining:
            apps = []
            if " and " in remaining:
                apps = [a.strip() for a in remaining.split(" and ") if a.strip()]
            elif "," in remaining:
                apps = [a.strip() for a in remaining.split(",") if a.strip()]
            else:
                apps = [remaining.strip()]
            
            if close_all:
                tags = " ".join([f"###{tag}: ALL_{app}" for app in apps])
            else:
                tags = " ".join([f"###{tag}: {app}" for app in apps])
            
            import random as _rand
            # Natural speech before command
            app_list = ", ".join(apps)
            if tag == "OPEN":
                speech = _rand.choice([
                    f"Opening {app_list}.",
                    f"On it. {app_list} coming up.",
                    f"{app_list}, coming right up.",
                    f"Launching {app_list}.",
                ])
            else:
                if close_all:
                    speech = _rand.choice([
                        f"Closing all {app_list}.",
                        f"Shutting down every {app_list}.",
                        f"Killing all {app_list} instances.",
                    ])
                else:
                    speech = _rand.choice([
                        f"Closing {app_list}.",
                        f"Shutting down {app_list}.",
                        f"Done with {app_list}.",
                    ])
            return f"{speech} {tags}"
    

    # =========================================================================
    # LAYER 5: MEMORY SEARCH (Questions/Chat only — not commands)
    # =========================================================================

    memory_context = ""

    # Skip memory for commands, greetings, and farewells
    is_greeting = first_word in ["hi", "hey", "hello", "bye", "goodbye"]

    if "VISUAL_REPORT:" not in prompt_text and not is_command and not is_greeting:
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        memory_context = seven_memory.search(prompt_text, user_id=search_uid)

        if memory_context:
            print(Fore.MAGENTA + "[MEMORY] Found relevant memories!")
            print(Fore.MAGENTA + memory_context)

            
    # =========================================================================
    # LAYER 5.5: WEB SEARCH (Live Knowledge — V1.4)
    # =========================================================================
    # Checks if the query needs live internet data.
    # If yes, searches DuckDuckGo and injects results into LLM context.
    # Runs AFTER memory search — memory takes priority over web.
    
    web_context = ""
    web_searched = False
    
    if not is_command and not is_greeting and "VISUAL_REPORT:" not in prompt_text:
        from web.classifier import needs_web_search
        from web.core import web_search, web_news
        
        should_search, search_query = needs_web_search(prompt_text)
        
        if should_search and search_query:
            print(Fore.CYAN + f"[BRAIN] Web search triggered for: '{search_query}'")
            
            # Check if it's a news query
            news_words = ["news", "latest", "happened", "breaking", "update"]
            is_news = any(w in clean_in for w in news_words)
            
            if is_news:
                web_context = web_news(search_query)
            else:
                web_context = web_search(search_query)
            
            if web_context:
                web_searched = True
                print(Fore.GREEN + "[BRAIN] Web results injected into context.")
            else:
                print(Fore.YELLOW + "[BRAIN] Web search returned no results.")

    # =========================================================================
    # LAYER 6: NO-MEMORY QUESTION HANDLER
    # =========================================================================
    # Only catches questions about the USER PERSONALLY when no memories exist.
    # "What sport do I play?" → personal question → needs memory
    # "Tell me a joke" → NOT a personal question → let LLM handle
    
    personal_question_words = ["my", "about me", "do i", "did i", "am i",
                               "i like", "i love", "i play", "i work", "i study"]
    is_personal_question = any(w in clean_in for w in personal_question_words)
    
    question_starts = ["what", "which", "who", "when", "where", "how", "do you know"]
    is_question = any(clean_in.startswith(w) for w in question_starts)
    
    if is_question and is_personal_question and not memory_context and not is_command:
        return "You haven't told me that yet."

    # =========================================================================
    # LAYER 7: FACT EXTRACTION (Meaningful input only — not commands)
    # =========================================================================

    if "VISUAL_REPORT:" not in prompt_text and not is_command and not is_greeting:
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        seven_memory.extract_and_store_facts(prompt_text, user_id=search_uid)

    # =========================================================================
    # LAYER 8: LLM INFERENCE
    # =========================================================================

    if "VISUAL_REPORT:" not in prompt_text:
        if speaker_id not in CONVO_HISTORY:
            CONVO_HISTORY[speaker_id] = []
        CONVO_HISTORY[speaker_id].append(f"User: {prompt_text}")

    if len(CONVO_HISTORY.get(speaker_id, [])) > 4:
        CONVO_HISTORY[speaker_id] = CONVO_HISTORY[speaker_id][-4:]

    system_prompt = (
        f"You are {config.KEY['identity']['name']}, created by {config.KEY['identity']['creator']}. "
        f"You are currently talking to: {speaker_name}. "
        "You talk like JARVIS from Iron Man — sharp, confident, slightly witty, efficient. "
        "You dont waste words. You get to the point. You have personality but you dont overdo it. "
        "You NEVER sound like a customer service bot. No 'How can I help you today' or 'Im happy to assist'. "
        "Think dry humor, quiet competence, like a brilliant butler who knows everything. "
        f"{mood_modifier} "

        "RULES: "
        "1. Keep responses to 1-2 sentences MAXIMUM. Be extremely concise. No exceptions. "
        "   Even with web search results, summarize in ONE sentence. "
        "   Example: 'Bitcoin is currently at $69,726 USD.' — DONE. No extra details. "
        "   If the answer is one word, say one word. "
        "   'What is my name?' → 'Rahul.' NOT a paragraph about it. "
        "2. NEVER ask follow-up questions. "
        "2b. NEVER repeat the same response twice. If asked similar questions, vary your phrasing and focus on different aspects. "
        "3. Talk like a HUMAN, not a machine. "
        "   BAD: 'Functioning within optimal parameters' or 'memory banks'. "
        "   GOOD: 'Doing good.' or 'I remember you mentioning that.' "
        "4. NEVER mention programming, parameters, banks, systems, or protocols. "
        "5. NEVER say 'Doing good' at the end of responses. "
        "5b. NEVER start responses with 'Nice to chat', 'Great to chat', 'Nice to see you', 'Happy to help', 'Im happy to'. "
        "   Just answer directly. Start with the answer, not pleasantries. "
        "   BAD: 'Nice to chat with Mani! I'm Seven...' "
        "   GOOD: 'I'm Seven, built by Team Seven.' "
        f"6. Facts about your creator: "
        f"   - Your creator is {config.KEY['identity']['creator']}. "
        f"   - {config.KEY['identity']['creator']} is the person/team who designed and built you. "
        f"   - You are Project Seven, built by {config.KEY['identity']['creator']}. "
        f"   - When asked about your creator, answer naturally using these facts. "
        f"   - Never say the exact same sentence twice about your creator. Vary your phrasing. "
        f"   You are currently speaking with {speaker_name}. Use their name naturally. "
        "7. When user asks 'can you open apps', say 'Yes, I can.' Do NOT output any tags. "
        "8. When user asks 'do you know me' and NO memories exist, say 'Not yet, but I am learning.' "
        "9. When user asks 'will you remember', say 'Everything we talk about stays with me.' "
        "10. You know these facts about YOURSELF: "
        "   - Your name is Seven. "
        f"   - You were created by {config.KEY['identity']['creator']}. "
        "   - You run 100 percent locally on the users PC. "
        "   - All data is stored locally. Nothing is sent to any cloud or server. "
        "   - Your capabilities: open apps, close apps, long-term memory, web search for live data, voice recognition, interruptible speech. "
        "   - You have access to DuckDuckGo for live prices, weather, news, and trending topics. "
        "   - You know which of your capabilities you used to answer any question. "
        "   - When describing your capabilities, speak naturally. NEVER output command tags. "
        "   - When asked the same question twice, give a DIFFERENT response. Vary your words every time. "
        "11. When asked about your storage or privacy, explain you are fully local. "
        "12. For general knowledge questions (capital of France, science, math), answer directly and confidently. "
        "13. ONLY say 'You havent told me that' for questions about the USER PERSONALLY. "

        
        # "   - You can open apps, close apps, remember conversations, search the web, and chat. "
        # "   - When you search the web, you use DuckDuckGo. You can find live prices, weather, news, and more. "
        #"   - When asked how you searched, explain: 'I searched DuckDuckGo for live data.' "


        "WEB SEARCH: "
        "1. If WEB SEARCH RESULTS section exists below, use it to answer accurately. "
        "2. Summarize web results naturally — do NOT list them as bullet points. "
        "3. If WEB SEARCH RESULTS section exists AND has data, mention that you looked it up. Example: 'I looked it up — ...' "
        "4. If NO web results section exists, NEVER say 'I looked it up'. Answer from your own knowledge and say 'I couldn't verify this online right now.' "
        "5. If web results don't fully answer the question, say what you found. "
        "6. NEVER make up real-time data like prices, scores, or weather. If you don't have live data, say 'I couldn't get live data right now.' "

        "MEMORY: "
        "1. If RECALLED MEMORIES section exists below, the answer IS in there. Use it. "
        "2. NEVER ignore recalled memories. State the fact clearly. "
        "3. NEVER invent facts about the USER. If no memories exist about the USER, say so. "
        "4. NEVER say 'football' if memory says 'chess'. READ the memory carefully. "

        "COMMANDS: "
        "ONLY output ###OPEN or ###CLOSE when users FIRST word is Open, Close, Start, Kill, Launch. "
        "'Open X' → '###OPEN: X' — nothing else. "
        "'Open X and Y' → '###OPEN: X ###OPEN: Y' — nothing else. "
        "'Close X' → '###CLOSE: X' — nothing else. "
        "'Close X and Y' → '###CLOSE: X ###CLOSE: Y' — nothing else. "
        "If first word is NOT a command verb, answer normally. NEVER output tags. "
        "'Can you open apps' → first word is 'can' → answer normally, no tags. "

        "TAGS: ###OPEN: [App] | ###CLOSE: [App] | ###LOOK"
    )

    full_prompt = system_prompt + "\n\n"

    if web_context:
        full_prompt += web_context + "\n\n"

    if memory_context:
        full_prompt += memory_context + "\n\n"

    speaker_history = CONVO_HISTORY.get(speaker_id, [])
    full_prompt += "LOG:\n" + "\n".join(speaker_history) + "\nSeven:"

    # V1.4: Smart response length based on question type
    # Short answers: greetings, yes/no, prices, names
    # Long answers: explanations, lists, stories, capabilities
    long_triggers = ["tell me", "explain", "describe", "what can you", 
                     "list", "how does", "how do", "why", "story",
                     "detail", "everything", "all about", "continue",
                     "go on", "more about", "your capabilities",
                     "what are you capable", "what do you do",
                     "what you can do", "capable of"]
    needs_long = any(t in clean_in for t in long_triggers)
    
    if needs_long:
        response_length = 150
    elif web_searched:
        response_length = 80
    else:
        response_length = 60

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": response_length,
            "repeat_penalty": 1.3,
            "stop": ["User:", "System:", "Seven:"]
        }
    }


    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=30)
        if r.status_code == 200:
            reply = r.json().get("response", "").strip()
            if not reply:
                reply = "Listening."

            if "VISUAL_REPORT:" not in prompt_text:
                if speaker_id not in CONVO_HISTORY:
                    CONVO_HISTORY[speaker_id] = []
                CONVO_HISTORY[speaker_id].append(f"Seven: {reply}")

            return reply
        else:
            print(Fore.RED + f"[BRAIN] Ollama returned status {r.status_code}")
            return "My brain hiccupped. Try again."
    except requests.exceptions.ConnectionError:
        print(Fore.RED + "[BRAIN] Cannot connect to Ollama. Is it running?")
        return "I can't reach my brain. Run 'ollama serve' in a terminal first."
    except requests.exceptions.Timeout:
        print(Fore.RED + "[BRAIN] Ollama took too long to respond.")
        return "My brain took too long. Try again."
    except Exception as e:
        print(Fore.RED + f"[BRAIN] Unexpected error: {e}")
        return "Something went wrong with my thinking."


def inject_observation(text):
    pass