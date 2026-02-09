import requests
import json
import config
from colorama import Fore

# API Endpoint
OLLAMA_API = "http://localhost:11434/api/generate"

def unload_model(model_name):
    """
    Forces Ollama to unload a model from VRAM to prevent Out Of Memory crashes.
    """
    print(Fore.CYAN + f"[MEMORY] Unloading {model_name}...")
    try:
        # Sending keep_alive: 0 forces the model to unload immediately
        requests.post(OLLAMA_API, json={
            "model": model_name,
            "keep_alive": 0
        })
    except Exception as e:
        print(Fore.RED + f"[MEMORY ERROR] Failed to unload: {e}")

def switch_to_vision():
    """
    Unloads Chat, Loads Vision (Passive).
    """
    # Unload Chat model (Llama-3)
    unload_model(config.KEY['brain']['model_name'])

def switch_to_chat():
    """
    Unloads Vision, Loads Chat (Passive).
    """
    # Unload Vision model (LLaVA)
    unload_model(config.KEY['vision']['model_name'])