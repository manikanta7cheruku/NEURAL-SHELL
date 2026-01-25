import ears
import brain
import hands
import mouth
import gui
import tkinter as tk
import threading
import os
import sys
import colorama
from colorama import Fore

colorama.init(autoreset=True)

app_ui = None

def seven_logic():
    global app_ui
    is_active = True 
    
    app_ui.update_status("SYSTEM ONLINE", "#00ff00") 
    mouth.speak("Seven Online.")

    while True:
        try:
            # 1. VISUAL STATE
            if is_active:
                app_ui.update_status("LISTENING...", "#00ff00") # Green
            else:
                app_ui.update_status("PAUSED (Say 'Wake Up')...", "#555555") # Grey

            # 2. LISTEN
            user_input = ears.listen()

            if not user_input:
                continue

            input_lower = user_input.lower()
            
            # --- LISTS OF TRIGGERS ---
            
            # A. KILL WORDS (Kills the App)
            kill_list = [
                "shut down", "shutdown", "kill system", "go to sleep", 
                "terminate", "turn off", "exit program", "quit"
            ]
            
            # B. PAUSE WORDS (Stops Listening)
            pause_list = [
                "stop", "wait", "hold on", "pause", "not you", 
                "shut up", "silence", "stand by", "break"
            ]
            
            # C. RESUME WORDS (Wakes him up)
            resume_list = [
                "seven", "hey seven", "wake up", "resume", 
                "online", "start listening", "i'm back"
            ]

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
                    # Ignore everything else while paused
                    print(Fore.LIGHTBLACK_EX + f"IGNORED: {user_input}")
                    continue

            # --- PROCESS COMMANDS (Only if Active) ---
            if is_active:
                # LOGGING & UI
                print(Fore.YELLOW + f"USER: {user_input}")
                # Show User text in BLUE to confirm we heard it
                app_ui.update_status(f"USER: {user_input}", "#00ccff")
                
                # THINK
                response = brain.think(user_input)

                # SHOW PROCESSING COLOR
                app_ui.update_status("PROCESSING...", "#ff00ff")
                
                # EXECUTE
                if "###OPEN:" in response:
                    app_name = response.split("###OPEN:")[1].strip()
                    mouth.speak(f"Opening {app_name}.")
                    hands.open_app(app_name)

                elif "###CLOSE:" in response:
                    app_name = response.split("###CLOSE:")[1].strip()
                    mouth.speak(f"Closing {app_name}.")
                    hands.close_app(app_name)
                    
                elif "###SEARCH:" in response:
                    query = response.split("###SEARCH:")[1].strip()
                    mouth.speak(f"Searching web.")
                    hands.search_web(query)
                    
                elif "###SYS:" in response:
                    cmd = response.split("###SYS:")[1].strip()
                    mouth.speak("Executing.") 
                    hands.system_control(cmd)
                    
                else:
                    # Chat
                    app_ui.update_status(response, "#00ccff") 
                    mouth.speak(response)

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