"""
=============================================================================
PROJECT SEVEN - main.py (The Controller)
Version: 1.1 (Memory Integration)
Version: 1.1.1 (Memory + Mood + Command Logging)
Version: 1.1.2 (Memory + Mood + Command Logging + Polish)

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

import ears
import brain
import hands
import mouth
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

    WAKE_WORDS = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait",
                   "pause", "stop listening", "sleep", "silence"]
    KILL_WORDS = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]

    # --- V1.1: Show memory stats on startup ---
    stats = seven_memory.get_stats()
    print(Fore.GREEN + f"[SYSTEM] Memory loaded: {stats['total_conversations']} conversations, "
                        f"{stats['total_facts']} facts stored.")
    
    # startup display
    mood_status = mood_engine.get_status()
    print(Fore.MAGENTA + f"[SYSTEM] Mood: {mood_status['mood_value']:.2f} ({mood_status['label']})")
    cmd_stats = command_log.get_stats()
    print(Fore.CYAN + f"[SYSTEM] Commands logged: {cmd_stats['total']} (success rate: {cmd_stats['success_rate']})")

    # Initial Greeting
    print(Fore.GREEN + "[SYSTEM] Initializing Seven...")
    mouth.speak(f"{config.KEY['identity']['name']} V1.1.2 Online.")
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
            user_input = ears.listen()

            if not user_input:
                continue

            text_lower = user_input.lower()

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
            response = brain.think(user_input)

            if not response:
                response = "Processing error."

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
                    if clean_response:
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
                mouth.speak(speech_part)
                app_ui.update_status(speech_part, "#00ccff")

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
                            hands.open_app(app_to_run)
                        elif cmd_type == "CLOSE":
                            app_ui.update_status(f"CLOSING: {app_to_run}", "#ff0000")
                            hands.close_app(app_to_run)
                        elif cmd_type == "SEARCH":
                            app_ui.update_status(f"SEARCHING: {app_to_run}", "#0000ff")
                            hands.search_web(app_to_run)
                        elif cmd_type == "SYS":
                            app_ui.update_status(f"SYSTEM: {app_to_run}", "#ffff00")
                            hands.system_control(app_to_run)

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