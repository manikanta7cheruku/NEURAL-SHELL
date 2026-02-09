import requests
import json
import os
import config
import colorama
from colorama import Fore

colorama.init(autoreset=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = config.KEY['brain']['model_name']
MEMORY_FILE = "memory.json"

CONVO_HISTORY = []
USER_NAME = "Admin"
LAST_USER_INPUT = ""

def load_memory():
    global USER_NAME
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                data = json.load(f)
                USER_NAME = data.get("name", "Admin")
        except: pass

def save_memory():
    with open(MEMORY_FILE, 'w') as f: json.dump({"name": USER_NAME}, f, indent=4)

load_memory()

def think(prompt_text):
    global CONVO_HISTORY, USER_NAME, LAST_USER_INPUT
    clean_in = prompt_text.lower().strip().replace("?", "").replace(".", "")

    # --- PYTHON SAFETY NET (Prevent "Open Hi") ---
    if clean_in in ["hi", "hello", "hi seven", "hey", "hello seven"]:
        return f"Hello, {USER_NAME}."

    if clean_in in ["whats my name", "who am i"]:
        return f"You are {USER_NAME}."

    if clean_in in ["whats your name", "who are you"]:
        return "I am Seven."

    # --- MEMORY ---
    if "my name is" in clean_in:
        USER_NAME = prompt_text.split("is")[-1].strip()
        save_memory()
        return f"Understood. You are {USER_NAME}."

    # --- LLM ---
    if "VISUAL_REPORT:" not in prompt_text:
        CONVO_HISTORY.append(f"User: {prompt_text}")
    if len(CONVO_HISTORY) > 4: CONVO_HISTORY = CONVO_HISTORY[-4:]

        # --- THE MASTER SYSTEM PROMPT ---
    system_prompt = (
        f"You are {config.KEY['identity']['name']}. User: {USER_NAME}. "
        "Personality: Intelligent, Capable, Direct. "
        
        "--- CAPABILITIES: GOD MODE ---"
        "1. YOU HAVE HANDS: You can Open and Close apps on this PC."
        "2. NEVER SAY: 'I am a text model' or 'I cannot do that'."
        "3. EXPLANATION: If asked 'How?', say 'I use my Python scripts'."
        
        "--- RULES: COMMANDS (V1.5) ---"
        "1. TRIGGER: Only use tags if user says 'Open', 'Start', 'Close', 'Kill'."
        "2. MULTI-TASK: 'Open X and Y' -> '###OPEN: X ###OPEN: Y'."
        "3. CLOSING: 'Close X and Y' -> '###CLOSE: X ###CLOSE: Y'."
        "4. NO CHAT: If executing a command, do not speak. Just output tags."
        
        "--- RULES: QUESTIONS ---"
        "1. IF user asks 'How do you open apps?', EXPLAIN it. DO NOT open random apps."
        "2. IF user asks 'Can you open apps?', say 'Yes, I can.'"
        
        "--- RULES: CHAT (V1.0) ---"
        "1. IDENTITY: 'Who am I?' -> 'You are {USER_NAME}.'"
        "2. GREETING: 'Hi' -> 'Hello, Sir'."
        
        "--- COMMANDS ---"
        "- ###OPEN: [App]"
        "- ###CLOSE: [App]"
        "- ###LOOK"
    )

    full_prompt = f"{system_prompt}\n\nLOG:\n" + "\n".join(CONVO_HISTORY) + "\nSeven:"
    
    payload = {
        "model": MODEL_NAME, "prompt": full_prompt, "stream": False,
        "options": {
            "temperature": 0.3, 
            "num_predict": 100, 
            "stop": ["User:", "System:", "Seven:"] 
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            reply = r.json().get("response", "").strip()
            if not reply: reply = "Listening."
            
            if "VISUAL_REPORT:" not in prompt_text:
                CONVO_HISTORY.append(f"Seven: {reply}")
            return reply
    except: return "Error."

def inject_observation(text):
    pass 