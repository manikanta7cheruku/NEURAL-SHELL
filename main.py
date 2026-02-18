"""
=============================================================================
PROJECT SEVEN - main.py (The Controller)
Version: 1.1 (Memory Integration)
Version: 1.1.1 (Memory + Mood + Command Logging)
Version: 1.1.2 (Memory + Mood + Command Logging + Polish)
Version: 1.2 (Memory + Mood + Command Logging + Voice Identity)
Version: 1.3 (Interruption & Full Duplex)

CHANGES FROM V1.5:
    1. NEW: Memory system initialized on startup
    2. NEW: Every conversation stored in long-term memory after response
    3. REMOVED: Commented-out V2.0 vision code (clean slate for when we need it)
    4. KEPT: All V1.5 app control logic (unchanged, still working)
    
ARCHITECTURE:
    GUI Thread (tkinter) ←→ Logic Thread (seven_logic)
        └→ ears.listen() → brain.think() → mouth.speak()    
                              ↑                ↓
                         memory.search()   memory.store()
=============================================================================
"""

from ears import listen
from ears.voice_id import identify_speaker, enroll_speaker, is_voice_id_enabled, get_enrolled_speakers
from ears.core import listen_for_interrupt
import brain
import hands.core as core
import mouth
from mouth import interrupt as mouth_interrupt, is_speaking
import random
import brain_manager
import gui
import tkinter as tk
import threading
import os
import sys
import re
import colorama
from colorama import Fore
import config

# V1.1: Import the memory system
from memory import seven_memory
from memory.mood import mood_engine
from memory.command_log import command_log

colorama.init(autoreset=True)

# Global UI Variable to update the window from the thread
app_ui = None


def seven_logic():
    """
    The Core Intelligence Loop.
    Runs on a separate thread to prevent the GUI from freezing.
    
    V1.1 Changes:
    - After every successful conversation, store it in long-term memory
    - Memory search happens INSIDE brain.think() (not here)
    - Storage happens HERE (after we have both user input AND response)
    """
    global app_ui
    is_active = True

    # =========================================================================
    # CONFIGURATION LOADING
    # =========================================================================

    # =========================================================================
    # V1.3: INTERRUPT CONFIGURATION
    # =========================================================================
    interrupt_config = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]

    def speak_with_interrupt(text):
        """
        V1.3: Speak with interrupt detection.
        Starts an interrupt listener thread while speaking.
        Returns True if completed, False if interrupted.
        """
        if not INTERRUPT_ENABLED:
            mouth.speak(text)
            return True
        
        import time as _time
        if _time.time() - last_interrupt_time[0] < INTERRUPT_COOLDOWN:
            mouth.speak(text)
            return True
        
        stop_listening = threading.Event()
        was_interrupted = threading.Event()
        
        def on_interrupt():
            was_interrupted.set()
            mouth_interrupt()
            last_interrupt_time[0] = _time.time()
        
        interrupt_thread = threading.Thread(
            target=listen_for_interrupt,
            args=(INTERRUPT_WORDS, on_interrupt, stop_listening),
            daemon=True
        )
        interrupt_thread.start()
        
        completed = mouth.speak(text)
        
        stop_listening.set()
        interrupt_thread.join(timeout=2)
        
        if was_interrupted.is_set():
            print("[SYSTEM] ⚡ Speech was interrupted by user")
            app_ui.update_status("INTERRUPTED", "#ffaa00")
            interrupt_context["was_interrupted"] = True
            interrupt_context["last_response"] = text
            mouth.speak("Yeah?")
            return False
        
        return True

    # =========================================================================
    # CONFIGURATION LOADING
    # =========================================================================

    WAKE_WORDS = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                   "pause", "stop listening", "sleep", "silence"]
    KILL_WORDS = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]


    # V1.3: Interrupt configuration
    interrupt_config = config.KEY.get('interrupt', {})
    INTERRUPT_ENABLED = interrupt_config.get('enabled', True)
    INTERRUPT_WORDS = interrupt_config.get('words', ["stop", "seven", "hey seven"])
    INTERRUPT_COOLDOWN = interrupt_config.get('interrupt_cooldown', 1.5)
    last_interrupt_time = [0]  # list so nonlocal works in nested function

    # V1.3: Interrupt context — what was Seven saying when interrupted
    interrupt_context = {"last_response": None, "last_input": None, "was_interrupted": False}

    # --- V1.1: Show memory stats on startup ---
    stats = seven_memory.get_stats()
    print(Fore.GREEN + f"[SYSTEM] Memory loaded: {stats['total_conversations']} conversations, "
                        f"{stats['total_facts']} facts stored.")
    
    # startup display
    mood_status = mood_engine.get_status()
    print(Fore.MAGENTA + f"[SYSTEM] Mood: {mood_status['mood_value']:.2f} ({mood_status['label']})")
    cmd_stats = command_log.get_stats()
    print(Fore.CYAN + f"[SYSTEM] Commands logged: {cmd_stats['total']} (success rate: {cmd_stats['success_rate']})")

        # V1.2: Voice ID status
    if is_voice_id_enabled():
        speakers = get_enrolled_speakers()
        print(Fore.CYAN + f"[SYSTEM] Voice ID active. Enrolled speakers: {', '.join(speakers)}")
    else:
        print(Fore.YELLOW + "[SYSTEM] Voice ID inactive. No speakers enrolled. Say 'Enroll my voice' to start.")

    # Initial Greeting
    print(Fore.GREEN + "[SYSTEM] Initializing Seven...")
    mouth.speak(f"{config.KEY['identity']['name']} V1.3 Online.")
    app_ui.update_status("SYSTEM ONLINE", "#00ff00")

    # =========================================================================
    # MAIN EVENT LOOP
    # =========================================================================
    while True:
        try:
            # --- 1. GUI STATE UPDATES ---
            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00")
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555")

            # --- 2. LISTEN INPUT ---
            user_input, audio_path = listen()

            if not user_input:
                continue


            # --- V1.3: INTERRUPT CONTEXT HANDLER ---
            # --- V1.3: INTERRUPT CONTEXT HANDLER ---
            if interrupt_context["was_interrupted"]:
                resume_words = ["continue", "resume", "go on", "go ahead", "keep going", "carry on"]
                
                if any(w in text_lower for w in resume_words):
                    old_response = interrupt_context["last_response"]
                    old_input = interrupt_context["last_input"]
                    interrupt_context["was_interrupted"] = False
                    interrupt_context["last_response"] = None
                    interrupt_context["last_input"] = None
                    
                    if old_response and old_input:
                        # Send to brain with context so LLM continues naturally
                        resume_prompt = f"I was interrupted while answering this: '{old_input}'. I had said: '{old_response}'. Now continue from where I left off naturally without repeating what was already said."
                        response = brain.think(resume_prompt, speaker_id=speaker_id)
                        if response:
                            speak_with_interrupt(response)
                        else:
                            mouth.speak("Sorry, I lost my train of thought.")
                    else:
                        mouth.speak("Sorry, I lost my train of thought. Ask me again?")
                    continue
                else:
                    interrupt_context["was_interrupted"] = False
                    interrupt_context["last_response"] = None
                    interrupt_context["last_input"] = None

            # --- 2.5. VOICE IDENTIFICATION (V1.2) ---

            text_lower = user_input.lower()

            # --- 2.5. VOICE IDENTIFICATION (V1.2) ---
            speaker_id = "default"
            if audio_path and is_voice_id_enabled():
                speaker_id = identify_speaker(audio_path)
                print(Fore.CYAN + f"[VOICE ID] Speaker: {speaker_id}")
            
            # --- 2.6. VOICE ENROLLMENT COMMAND ---
            if "enroll my voice" in text_lower or "enroll voice" in text_lower:
                # Ask for name
                mouth.speak("What name should I save this voice as?")
                app_ui.update_status("ENROLLING — Speak your name...", "#ff00ff")
                name_input, name_audio = listen()
                if name_input:
                    enroll_name = name_input.strip().replace(".", "").replace("!", "")
                    mouth.speak(f"Now say a few sentences so I can learn your voice, {enroll_name}.")
                    app_ui.update_status(f"ENROLLING {enroll_name} — Keep talking...", "#ff00ff")
                    # Record a longer sample for enrollment
                    enroll_input, enroll_audio = listen()
                    if enroll_audio:
                        success = enroll_speaker(enroll_name, enroll_audio)
                        if success:
                            mouth.speak(f"Got it. I'll recognize your voice now, {enroll_name}.")
                        else:
                            mouth.speak("I couldn't capture your voice clearly. Try again.")
                    else:
                        mouth.speak("I didn't hear anything. Try again.")
                else:
                    mouth.speak("I didn't catch your name. Try again.")
                continue

            # =================================================================
            # 3. TRIGGER WORD FILTERS
            # =================================================================

            # A. KILL COMMAND (Always Active)
            if any(trigger in text_lower for trigger in KILL_WORDS):
                print(Fore.RED + f"USER COMMAND: KILL ({user_input})")
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            # B. WAKE COMMAND
            if any(trigger in text_lower for trigger in WAKE_WORDS):
                if not is_active:
                    is_active = True
                    mouth.speak("I'm listening.")
                    print(Fore.GREEN + "SYSTEM: RESUMED")
                    app_ui.update_status("RESUMED", "#00ff00")
                    continue

            # C. PAUSE COMMAND
            if is_active:
                if any(trigger in text_lower for trigger in PAUSE_WORDS):
                    is_active = False
                    mouth.speak("Standing by.")
                    print(Fore.MAGENTA + "SYSTEM: PAUSED")
                    app_ui.update_status("PAUSED", "#555555")
                    continue

            # If Paused, ignore everything
            if not is_active:
                continue

            # =================================================================
            # 4. CORE PROCESSING (Active Mode)
            # =================================================================

            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status(f"USER: {user_input}", "#00ccff")
            app_ui.update_status("THINKING...", "#ff00ff")

            # SEND TO BRAIN
            # brain.think() now internally:
            #   1. Checks Python overrides
            #   2. Searches memory for relevant context
            #   3. Extracts facts from user input
            #   4. Sends enhanced prompt to LLM
            response = brain.think(user_input, speaker_id=speaker_id)

            if not response:
                response = "Processing error."
            # V1.3: Track if speech completes (set later in speech block)
            completed = True

            # =================================================================
            # V1.1: STORE CONVERSATION IN LONG-TERM MEMORY
            # =================================================================
            # We store AFTER getting the response so we save both sides
            # We DON'T store:
            #   - Pure command responses (###OPEN, ###CLOSE) — no useful info
            #   - Very short exchanges ("hi" → "hello") — noise
            #   - Visual reports — they're real-time, not historical
            
            should_store = True
            
            # Don't store pure command outputs
            if response.strip().startswith("###"):
                should_store = False
            
            # Don't store very short greetings (they're noise in memory)
            if len(user_input.strip()) <= 3:
                should_store = False
            
            # Don't store if it's just a greeting response
            greeting_words = ["hi", "hello", "hey"]
            if user_input.lower().strip() in greeting_words:
                should_store = False
            
            # Don't store identity responses (they pollute memory)
            identity_phrases = ["i am seven", "you can call me seven",
                                "still seven", "you just asked",
                                "you've asked me this", "you haven't told me that",
                                f"you are {brain.USER_NAME.lower()}"]
            response_lower = response.lower()
            if any(phrase in response_lower for phrase in identity_phrases):
                should_store = False
            
            if should_store:
                # Store in long-term memory (ChromaDB)
                # This runs in the background — doesn't slow down response
                try:
                    # Clean the response: remove command tags before storing
                    clean_response = re.sub(r'###\w+:\s*\S+', '', response).strip()
                    # V1.3: Tag interrupted responses so Seven knows it was cut off
                    if not completed and clean_response:
                        clean_response = f"[INTERRUPTED] {clean_response}"
                    if clean_response:
                        if speaker_id != "default" and speaker_id != "unknown":
                            seven_memory.store_conversation(user_input, clean_response, user_id=speaker_id)
                        else:
                            seven_memory.store_conversation(user_input, clean_response)
                except Exception as e:
                    # Memory storage failure should NEVER crash Seven
                    print(Fore.RED + f"[MEMORY ERROR] Failed to store: {e}")

            # =================================================================
            # PHASE 1.5: COMMAND PIPELINE (The Hands)
            # =================================================================

            # STEP A: Separate Speech from Actions
            speech_part = response
            if "###" in response:
                speech_part = response.split("###")[0].strip()

            if speech_part:
                interrupt_context["last_input"] = user_input
                completed = speak_with_interrupt(speech_part)
                if completed:
                    app_ui.update_status(speech_part, "#00ccff")
                else:
                    app_ui.update_status("⚡ INTERRUPTED", "#ffaa00")

                    
            # STEP B1: EXTRACT WINDOW COMMANDS (V1.6)
            window_cmds = re.findall(r"###WINDOW:\s*(.*?)(?=###|$)", response)
            if window_cmds:
                for param_str in window_cmds:
                    param_str = param_str.strip()
                    print(Fore.CYAN + f"[WINDOW CMD] Raw params: {param_str}")
                    
                    # Parse key=value pairs
                    params = {}
                    for pair in param_str.split():
                        if "=" in pair:
                            key, val = pair.split("=", 1)
                            params[key.strip()] = val.strip()
                    
                    if params:
                        success, msg = hands.manage_window(params)
                        if success:
                            app_ui.update_status(f"🪟 {msg}", "#00ff00")
                        else:
                            fail_responses = [
                                msg,
                                f"Window issue: {msg}",
                                msg,
                            ]
                            mouth.speak(random.choice(fail_responses))
                            app_ui.update_status(f"🪟 FAILED: {msg}", "#ff0000")

            # STEP B: EXTRACT COMMANDS
            commands = re.findall(r"###(OPEN|CLOSE|SEARCH|SYS): (.*?)(?=###|$)", response)

            if commands:
                print(Fore.CYAN + f"COMMANDS FOUND: {commands}")

                for cmd_type, arg in commands:
                    clean_arg = arg.replace('"', '').replace("'", "").replace(",", "").replace(".", "").strip()

                    if not clean_arg:
                        continue

                    # --- SAFETY NET: SPLIT MULTIPLE APPS ---
                    sub_apps = []

                    if " and " in clean_arg:
                        sub_apps = clean_arg.split(" and ")
                    elif "," in clean_arg:
                        sub_apps = clean_arg.split(",")
                    elif "&" in clean_arg:
                        sub_apps = clean_arg.split("&")
                    else:
                        known_apps = ["camera", "control panel", "notepad", "chrome", "explorer"]
                        lower_arg = clean_arg.lower()
                        found_split = False

                        for app in known_apps:
                            if app in lower_arg:
                                sub_apps.append(app)
                                lower_arg = lower_arg.replace(app, "")
                                found_split = True

                        if not found_split:
                            sub_apps = [clean_arg]

                    # --- EXECUTION LOOP ---
                    for app_to_run in sub_apps:
                        app_to_run = app_to_run.strip()
                        if not app_to_run:
                            continue

                        if cmd_type == "OPEN":
                            app_ui.update_status(f"OPENING: {app_to_run}", "#00ff00")
                            success = core.open_app(app_to_run)
                            if not success:
                                fail_responses = [
                                    f"Can't find {app_to_run}. Check the name?",
                                    f"{app_to_run} doesn't seem to exist on this machine.",
                                    f"No luck with {app_to_run}. Is it installed?",
                                    f"Couldn't find {app_to_run}. Try the exact name.",
                                ]
                                mouth.speak(random.choice(fail_responses))
                        elif cmd_type == "CLOSE":
                            app_ui.update_status(f"CLOSING: {app_to_run}", "#ff0000")
                            success = core.close_app(app_to_run)
                            if not success:
                                fail_responses = [
                                    f"{app_to_run} doesn't seem to be running.",
                                    f"Can't find {app_to_run} in active processes.",
                                    f"Nothing to close — {app_to_run} isn't open.",
                                ]
                                mouth.speak(random.choice(fail_responses))
                        elif cmd_type == "SEARCH":
                            app_ui.update_status(f"SEARCHING: {app_to_run}", "#0000ff")
                            core.search_web(app_to_run)
                        elif cmd_type == "SYS":
                            app_ui.update_status(f"SYSTEM: {app_to_run}", "#ffff00")
                            core.system_control(app_to_run)
            # Clean up temp audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass

        except Exception as e:
            print(Fore.RED + f"CRITICAL ERROR in Main Loop: {e}")
            app_ui.update_status("ERROR RECOVERED", "#ff0000")


def start_app():
    """
    Launches the GUI and the Logic Thread.
    """
    global app_ui
    root = tk.Tk()
    app_ui = gui.SevenGUI(root)

    logic_thread = threading.Thread(target=seven_logic, daemon=True)
    logic_thread.start()

    root.mainloop()


if __name__ == "__main__":
    start_app()