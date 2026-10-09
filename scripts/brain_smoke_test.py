"""
scripts/brain_smoke_test.py

Live check against a running Seven (python main.py, or npm run dev).
Measures time to first streamed token and prints each reply.

    python scripts/brain_smoke_test.py
"""

import json
import sys
import time

import requests

URL = "http://127.0.0.1:7777/api/chat"
SCENARIOS = [
    ("1. Greeting", "Hey"),
    ("2a. Hello", "Hello"), ("2b. Hello", "Hello"), ("2c. Hello", "Hello"), ("2d. Hello", "Hello"),
    ("3. Creator", "Who created you?"),
    ("4. Remember", "Remember that my favorite framework is React."),
    ("5. Recall", "What is my favorite framework?"),
    ("6. Weather", "What's the weather in Rio?"),
    ("7. Chat", "Explain what a hash map is in two sentences."),
    ("8. Time", "what time is it"),
]


def ask(text):
    start, first, parts = time.time(), None, []
    with requests.post(URL, json={"text": text, "stream": True}, stream=True, timeout=120) as r:
        for line in r.iter_lines():
            if not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                break
            try:
                obj = json.loads(payload)
            except ValueError:
                continue
            if obj.get("token"):
                if first is None:
                    first = int((time.time() - start) * 1000)
                parts.append(obj["token"])
    return "".join(parts).strip(), first, int((time.time() - start) * 1000)


def main():
    try:
        requests.get("http://127.0.0.1:7777/api/health", timeout=3)
    except Exception:
        print("Seven is not running on port 7777.")
        sys.exit(1)
    for label, text in SCENARIOS:
        reply, first, total = ask(text)
        print(f"{label:<14} first token {first} ms | total {total} ms\n   you:   {text}\n   seven: {reply}\n")


if __name__ == "__main__":
    main()
