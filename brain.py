"""
=============================================================================
PROJECT SEVEN - brain.py (The Intelligence)
Version: 1.1 (Smart Logic + Memory)

LAYER ORDER (Critical):
    Layer 1: Name SETTING ("My name is Mani") — must be first
    Layer 2: Repetition detector — catches repeated questions
    Layer 3: Identity overrides — keyword detection for name questions
    Layer 4: Input classification — command vs question vs chat
    Layer 5: Memory search — only for questions
    Layer 6: Fact extraction — learns from user
    Layer 7: LLM inference — handles everything else
=============================================================================
"""

import requests
import json
import os
import config
import colorama
from colorama import Fore
from memory import seven_memory
from memory.mood import mood_engine
from memory.core import seven_memory

colorama.init(autoreset=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = config.KEY['brain']['model_name']
MEMORY_FILE = "memory.json"

CONVO_HISTORY = []
USER_NAME = "Admin"
LAST_USER_INPUT = ""
RECENT_QUESTIONS = []


def load_memory():
    global USER_NAME
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                data = json.load(f)
                USER_NAME = data.get("name", "Admin")
        except:
            pass


def save_memory():
    with open(MEMORY_FILE, 'w') as f:
        json.dump({"name": USER_NAME}, f, indent=4)


def reset_session():
    """Clears session data when memory is wiped."""
    global RECENT_QUESTIONS, CONVO_HISTORY
    RECENT_QUESTIONS = []
    CONVO_HISTORY = []


load_memory()


def think(prompt_text):
    global CONVO_HISTORY, USER_NAME, LAST_USER_INPUT, RECENT_QUESTIONS

    clean_in = prompt_text.lower().strip()
    clean_in = clean_in.replace("?", "").replace(".", "").replace("!", "").replace("'", "").replace(",", "")
    words = clean_in.split()

    # =========================================================================
    # LAYER 1: NAME SETTING (Must be absolute first)
    # =========================================================================
    # "My name is Mani" must save BEFORE any other check runs.
    # If we don't catch this first, "my name" triggers identity check instead.

    if "my name is" in clean_in:
        USER_NAME = prompt_text.split("is")[-1].strip().rstrip(".")
        save_memory()
        seven_memory.store_fact(f"User's name is {USER_NAME}", category="identity")
        return f"Understood. You are {USER_NAME}."

       # =========================================================================
    # LAYER 2: REPETITION DETECTOR
    # =========================================================================

    # NEVER block commands — user might retry because first attempt failed
    first_word = words[0] if words else ""
    is_command = first_word in ["open", "close", "start", "kill", "launch"]
    is_greeting = first_word in ["hi", "hey", "hello", "bye", "goodbye", "good"]

        # Skip repetition for commands, greetings, AND requests
    is_request = any(w in clean_in for w in ["tell me", "show me", "give me", "sing", "explain"])
    
    if clean_in in RECENT_QUESTIONS and not is_command and not is_greeting and not is_request:

        
        # Before blocking, check if NEW memories exist that could change the answer
        fresh_memory = seven_memory.search(prompt_text)
        if fresh_memory:
            # New info available — don't block, let LLM answer with memory
            memory_context = fresh_memory
            print(Fore.MAGENTA + "[MEMORY] Found NEW memories for repeated question!")
            print(Fore.MAGENTA + memory_context)
        else:
            repeat_count = RECENT_QUESTIONS.count(clean_in)

            if repeat_count >= 2:
                return "You've asked me this multiple times now. My answer hasn't changed."

            if "your name" in clean_in or "who are you" in clean_in:
                return "Still Seven. That hasn't changed."
            if "my name" in clean_in or "who am i" in clean_in:
                return f"Still {USER_NAME}, last I checked."

            return "You just asked me that. Same answer."

    if not is_command and not is_greeting:
        RECENT_QUESTIONS.append(clean_in)
        if len(RECENT_QUESTIONS) > 10:
            RECENT_QUESTIONS.pop(0)

    # =========================================================================
    # LAYER 3: IDENTITY OVERRIDES (Smart Keyword Detection)
    # =========================================================================
    # Only reaches here on FIRST time asking. Repeats caught above.
    # Uses keyword detection — not exact matching.
    # Skips to LLM if question is ABOUT names but not asking directly.

    # --- USER ASKING SEVEN'S NAME ---
    # "What's your name?" / "Tell me your name" / "Who are you?"
    # BUT NOT: "How many times did I ask your name?" → LLM handles
    if "your name" in clean_in:
        if len(words) <= 6 and "how" not in clean_in and "did" not in clean_in:
            return "I am Seven. You can call me Seven."

    if clean_in == "who are you":
        return "I am Seven, your personal AI assistant."

    # --- USER ASKING THEIR NAME ---
    # "What's my name?" / "Do you know my name?"
    # BUT NOT: "What is my friend's name?" / "How many times did I ask my name?"
    if "my name" in clean_in or "who am i" in clean_in:
        is_direct = (
            "is" not in clean_in
            and "how many" not in clean_in
            and "why" not in clean_in
            and "did" not in clean_in
            and "times" not in clean_in
            and "about" not in clean_in
            and "friend" not in clean_in
        )
        if is_direct:
            return f"You are {USER_NAME}."
        
    # --- FAREWELLS ---
    farewell_words = ["bye", "goodbye", "bye seven", "goodbye seven", "see you",
                      "see ya", "later", "good night", "goodnight"]
    if clean_in in farewell_words:
        return "Later, Mani."

    # --- WHAT ARE YOU ---
    if clean_in == "what are you":
        return "I am Seven, your personal AI assistant."

    # --- WHAT SHOULD I CALL YOU ---
    if "call you" in clean_in or "should i call" in clean_in:
        return "You can call me Seven."
    

     # --- USER TEACHING A FACT (acknowledge it, don't parrot it back) ---
    # "I love cricket" should get "Nice, I'll remember that." not "You play cricket."
    # teaching_triggers = ["i love", "i like", "i prefer", "my favorite", "my favourite",
    #                      "i work", "i study", "i am a", "i am an", "remember that"]
    # if any(trigger in clean_in for trigger in teaching_triggers):
    #     seven_memory.extract_and_store_facts(prompt_text)
    #     return "Noted. I'll remember that."

    
    # =========================================================================
    # LAYER 4: MOOD ANALYSIS (NEW IN V1.1.1)
    # =========================================================================
    mood_engine.analyze_input(prompt_text)
    mood_modifier = mood_engine.get_mood_prompt_modifier()

    # =========================================================================
    # LAYER 5: MEMORY SEARCH (Questions/Chat only — not commands)
    # =========================================================================

    memory_context = ""

    # Skip memory for commands, greetings, and farewells
    is_greeting = first_word in ["hi", "hey", "hello", "bye", "goodbye"]

    if "VISUAL_REPORT:" not in prompt_text and not is_command and not is_greeting:
        memory_context = seven_memory.search(prompt_text)
        if memory_context:
            print(Fore.MAGENTA + "[MEMORY] Found relevant memories!")
            print(Fore.MAGENTA + memory_context)

            


    # =========================================================================
    # LAYER 5.5: NO-MEMORY QUESTION HANDLER
    # =========================================================================
    # Only catches questions about the USER PERSONALLY when no memories exist.
    # "What sport do I play?" → personal question → needs memory
    # "Tell me a joke" → NOT a personal question → let LLM handle
    
    personal_question_words = ["my", "about me", "do i", "did i", "am i",
                               "i like", "i love", "i play", "i work", "i study"]
    is_personal_question = any(w in clean_in for w in personal_question_words)
    
    question_starts = ["what", "which", "who", "when", "where", "how", "do you know"]
    is_question = any(clean_in.startswith(w) for w in question_starts)
    
    if is_question and is_personal_question and not memory_context and not is_command:
        return "You haven't told me that yet."

    # =========================================================================
    # LAYER 6: FACT EXTRACTION (Meaningful input only — not commands)
    # =========================================================================

    if "VISUAL_REPORT:" not in prompt_text and not is_command and not is_greeting:
        seven_memory.extract_and_store_facts(prompt_text)

    # =========================================================================
    # LAYER 7: LLM INFERENCE
    # =========================================================================

    if "VISUAL_REPORT:" not in prompt_text:
        CONVO_HISTORY.append(f"User: {prompt_text}")

    if len(CONVO_HISTORY) > 4:
        CONVO_HISTORY = CONVO_HISTORY[-4:]

    system_prompt = (
        f"You are {config.KEY['identity']['name']}, created by {USER_NAME}. User: {USER_NAME}. "
        "You talk like Jarvis from Iron Man. Smart, warm, human. NOT a robot. "
        f"{mood_modifier} "

        "RULES: "
        "1. Keep responses to 1-2 sentences max. "
        "2. NEVER ask follow-up questions. "
        "3. Talk like a HUMAN, not a machine. "
        "   BAD: 'Functioning within optimal parameters' or 'memory banks'. "
        "   GOOD: 'Doing good.' or 'I dont have that info yet.' "
        "4. NEVER mention programming, parameters, banks, systems, or protocols. "
                f"5. You were created by {USER_NAME}. When asked about your creator, origin, or inventor, mention {USER_NAME} naturally. Never say the same sentence twice. "
        "6. When user asks 'can you open apps', say 'Yes, I can.' Do NOT output any tags. "
        "7. When user asks 'do you know me' and NO memories exist, say 'Not yet, but I am learning.' "
        "8. When user asks 'will you remember', say 'Everything we talk about stays with me.' "
         "9. You know these facts about YOURSELF: "
        "   - Your name is Seven. "
        f"   - You were created by {USER_NAME}. "
        "   - You run 100 percent locally on the users PC. "
        "   - All data is stored locally. Nothing is sent to any cloud or server. "
        "   - You can open apps, close apps, remember conversations, and chat. "
        "10. When asked about your storage or privacy, explain you are fully local. "

        "MEMORY: "
        "1. If RECALLED MEMORIES section exists below, the answer IS in there. Use it. "
        "2. NEVER ignore recalled memories. State the fact clearly. "
        "3. NEVER invent facts. If no memories exist about the topic, say so. "
        "4. NEVER say 'football' if memory says 'chess'. READ the memory carefully. "

        "COMMANDS: "
        "ONLY output ###OPEN or ###CLOSE when users FIRST word is Open, Close, Start, Kill, Launch. "
        "'Open X' → '###OPEN: X' — nothing else. "
        "'Open X and Y' → '###OPEN: X ###OPEN: Y' — nothing else. "
        "'Close X' → '###CLOSE: X' — nothing else. "
        "If first word is NOT a command verb, answer normally. NEVER output tags. "
        "'Can you open apps' → first word is 'can' → answer normally, no tags. "

        "TAGS: ###OPEN: [App] | ###CLOSE: [App] | ###LOOK"
    )

    full_prompt = system_prompt + "\n\n"

    if memory_context:
        full_prompt += memory_context + "\n\n"

    full_prompt += "LOG:\n" + "\n".join(CONVO_HISTORY) + "\nSeven:"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 50,
            "repeat_penalty": 1.3,
            "stop": ["User:", "System:", "Seven:"]
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload)
        if r.status_code == 200:
            reply = r.json().get("response", "").strip()
            if not reply:
                reply = "Listening."

            if "VISUAL_REPORT:" not in prompt_text:
                CONVO_HISTORY.append(f"Seven: {reply}")

            return reply
    except:
        return "Error."


def inject_observation(text):
    pass