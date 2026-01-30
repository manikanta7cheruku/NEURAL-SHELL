import json
import os

# Define the file name for our settings
CONFIG_FILE = "config.json"

def load_config():
    """
    Tries to load settings from config.json.
    If the file is missing, it returns a default set of settings
    so the program doesn't crash.
    """
    if not os.path.exists(CONFIG_FILE):
        print(f"[WARNING] {CONFIG_FILE} not found. Using default settings.")
        return get_defaults()

    try:
        with open(CONFIG_FILE, 'r') as file:
            data = json.load(file)
            print(f"[SYSTEM] Configuration loaded successfully.")
            return data
    except Exception as e:
        print(f"[ERROR] Could not load config: {e}")
        return get_defaults()

def get_defaults():
    """
    Backup settings in case the JSON file is broken or missing.
    """
    return {
        "identity": {"name": "Seven", "wake_words": ["seven"]},
        "brain": {"model_name": "llama3:8b-instruct-q4_K_M", "temperature": 0.3, "max_history": 10},
        "gui": {"opacity": 0.8, "text_color": "#00FF00"}
    }

# Load the config immediately when this script is imported
# This variable 'KEY' is what we will import in main.py
KEY = load_config()