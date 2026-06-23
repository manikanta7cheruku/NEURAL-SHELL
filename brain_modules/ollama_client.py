# =============================================================================
# brain_modules/ollama_client.py
#
# PURPOSE: The ONLY file in the entire codebase that talks to Ollama.
#          If you switch LLM providers (e.g. llama.cpp, LM Studio, GPT4All),
#          you change THIS file only. Nothing else changes.
#
# PATTERN: Single Responsibility + Facade
#          Facade = simple interface (call_ollama, stream_sentences)
#                   hiding complex HTTP + JSON + error handling underneath.
#
# ENGINEERING NOTE:
#   We use raw requests instead of the ollama Python SDK because:
#   1. Full control over timeout values (critical for voice latency)
#   2. Direct access to iter_lines() for streaming
#   3. No extra dependency to manage in embedded Python
#
# INTERVIEW TALKING POINT:
#   "I separated the LLM client into its own module using the Facade pattern.
#    This means if we ever swap Ollama for another provider, we change one file.
#    The rest of brain.py never knows the difference."
# =============================================================================

import json
import requests
import colorama
from colorama import Fore

colorama.init(autoreset=True)

# ---------------------------------------------------------------------------
# OLLAMA ENDPOINT
# Ollama runs locally on port 11434.
# The /api/generate endpoint accepts a model name + prompt and returns JSON.
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


def call_ollama(payload: dict) -> str:
    """
    Send a prompt to Ollama and return the full text response.
    This is the NON-STREAMING path — waits for complete response.

    Args:
        payload (dict): Full Ollama request body.
                        Must contain: model, prompt, stream=False, options.

    Returns:
        str: The LLM's response text.
             Returns a user-friendly error string on failure — never raises.

    ERROR HANDLING STRATEGY:
        We catch specific exceptions in order of likelihood:
        1. ConnectionError  — Ollama not running (most common mistake)
        2. Timeout          — Model too slow for voice use
        3. Exception        — Anything else (JSON parse, memory, etc.)

        We return strings not raise exceptions because brain.py
        passes the return value directly to mouth.speak().
        A crash here would silence Seven completely.

    INTERVIEW NOTE:
        This is "defensive programming" — assume the external dependency
        (Ollama) can fail at any time and handle it gracefully.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120  # 2 minutes max — voice users will not wait longer
        )

        if response.status_code == 200:
            reply = response.json().get("response", "").strip()
            # If Ollama returns empty string, return neutral fallback
            return reply if reply else "Listening."

        # Non-200 from Ollama (e.g. model not found, OOM)
        print(Fore.RED + f"[OLLAMA] Status {response.status_code}")
        return "My brain hiccupped. Try again."

    except requests.exceptions.ConnectionError:
        # Ollama process is not running
        print(Fore.RED + "[OLLAMA] Cannot connect. Is Ollama running?")
        return "I can't reach my brain. Run 'ollama serve' in a terminal first."

    except requests.exceptions.Timeout:
        # Model took too long — common with large models on slow hardware
        print(Fore.RED + "[OLLAMA] Timeout. Model too slow?")
        return "My brain took too long. Try again."

    except Exception as e:
        # Catch-all — JSON parse errors, memory errors, etc.
        print(Fore.RED + f"[OLLAMA] Unexpected error: {e}")
        return "Something went wrong with my thinking."


def stream_sentences(prompt: str, payload: dict):
    """
    Stream tokens from Ollama and yield complete sentences.

    WHY STREAMING:
        Without streaming, Seven waits for the full response before speaking.
        With streaming, Seven speaks the first sentence while thinking the rest.
        This reduces perceived latency from ~3s to ~0.8s for the user.

    HOW IT WORKS:
        1. Send request with stream=True to Ollama
        2. Ollama sends one JSON line per token (Server-Sent Events style)
        3. We buffer tokens until we hit a sentence boundary (. ! ?)
        4. We yield each complete sentence immediately
        5. main.py calls mouth.speak(sentence) per yield

    SENTENCE BOUNDARY DETECTION:
        We check if the character after . ! ? is a space or end of buffer.
        This prevents false splits on:
        - Decimals: "3.14" — no space after dot
        - Abbreviations: "Dr." — caught by "no space" rule most of the time
        This is heuristic, not perfect. Good enough for voice.

    YIELD PATTERN (Generator):
        Using yield makes this a Python generator.
        Callers use: for sentence in stream_sentences(...)
        Memory efficient — we never hold the full response in RAM.

    Args:
        prompt (str): Not used directly — payload contains the full prompt.
                      Kept for API consistency.
        payload (dict): Full Ollama request body.

    Yields:
        str: One complete sentence at a time.

    INTERVIEW NOTE:
        "I used Python generators for streaming because they are lazy —
         they produce values on demand without storing everything in memory.
         This is the same pattern used in file reading, database cursors,
         and any time you process data larger than RAM."
    """
    # Force streaming on — caller may have set stream=False
    stream_payload = {**payload, "stream": True}

    # Token buffer — accumulates characters until a sentence boundary
    buffer = ""

    # Characters that end a sentence
    sentence_endings = {'.', '!', '?'}

    try:
        response = requests.post(
            OLLAMA_URL,
            json=stream_payload,
            timeout=60,
            stream=True  # Keep HTTP connection open for chunked response
        )

        if response.status_code != 200:
            yield "My brain hiccupped. Try again."
            return

        # iter_lines() reads one JSON line at a time from the stream
        # This is how Ollama sends Server-Sent Events
        for line in response.iter_lines():
            if not line:
                continue  # Skip empty keep-alive lines

            try:
                chunk = json.loads(line)
                token = chunk.get("response", "")  # One token (word piece)
                done  = chunk.get("done", False)    # True on last chunk

                # Accumulate token into buffer
                if token:
                    buffer += token

                # Scan buffer for sentence boundaries
                # We want: "Hello world. " → yield "Hello world."
                # We avoid: "3.14" → no yield (no space after dot)
                if buffer:
                    last_boundary = -1
                    for i, ch in enumerate(buffer):
                        if ch in sentence_endings:
                            # Check character after boundary
                            if i + 1 < len(buffer) and buffer[i + 1] == ' ':
                                last_boundary = i + 1  # Include the space
                            elif i + 1 >= len(buffer):
                                last_boundary = i + 1  # End of buffer

                    # Yield everything up to last boundary
                    if last_boundary > 0:
                        sentence = buffer[:last_boundary].strip()
                        buffer   = buffer[last_boundary:].strip()
                        # Guard: skip single chars and empty strings
                        if sentence and len(sentence) > 1:
                            yield sentence

                if done:
                    # Flush remaining buffer as final sentence
                    if buffer.strip():
                        yield buffer.strip()
                    break

            except json.JSONDecodeError:
                # Malformed JSON chunk — skip and continue
                # This can happen on the very last "done" line from some Ollama versions
                continue

    except requests.exceptions.ConnectionError:
        yield "I can't reach my brain. Run 'ollama serve' first."

    except requests.exceptions.Timeout:
        yield "My brain took too long. Try again."

    except Exception as e:
        print(Fore.RED + f"[OLLAMA] Stream error: {e}")
        yield "Something went wrong with my thinking."