import ears
import brain
import hands
import mouth
import gui
import tkinter as tk
import threading
import os
import sys
import re  # <--- CRITICAL IMPORT FOR MULTI-COMMANDS
import colorama
from colorama import Fore

# Import the config system we built in Step 1
import config 

colorama.init(autoreset=True)

app_ui = None

def seven_logic():
    global app_ui
    is_active = True 
    
    # Load basic settings from config (or defaults)
    wake_words = config.KEY['identity']['wake_words']
    
    app_ui.update_status("SYSTEM ONLINE", "#00ff00") 
    mouth.speak("Seven Online.")

    while True:
        try:
            # 1. VISUAL STATE
            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00") # Green
            else:
                app_ui.update_status("PAUSED", "#555555") # Grey

            # 2. LISTEN
            user_input = ears.listen()

            if not user_input:
                continue

            input_lower = user_input.lower()
            
            # --- LISTS OF TRIGGERS ---
            
            # A. KILL WORDS (Kills the App)
            kill_list = ["shut down", "shutdown", "kill system", "go to sleep", "terminate"]
            
            # B. PAUSE WORDS (Stops Listening)
            pause_list = config.KEY['identity']['stop_words']
            
            # C. RESUME WORDS (Wakes him up)
            resume_list = wake_words

            # --- LOGIC FLOW ---

            # 1. CHECK FOR KILL (Always Active)
            if any(trigger in input_lower for trigger in kill_list):
                print(Fore.RED + f"USER COMMAND: {user_input}") 
                app_ui.update_status("SHUTTING DOWN...", "#ff0000")
                mouth.speak("Systems offline. Goodbye.")
                app_ui.close()
                os._exit(0)

            # 2. CHECK FOR PAUSE (Only if Active)
            if is_active:
                if any(trigger in input_lower for trigger in pause_list):
                    print(Fore.MAGENTA + f"USER COMMAND: PAUSE ({user_input})") 
                    is_active = False
                    app_ui.update_status("PAUSED", "#555555")
                    mouth.speak("Standing by.")
                    continue 

            # 3. CHECK FOR RESUME (Only if Paused)
            if not is_active:
                if any(trigger in input_lower for trigger in resume_list):
                    print(Fore.GREEN + f"USER COMMAND: RESUME ({user_input})") 
                    is_active = True
                    app_ui.update_status("RESUMING...", "#00ff00")
                    mouth.speak("Online.")
                    continue
                else:
                    continue

            # --- PROCESS COMMANDS (Only if Active) ---
            if is_active:
                # LOGGING & UI
                print(Fore.YELLOW + f"USER: {user_input}")
                app_ui.update_status(f"USER: {user_input}", "#00ccff")
                
                # THINK
                # The GUI should Pulse here (Phase 1.5 Step 3), but for now we keep it simple
                app_ui.update_status("PROCESSING...", "#ff00ff")
                
                response = brain.think(user_input)
                
                # --- V1.5 NEW PARSING LOGIC ---
                
                # Step A: Separate Speech from Action
                # If the AI says: "Sure. ###OPEN: Chrome"
                # We want to speak "Sure" immediately.
                if "###" in response:
                    speech_part = response.split("###")[0].strip()
                    if speech_part:
                        mouth.speak(speech_part)
                else:
                    # If no tags, just speak the whole thing
                    mouth.speak(response)
                    app_ui.update_status(response, "#00ccff")

                # Step B: Find ALL Commands using Regex
                # This finds patterns like ###TAG: Value
                commands = re.findall(r"###(OPEN|CLOSE|SEARCH|SYS): (.*?)(?=###|$)", response)
                
                if commands:
                    print(Fore.CYAN + f"COMMANDS FOUND: {commands}")
                    
                    # Loop through every command found
                    for cmd_type, arg in commands:
                        arg = arg.strip()
                        
                        if cmd_type == "OPEN":
                            app_ui.update_status(f"OPENING: {arg}", "#00ff00")
                            # mouth.speak(f"Opening {arg}") # Optional: Un-comment if you want him to narrate
                            hands.open_app(arg)

                        elif cmd_type == "CLOSE":
                            app_ui.update_status(f"CLOSING: {arg}", "#ff0000")
                            # mouth.speak(f"Closing {arg}")
                            hands.close_app(arg)
                            
                        elif cmd_type == "SEARCH":
                            app_ui.update_status(f"SEARCHING: {arg}", "#0000ff")
                            hands.search_web(arg)
                            
                        elif cmd_type == "SYS":
                            app_ui.update_status(f"SYSTEM: {arg}", "#ffff00")
                            hands.system_control(arg)

        except Exception as e:
            print(Fore.RED + f"CRITICAL ERROR: {e}")

def start_app():
    global app_ui
    root = tk.Tk()
    app_ui = gui.SevenGUI(root)
    logic_thread = threading.Thread(target=seven_logic, daemon=True)
    logic_thread.start()
    root.mainloop()

if __name__ == "__main__":
    start_app()