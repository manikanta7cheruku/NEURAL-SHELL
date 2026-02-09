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
import re  # <--- V1.5: Regex for finding multiple commands
import colorama
from colorama import Fore

# Import the config system we built in Step 1
import config 

# Initialize Colorama for colored console text
colorama.init(autoreset=True)

# Global UI Variable to update the window from the thread
app_ui = None

def seven_logic():
    """
    The Core Intelligence Loop.
    Runs on a separate thread to prevent the GUI from freezing.
    """
    global app_ui
    is_active = True 
    
    # =========================================================================
    # CONFIGURATION LOADING
    # =========================================================================
    
    # Load basic settings from config (or defaults)
    WAKE_WORDS = ["wake up", "seven", "hey seven", "listen", "online", "resume"]
    PAUSE_WORDS = ["not you", "hold it", "hold on", "just a moment", "wait", "pause", "stop listening", "sleep", "silence"]
    KILL_WORDS = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]
    
    # Initial Greeting
    print(Fore.GREEN + "[SYSTEM] Initializing Seven...")
    mouth.speak(f"{config.KEY['identity']['name']} Online.")
    app_ui.update_status("SYSTEM ONLINE", "#00ff00") 

    # =========================================================================
    # MAIN EVENT LOOP
    # =========================================================================
    while True:
        try:
            # --- 1. GUI STATE UPDATES ---
            # Update the floating window to show if we are listening or sleeping
            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00") # Green
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')", "#555555") # Grey

            # --- 2. LISTEN INPUT ---
            # This function blocks until it hears a sentence
            user_input = ears.listen()

            # If silence or noise, loop back
            if not user_input:
                continue
            
            # Normalize text for checking triggers
            text_lower = user_input.lower()

            # =================================================================
            # 3. TRIGGER WORD FILTERS
            # =================================================================

            # A. KILL COMMAND (Always Active)
            # This shuts down the entire Python script immediately
            if any(trigger in text_lower for trigger in KILL_WORDS):
                print(Fore.RED + f"USER COMMAND: KILL ({user_input})") 
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                mouth.speak("Systems offline. Goodbye.")
                app_ui.close() # Close GUI
                os._exit(0)    # Kill Process

            # B. WAKE COMMAND (Activates the Brain)
            # Checks if the user said "Seven" or "Wake up"
            if any(trigger in text_lower for trigger in WAKE_WORDS):
                if not is_active:
                    is_active = True
                    mouth.speak("I'm listening.")
                    print(Fore.GREEN + "SYSTEM: RESUMED")
                    app_ui.update_status("RESUMED", "#00ff00")
                    # We continue here so we don't process the "Wake up" text as a command
                    continue 

            # C. PAUSE COMMAND (Deactivates the Brain)
            # Checks if the user said "Not you" or "Stop listening"
            if is_active:
                if any(trigger in text_lower for trigger in PAUSE_WORDS):
                    is_active = False
                    mouth.speak("Standing by.")
                    print(Fore.MAGENTA + "SYSTEM: PAUSED")
                    app_ui.update_status("PAUSED", "#555555")
                    continue

            # If Paused, ignore everything else
            if not is_active:
                continue

            # =================================================================
            # 4. CORE PROCESSING (Active Mode)
            # =================================================================
            
            # Log the input
            print(Fore.YELLOW + f"USER: {user_input}")
            app_ui.update_status(f"USER: {user_input}", "#00ccff")
            app_ui.update_status("THINKING...", "#ff00ff")

            # SEND TO BRAIN (Llama-3)
            # The Brain decides what to do: Chat, Look, or Act
            response = brain.think(user_input)
            
            # Failsafe if Brain returns None
            if not response: 
                response = "Processing error."

            # # =================================================================
            # # PHASE 2.0: VISION PIPELINE (The Eyes)
            # # =================================================================
            # if "###LOOK" in response:
            #     print(Fore.MAGENTA + "[VISION] Triggered!")
            #     app_ui.update_status("👀 LOOKING...", "#FF00FF") 
            #     mouth.speak("Scanning screen.")
                
            #     # STEP A: VRAM SWAP (Unload Chat Model)
            #     # We need to free up 4GB VRAM for the Vision Model
            #     print(Fore.CYAN + "[MEMORY] Unloading Chat Model...")
            #     try:
            #         brain_manager.switch_to_vision()
            #     except Exception as e:
            #         # Fallback if manager fails
            #         print(Fore.RED + f"[MEMORY WARNING] Manager failed: {e}")
            #         brain_manager.unload_model(config.KEY['brain']['model_name'])

            #     # STEP B: CAPTURE & ANALYZE
            #     # Captures screenshot and sends to LLaVA
            #     print(Fore.CYAN + "[EYES] Capturing visual data...")
            #     vision_text = eyes.see() 
                
            #     if not vision_text:
            #         vision_text = "I could not see anything. The screen might be blank."

            #     # STEP C: VRAM SWAP (Reload Chat Model)
            #     # We need Llama-3 back to explain what it saw
            #     print(Fore.CYAN + "[MEMORY] Reloading Chat Model...")
            #     try:
            #         brain_manager.switch_to_chat()
            #     except Exception as e:
            #         brain_manager.unload_model(config.KEY['vision']['model_name'])
                
            #     # STEP D: REPORT BACK (DIRECT FEED FIX)
            #     app_ui.update_status("ANALYZING...", "#00ccff")
                
            #     # 1. Inject into history for context
            #     brain.inject_observation(vision_text)
                
            #     # 2. FORCE FEED the data into the prompt
            #     # This prevents the "Discord" hallucination by putting the real text in the prompt
            #     # We use 'VISUAL_REPORT:' which prompts the brain to simply describe it
            #     final_answer = brain.think(f"VISUAL_REPORT: {vision_text}")
                
            #     # 3. Clean up the tag so we don't say "Hashtag Look"
            #     final_answer = final_answer.replace("###LOOK", "")
                
            #     # 4. Speak
            #     print(Fore.GREEN + f"SEVEN: {final_answer}")
            #     mouth.speak(final_answer)
            #     app_ui.update_status(final_answer, "#00ccff")
                
            #     # Skip the rest of the loop so we don't try to "open" the image
            #     continue 

            # =================================================================
            # PHASE 1.5: COMMAND PIPELINE (The Hands)
            # =================================================================
            
            # STEP A: Separate Speech from Actions
            # Example: "On it. ###OPEN: Chrome"
            # We want to speak "On it" immediately.
            speech_part = response
            if "###" in response:
                speech_part = response.split("###")[0].strip()
            
            if speech_part:
                # Speak the conversational part
                mouth.speak(speech_part)
                app_ui.update_status(speech_part, "#00ccff")

            # STEP B: EXTRACT COMMANDS (Regex to find ALL tags)
            # Finds: ###OPEN: Chrome ###OPEN: Camera
            commands = re.findall(r"###(OPEN|CLOSE|SEARCH|SYS): (.*?)(?=###|$)", response)
            
            if commands:
                print(Fore.CYAN + f"COMMANDS FOUND: {commands}")
                
                for cmd_type, arg in commands:
                    # --- STRING CLEANING (CRITICAL FIX) ---
                    # Removes quotes, commas, periods that might crash the Hands
                    # Example: "Camera," -> "Camera"
                    clean_arg = arg.replace('"', '').replace("'", "").replace(",", "").replace(".", "").strip()
                    
                    if not clean_arg:
                        continue

                    # --- SAFETY NET: SPLIT MULTIPLE APPS ---
                    # Handle "Camera and Notepad" OR "Camera, Notepad"
                    # This fixes the issue where Brain outputs one tag for two apps
                    sub_apps = []
                    
                    if " and " in clean_arg:
                        sub_apps = clean_arg.split(" and ")
                    elif "," in clean_arg:
                        sub_apps = clean_arg.split(",")
                    elif "&" in clean_arg:
                        sub_apps = clean_arg.split("&")
                    else:
                        # Fallback: Check for stuck-together names like "Camera Control Panel"
                        known_apps = ["camera", "control panel", "notepad", "chrome", "explorer"]
                        lower_arg = clean_arg.lower()
                        found_split = False
                        
                        for app in known_apps:
                            if app in lower_arg:
                                sub_apps.append(app)
                                lower_arg = lower_arg.replace(app, "")
                                found_split = True
                        
                        if not found_split:
                            sub_apps = [clean_arg] # Just one app

                    # --- EXECUTION LOOP ---
                    # Runs for every app found in the split list
                    for app_to_run in sub_apps:
                        app_to_run = app_to_run.strip()
                        if not app_to_run: continue

                        # Execute based on Type
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
            # We catch the error but don't crash, so Seven stays online.
            app_ui.update_status("ERROR RECOVERED", "#ff0000")

def start_app():
    """
    Launches the GUI and the Logic Thread.
    """
    global app_ui
    root = tk.Tk()
    app_ui = gui.SevenGUI(root)
    
    # Daemon=True means this thread dies when the window closes
    logic_thread = threading.Thread(target=seven_logic, daemon=True)
    logic_thread.start()
    
    root.mainloop()

if __name__ == "__main__":
    start_app()