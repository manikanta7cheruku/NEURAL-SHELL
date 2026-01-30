import requests
import json
import config  # Imports settings from config.json

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = config.KEY['brain']['model_name']
MAX_HISTORY = config.KEY['brain']['max_history']
TEMP = config.KEY['brain']['temperature']

# HISTORY STORAGE
CONVO_HISTORY = []

def think(prompt_text):
    global CONVO_HISTORY
    
    # 1. ADD USER INPUT
    CONVO_HISTORY.append(f"User: {prompt_text}")

    # 2. MEMORY MANAGEMENT (Sliding Window)
    # Prevents token overflow by removing the oldest exchange
    if len(CONVO_HISTORY) > (MAX_HISTORY * 2):
        CONVO_HISTORY.pop(0)
        CONVO_HISTORY.pop(0)

    # 3. BUILD THE PROMPT (ADAPTIVE LENGTH + STRICT LOGIC)
    system_prompt = (
        f"You are {config.KEY['identity']['name']}. "
        "Personality: Sarcastic, Dry, Efficient, Minimalist. "
        
        "RESPONSE GUIDELINES:"
        "1. ADAPTIVE LENGTH: If the user chats casually, be brief (1 sentence). If the user asks a complex question, explain clearly but concisley (max 3-4 sentences)."
        "2. TONE: Don't be overly polite. Be efficient. Use dry humor."
        "3. NO RAMBLING: Do not give life advice unless asked."
        
        "CORE LOGIC (CHAT vs ACTION):"
        "- IF the user asks for an ACTION (Open, Close, Search), output the COMMAND TAG."
        "- IF the user asks a QUESTION, just CHAT. Do NOT output a tag."
        
        "COMMAND SYNTAX (Use exact tags):"
        "1. ###OPEN: [app_name]"
        "2. ###CLOSE: [app_name] (Use '###CLOSE: CURRENT' only for 'Close it/Shut down')"
        "3. ###SEARCH: [query] (Only if explicitly asked to search/google)"
        "4. ###SYS: [command] (Volume/Screenshot)"
        
        "NEGATIVE CONSTRAINTS:"
        "- Do NOT take screenshots just because the user asks 'What are you doing?'."
        "- Do NOT hallucinate commands inside normal conversation."
        "- If the user makes a typo (e.g. 'Open Camlo'), assume the intent and output '###OPEN: Camlo'."
        
        "EXAMPLES:"
        "User: Hello -> Seven: What do you want?"
        "User: Tell me about Quantum Physics -> Seven: It's the study of matter and energy at the most fundamental level. It behaves differently than the macro world. That's the short version."
        "User: Open Chrome and Notepad -> Seven: On it. ###OPEN: Chrome ###OPEN: Notepad"
        "User: What are you doing? -> Seven: Waiting for you to make sense."
    )
    
    # 4. MERGE PROMPT WITH HISTORY
    history_block = "\n".join(CONVO_HISTORY)
    full_prompt = f"{system_prompt}\n\nCONVERSATION HISTORY:\n{history_block}\n\nSeven:"

    # 5. SEND TO OLLAMA
    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt, 
        "stream": False,
        "options": {
            "temperature": 0.2, # Low temp = Focused, less rambling
            "num_predict": 200  # Cap response length to avoid endless essays
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            ai_reply = response.json()["response"]
            
            # Save AI Reply to Memory
            CONVO_HISTORY.append(f"Seven: {ai_reply}")
            
            return ai_reply
        else:
            return "Error: Ollama server fail."
    except Exception as e:
        return f"Error: {e}"

def clear_history():
    global CONVO_HISTORY
    CONVO_HISTORY = []