import brain
import hands
import re
import colorama
from colorama import Fore

colorama.init(autoreset=True)

print(Fore.CYAN + "=== SEVEN TEXT DEBUGGER (ACTIVE MODE) ===")
print("Type 'quit' to exit.")

while True:
    # 1. Get Input
    user_input = input(Fore.YELLOW + "\nYOU: ")
    if user_input.lower() in ["quit", "exit"]: break

    # 2. Brain Think
    print(Fore.MAGENTA + "Seven is thinking...")
    response = brain.think(user_input)
    print(Fore.GREEN + f"SEVEN: {response}")

    # 3. Hands Act (ACTUALLY EXECUTING NOW)
    commands = re.findall(r"###(OPEN|CLOSE|SEARCH|SYS): (.*?)(?=###|$)", response)
    
    for cmd_type, arg in commands:
        arg = arg.replace('"', '').replace("'", "").strip()
        
        # Splitter Logic
        sub_apps = []
        if " and " in arg: sub_apps = arg.split(" and ")
        elif "," in arg: sub_apps = arg.split(",")
        else: sub_apps = [arg]

        for clean_arg in sub_apps:
            clean_arg = clean_arg.strip()
            print(Fore.BLUE + f"[HANDS ACTION] Executing: {cmd_type} -> {clean_arg}")
            
            # --- EXECUTION ENABLED ---
            if cmd_type == "OPEN": 
                hands.open_app(clean_arg)
            elif cmd_type == "CLOSE": 
                hands.close_app(clean_arg)
            elif cmd_type == "SEARCH": 
                hands.search_web(clean_arg)