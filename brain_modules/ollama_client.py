"""
brain_modules/ollama_client.py
High performance client for Ollama API using /api/chat.
Optimized for local system latency.
"""

import json
import requests
from colorama import Fore
import config

OLLAMA_HOST = "http://127.0.0.1:11434"


def get_current_model() -> str:
    """Return configured or auto-selected model identifier."""
    try:
        from brain_modules.model_selector import select_best_model
        return select_best_model()
    except Exception:
        return config.KEY.get("brain_model", "llama3.2:3b")


def chat(messages: list, stream: bool = False, num_predict: int = 50, temperature: float = 0.7):
    """
    Core /api/chat client for Ollama.
    Yields text tokens if stream is True, returns full string if False.
    """
    model = get_current_model()
    url = f"{OLLAMA_HOST}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
            "top_p": 0.9,
            "stop": ["<|eot_id|>", "<|start_header_id|>", "\nUser:", "\nAssistant:"]
        }
    }

    try:
        if stream:
            return _stream_chat(url, payload)
            
        response = requests.post(url, json=payload, timeout=15.0)
        if response.status_code == 200:
            data = response.json()
            return data.get("message", {}).get("content", "").strip()
        else:
            print(Fore.RED + f"[OLLAMA] Chat failed with code {response.status_code}")
            return ""
    except Exception as e:
        print(Fore.RED + f"[OLLAMA] Chat network error: {e}")
        return ""


def _stream_chat(url: str, payload: dict):
    """Internal generator to stream chat responses token-by-token."""
    try:
        response = requests.post(url, json=payload, stream=True, timeout=10.0)
        if response.status_code != 200:
            print(Fore.RED + f"[OLLAMA] Stream chat failed: status {response.status_code}")
            yield ""
            return

        for line in response.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line.decode("utf-8"))
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done", False):
                    break
            except Exception:
                continue
    except Exception as e:
        print(Fore.RED + f"[OLLAMA] Stream exception: {e}")
        yield ""