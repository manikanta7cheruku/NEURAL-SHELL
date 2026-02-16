"""
=============================================================================
PROJECT SEVEN - brain.py (The Intelligence)
Version: 1.1 (Smart Logic + Memory)
Version: 1.1.2 (Smart Logic + Memory + Mood + Polish)
Version: 1.2 (Smart Logic + Memory + Mood + Voice Identity)

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
import random
import config
import colorama
from colorama import Fore
from memory import seven_memory
from memory.mood import mood_engine
#from memory.core import seven_memory

colorama.init(autoreset=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = config.KEY['brain']['model_name']
CONVO_HISTORY = {}
USER_NAME = "Admin"
LAST_USER_INPUT = ""
RECENT_QUESTIONS = {}


def load_name_from_memory():
    """Load user's name from ChromaDB facts (single source of truth)."""
    global USER_NAME
    try:
        all_facts = seven_memory.user_facts.get()
        if all_facts and all_facts['documents']:
            for doc in all_facts['documents']:
                doc_lower = doc.lower()
                if "user's name is" in doc_lower or "user wants to be called" in doc_lower:
                    # Extract name from fact text
                    # "User's name is Mani" → "Mani"
                    if "name is" in doc_lower:
                        name = doc.split("is")[-1].strip().rstrip(".")
                    elif "called" in doc_lower:
                        name = doc.split("called")[-1].strip().rstrip(".")
                    else:
                        continue
                    if name and len(name) > 0:
                        USER_NAME = name
                        print(Fore.GREEN + f"[BRAIN] Loaded user name from memory: {USER_NAME}")
                        return
        print(Fore.YELLOW + "[BRAIN] No user name found in memory. Using default: Admin")
    except Exception as e:
        print(Fore.YELLOW + f"[BRAIN] Could not load name from memory: {e}")


def reset_session():
    """Clears session data when memory is wiped."""
    global RECENT_QUESTIONS, CONVO_HISTORY, USER_NAME
    RECENT_QUESTIONS = {}
    CONVO_HISTORY = {}
    USER_NAME = "Admin"


load_name_from_memory()


def think(prompt_text, speaker_id="default"):
    global CONVO_HISTORY, USER_NAME, LAST_USER_INPUT, RECENT_QUESTIONS

    # If we know who's speaking, use their name
    if speaker_id not in ("default", "unknown"):
        # Try to find this speaker's real name from memory
        speaker_name = speaker_id.title()  # Default: capitalize profile ID
        try:
            all_facts = seven_memory.user_facts.get(where={"user_id": speaker_id})
            if all_facts and all_facts['documents']:
                for doc in all_facts['documents']:
                    doc_lower = doc.lower()
                    if "name is" in doc_lower:
                        found_name = doc.split("is")[-1].strip().rstrip(".")
                        if found_name and len(found_name) > 0:
                            speaker_name = found_name
                            break
                    elif "called" in doc_lower:
                        found_name = doc.split("called")[-1].strip().rstrip(".")
                        if found_name and len(found_name) > 0:
                            speaker_name = found_name
                            break
        except:
            pass
    else:
        speaker_name = USER_NAME

    clean_in = prompt_text.lower().strip()
    clean_in = clean_in.replace("?", "").replace(".", "").replace("!", "").replace("'", "").replace(",", "")
    words = clean_in.split()

    # =========================================================================
    # LAYER 1: NAME SETTING (Must be absolute first)
    # =========================================================================
    # "My name is Mani" must save BEFORE any other check runs.
    # If we don't catch this first, "my name" triggers identity check instead.

    if "my name is" in clean_in:
        new_name = prompt_text.split("is")[-1].strip().rstrip(".")
        if speaker_id != "default" and speaker_id != "unknown":
            # Store name linked to this speaker's voice profile
            seven_memory.store_fact(f"Speaker {speaker_id}'s name is {new_name}", category="identity", user_id=speaker_id)
            speaker_name = new_name
        else:
            USER_NAME = new_name
            seven_memory.store_fact(f"User's name is {USER_NAME}", category="identity")
        return f"Understood. You are {new_name}."

       # =========================================================================
    # LAYER 2: REPETITION DETECTOR
    # =========================================================================

    # NEVER block commands — user might retry because first attempt failed
    first_word = words[0] if words else ""
    is_command = first_word in ["open", "close", "start", "kill", "launch"]
    is_greeting = first_word in ["hi", "hey", "hello", "bye", "goodbye", "good"]

    # Skip repetition for commands, greetings, AND requests
    is_request = any(w in clean_in for w in ["tell me", "show me", "give me", "sing", "explain", "open", "close"])
    
    speaker_questions = RECENT_QUESTIONS.get(speaker_id, [])
    if clean_in in speaker_questions and not is_command and not is_greeting and not is_request:

        # Identity questions have FIXED answers — no need to check memory
        # These answers NEVER change, so always block on repeat
        if "your name" in clean_in or "who are you" in clean_in:
            import random
            responses = [
                "Seven. Same as before.",
                "Still Seven.",
                "I'm Seven. That hasn't changed.",
                "Seven — same answer as last time.",
            ]
            return random.choice(responses)
        if "my name" in clean_in or "who am i" in clean_in:
            if speaker_id not in ("default", "unknown") and speaker_name == speaker_id.title():
                return "You haven't told me your name yet."
            import random
            responses = [
                f"You're {speaker_name}.",
                f"Still {speaker_name}.",
                f"{speaker_name}, same as before.",
                f"{speaker_name} — hasn't changed.",
            ]
            return random.choice(responses)
        if "what are you" in clean_in:
            return "Still Seven, your personal AI assistant."
        if "call you" in clean_in:
            return "Seven. Same as always."
        if "created you" in clean_in or "made you" in clean_in or "who made" in clean_in:
            creator = config.KEY['identity']['creator']
            import random
            responses = [
                f"{creator}. Same answer.",
                f"Still {creator}.",
                f"{creator} built me. That hasn't changed.",
                f"{creator} — my creator.",
            ]
            return random.choice(responses)

        # For NON-identity questions, check if new memories exist
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        fresh_memory = seven_memory.search(prompt_text, user_id=search_uid)
        if fresh_memory:
            # New info available — don't block, let LLM answer with memory
            memory_context = fresh_memory
            print(Fore.MAGENTA + "[MEMORY] Found NEW memories for repeated question!")
            print(Fore.MAGENTA + memory_context)
        else:
            repeat_count = speaker_questions.count(clean_in)

            if repeat_count >= 2:
                return "You've asked me this multiple times now. My answer hasn't changed."

            return "You just asked me that. Same answer."

    if not is_command and not is_greeting:
        if speaker_id not in RECENT_QUESTIONS:
            RECENT_QUESTIONS[speaker_id] = []
        RECENT_QUESTIONS[speaker_id].append(clean_in)
        if len(RECENT_QUESTIONS[speaker_id]) > 10:
            RECENT_QUESTIONS[speaker_id].pop(0)

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
            if speaker_id not in ("default", "unknown") and speaker_name == speaker_id.title():
                return "You haven't told me your name yet."
            return f"You are {speaker_name}."
        
    # --- FAREWELLS ---
    farewell_words = ["bye", "goodbye", "bye seven", "goodbye seven", "see you",
                      "see ya", "later", "good night", "goodnight"]
    if clean_in in farewell_words:
        return f"Later, {speaker_name}."

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
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        memory_context = seven_memory.search(prompt_text, user_id=search_uid)

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
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        seven_memory.extract_and_store_facts(prompt_text, user_id=search_uid)

    # =========================================================================
    # LAYER 7: LLM INFERENCE
    # =========================================================================

    if "VISUAL_REPORT:" not in prompt_text:
        if speaker_id not in CONVO_HISTORY:
            CONVO_HISTORY[speaker_id] = []
        CONVO_HISTORY[speaker_id].append(f"User: {prompt_text}")

    if len(CONVO_HISTORY.get(speaker_id, [])) > 4:
        CONVO_HISTORY[speaker_id] = CONVO_HISTORY[speaker_id][-4:]

    system_prompt = (
        f"You are {config.KEY['identity']['name']}, created by {config.KEY['identity']['creator']}. "
        f"You are currently talking to: {speaker_name}. "
        "You talk like Jarvis from Iron Man. Smart, warm, human. NOT a robot. "
        f"{mood_modifier} "

        "RULES: "
        "1. Keep responses to 1-2 sentences MAXIMUM. Be extremely concise. "
        "   If the answer is one word, say one word. "
        "   'What is my name?' → 'Rahul.' NOT a paragraph about it. "
        "2. NEVER ask follow-up questions. "
        "3. Talk like a HUMAN, not a machine. "
        "   BAD: 'Functioning within optimal parameters' or 'memory banks'. "
        "   GOOD: 'Doing good.' or 'I remember you mentioning that.' "
        "4. NEVER mention programming, parameters, banks, systems, or protocols. "
        "5. NEVER say 'Doing good' at the end of responses. "
        f"6. Facts about your creator: "
        f"   - Your creator is {config.KEY['identity']['creator']}. "
        f"   - {config.KEY['identity']['creator']} is the person/team who designed and built you. "
        f"   - You are Project Seven, built by {config.KEY['identity']['creator']}. "
        f"   - When asked about your creator, answer naturally using these facts. "
        f"   - Never say the exact same sentence twice about your creator. Vary your phrasing. "
        f"   You are currently speaking with {speaker_name}. Use their name naturally. "
        "7. When user asks 'can you open apps', say 'Yes, I can.' Do NOT output any tags. "
        "8. When user asks 'do you know me' and NO memories exist, say 'Not yet, but I am learning.' "
        "9. When user asks 'will you remember', say 'Everything we talk about stays with me.' "
        "10. You know these facts about YOURSELF: "
        "   - Your name is Seven. "
        f"   - You were created by {config.KEY['identity']['creator']}. "
        "   - You run 100 percent locally on the users PC. "
        "   - All data is stored locally. Nothing is sent to any cloud or server. "
        "   - You can open apps, close apps, remember conversations, and chat. "
        "11. When asked about your storage or privacy, explain you are fully local. "
        "12. For general knowledge questions (capital of France, science, math), answer directly and confidently. "
        "13. ONLY say 'You havent told me that' for questions about the USER PERSONALLY. "

        "MEMORY: "
        "1. If RECALLED MEMORIES section exists below, the answer IS in there. Use it. "
        "2. NEVER ignore recalled memories. State the fact clearly. "
        "3. NEVER invent facts about the USER. If no memories exist about the USER, say so. "
        "4. NEVER say 'football' if memory says 'chess'. READ the memory carefully. "

        "COMMANDS: "
        "ONLY output ###OPEN or ###CLOSE when users FIRST word is Open, Close, Start, Kill, Launch. "
        "'Open X' → '###OPEN: X' — nothing else. "
        "'Open X and Y' → '###OPEN: X ###OPEN: Y' — nothing else. "
        "'Close X' → '###CLOSE: X' — nothing else. "
        "'Close X and Y' → '###CLOSE: X ###CLOSE: Y' — nothing else. "
        "If first word is NOT a command verb, answer normally. NEVER output tags. "
        "'Can you open apps' → first word is 'can' → answer normally, no tags. "

        "TAGS: ###OPEN: [App] | ###CLOSE: [App] | ###LOOK"
    )

    full_prompt = system_prompt + "\n\n"

    if memory_context:
        full_prompt += memory_context + "\n\n"

    speaker_history = CONVO_HISTORY.get(speaker_id, [])
    full_prompt += "LOG:\n" + "\n".join(speaker_history) + "\nSeven:"

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 60,
            "repeat_penalty": 1.3,
            "stop": ["User:", "System:", "Seven:"]
        }
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=30)
        if r.status_code == 200:
            reply = r.json().get("response", "").strip()
            if not reply:
                reply = "Listening."

            if "VISUAL_REPORT:" not in prompt_text:
                if speaker_id not in CONVO_HISTORY:
                    CONVO_HISTORY[speaker_id] = []
                CONVO_HISTORY[speaker_id].append(f"Seven: {reply}")

            return reply
        else:
            print(Fore.RED + f"[BRAIN] Ollama returned status {r.status_code}")
            return "My brain hiccupped. Try again."
    except requests.exceptions.ConnectionError:
        print(Fore.RED + "[BRAIN] Cannot connect to Ollama. Is it running?")
        return "I can't reach my brain. Run 'ollama serve' in a terminal first."
    except requests.exceptions.Timeout:
        print(Fore.RED + "[BRAIN] Ollama took too long to respond.")
        return "My brain took too long. Try again."
    except Exception as e:
        print(Fore.RED + f"[BRAIN] Unexpected error: {e}")
        return "Something went wrong with my thinking."


def inject_observation(text):
    pass