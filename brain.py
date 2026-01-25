import requests 
import json     

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3" 
CONVO_HISTORY = "" # String to store the conversation

def think(prompt_text):
    global CONVO_HISTORY
    
    # 1. LIMIT HISTORY (Keep only last ~5 exchanges to save RAM)
    # If history gets too long, we chop the beginning
    if len(CONVO_HISTORY) > 2000:
        CONVO_HISTORY = CONVO_HISTORY[-2000:]

    # 2. UPDATE HISTORY WITH USER INPUT
    CONVO_HISTORY += f"\nUser: {prompt_text}"

        #3 STRICTER PROMPT
    system_prompt = (
        "You are Seven. An AI Agent on an 8 Billion Parameters. "
        "Personality: Sarcastic, dry, efficient. "
        
        "COMMAND RULES (USE ONLY THESE):"
        "1. ###OPEN: [app_name]"
        "2. ###SEARCH: [query]"
        "3. ###CLOSE: [app_name]"
        "4. ###SYS: [volume up / volume down / screenshot]"
        
        "NEGATIVE CONSTRAINTS (CRITICAL):"
        "1. NEVER put chat text inside ###SYS. Example: ###SYS: I don't care -> WRONG."
        "2. If you want to be sarcastic, just write plain text."
        "3. If the user input makes no sense, just say 'What?'."
        "4. Do not invent commands."
    )
    
    # ... (Keep the rest of the code, ensure temperature is 0.1) ...

    # 4. FULL PROMPT (System + History + New Input)
    full_prompt = f"{system_prompt}\n\nCONVERSATION HISTORY:\n{CONVO_HISTORY}\n\nUser: {prompt_text}\nSeven:"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt, 
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 100 
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            ai_reply = response.json()["response"]
            
            # 5. SAVE AI REPLY TO HISTORY
            CONVO_HISTORY += f"\nSeven: {ai_reply}"
            
            return ai_reply
        else:
            return "Error."
    except Exception as e:
        return f"Error: {e}"