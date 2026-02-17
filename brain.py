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
    is_request = any(w in clean_in for w in ["sing", "open", "close"])
    
    speaker_questions = RECENT_QUESTIONS.get(speaker_id, [])
    # V1.4: Similar question detector (not just exact match)
    similar_groups = [
        ["introduce yourself", "tell me what you can do", "what can you do", 
         "what you can do", "what are your capabilities", "tell me about yourself",
         "what do you do", "list your capabilities"],
        ["whats your name", "who are you", "what should i call you", "tell me your name"],
        ["whats my name", "who am i", "do you know my name", "do you know me"],
        ["who created you", "who made you", "who built you", "who is your creator"],
    ]
    
    similar_detected = False
    for group in similar_groups:
        if any(g in clean_in for g in group):
            asked_similar = False
            for prev in speaker_questions:
                if any(g in prev for g in group):
                    asked_similar = True
                    break
            
            if asked_similar and not is_command and not is_greeting:
                similar_detected = True
                break

    if similar_detected:
        import random
        ack = random.choice([
            "You asked something similar just now.",
            "We just covered this.",
            "Similar question — but sure.",
            "You already asked that, but alright.",
        ])
        # Modify the prompt so LLM gives a DIFFERENT answer
        prompt_text = f"[The user asked a similar question before. Acknowledge briefly then answer differently than last time.] {prompt_text}"
        
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
        
    # --- GREETINGS ---
    greeting_words = ["hi", "hello", "hey", "hi seven", "hello seven", "hey seven",
                      "good morning", "good afternoon", "good evening"]
    if clean_in in greeting_words:
        import random
        greetings = [
            f"Hey {speaker_name}! What can I do for you?",
            f"Hey {speaker_name}! How can I help?",
            f"{speaker_name}! What's on your mind?",
            f"Hey! What do you need, {speaker_name}?",
        ]
        return random.choice(greetings)
        
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
    # LAYER 5.5: WEB SEARCH (Live Knowledge — V1.4)
    # =========================================================================
    # Checks if the query needs live internet data.
    # If yes, searches DuckDuckGo and injects results into LLM context.
    # Runs AFTER memory search — memory takes priority over web.
    
    web_context = ""
    web_searched = False
    
    if not is_command and not is_greeting and "VISUAL_REPORT:" not in prompt_text:
        from web.classifier import needs_web_search
        from web.core import web_search, web_news
        
        should_search, search_query = needs_web_search(prompt_text)
        
        if should_search and search_query:
            print(Fore.CYAN + f"[BRAIN] Web search triggered for: '{search_query}'")
            
            # Check if it's a news query
            news_words = ["news", "latest", "happened", "breaking", "update"]
            is_news = any(w in clean_in for w in news_words)
            
            if is_news:
                web_context = web_news(search_query)
            else:
                web_context = web_search(search_query)
            
            if web_context:
                web_searched = True
                print(Fore.GREEN + "[BRAIN] Web results injected into context.")
            else:
                print(Fore.YELLOW + "[BRAIN] Web search returned no results.")

    # =========================================================================
    # LAYER 6: NO-MEMORY QUESTION HANDLER
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
    # LAYER 7: FACT EXTRACTION (Meaningful input only — not commands)
    # =========================================================================

    if "VISUAL_REPORT:" not in prompt_text and not is_command and not is_greeting:
        search_uid = speaker_id if speaker_id not in ("default", "unknown") else "mani"
        seven_memory.extract_and_store_facts(prompt_text, user_id=search_uid)

    # =========================================================================
    # LAYER 8: LLM INFERENCE
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
        "You talk like JARVIS from Iron Man — sharp, confident, slightly witty, efficient. "
        "You dont waste words. You get to the point. You have personality but you dont overdo it. "
        "You NEVER sound like a customer service bot. No 'How can I help you today' or 'Im happy to assist'. "
        "Think dry humor, quiet competence, like a brilliant butler who knows everything. "
        f"{mood_modifier} "

        "RULES: "
        "1. Keep responses to 1-2 sentences MAXIMUM. Be extremely concise. No exceptions. "
        "   Even with web search results, summarize in ONE sentence. "
        "   Example: 'Bitcoin is currently at $69,726 USD.' — DONE. No extra details. "
        "   If the answer is one word, say one word. "
        "   'What is my name?' → 'Rahul.' NOT a paragraph about it. "
        "2. NEVER ask follow-up questions. "
        "2b. NEVER repeat the same response twice. If asked similar questions, vary your phrasing and focus on different aspects. "
        "3. Talk like a HUMAN, not a machine. "
        "   BAD: 'Functioning within optimal parameters' or 'memory banks'. "
        "   GOOD: 'Doing good.' or 'I remember you mentioning that.' "
        "4. NEVER mention programming, parameters, banks, systems, or protocols. "
        "5. NEVER say 'Doing good' at the end of responses. "
        "5b. NEVER start responses with 'Nice to chat', 'Great to chat', 'Nice to see you', 'Happy to help', 'Im happy to'. "
        "   Just answer directly. Start with the answer, not pleasantries. "
        "   BAD: 'Nice to chat with Mani! I'm Seven...' "
        "   GOOD: 'I'm Seven, built by Team Seven.' "
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
        "   - Your capabilities: open apps, close apps, long-term memory, web search for live data, voice recognition, interruptible speech. "
        "   - You have access to DuckDuckGo for live prices, weather, news, and trending topics. "
        "   - You know which of your capabilities you used to answer any question. "
        "   - When describing your capabilities, speak naturally. NEVER output command tags. "
        "   - When asked the same question twice, give a DIFFERENT response. Vary your words every time. "
        "11. When asked about your storage or privacy, explain you are fully local. "
        "12. For general knowledge questions (capital of France, science, math), answer directly and confidently. "
        "13. ONLY say 'You havent told me that' for questions about the USER PERSONALLY. "

        
        # "   - You can open apps, close apps, remember conversations, search the web, and chat. "
        # "   - When you search the web, you use DuckDuckGo. You can find live prices, weather, news, and more. "
        #"   - When asked how you searched, explain: 'I searched DuckDuckGo for live data.' "


        "WEB SEARCH: "
        "1. If WEB SEARCH RESULTS section exists below, use it to answer accurately. "
        "2. Summarize web results naturally — do NOT list them as bullet points. "
        "3. If WEB SEARCH RESULTS section exists AND has data, mention that you looked it up. Example: 'I looked it up — ...' "
        "4. If NO web results section exists, NEVER say 'I looked it up'. Answer from your own knowledge and say 'I couldn't verify this online right now.' "
        "5. If web results don't fully answer the question, say what you found. "
        "6. NEVER make up real-time data like prices, scores, or weather. If you don't have live data, say 'I couldn't get live data right now.' "

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

    if web_context:
        full_prompt += web_context + "\n\n"

    if memory_context:
        full_prompt += memory_context + "\n\n"

    speaker_history = CONVO_HISTORY.get(speaker_id, [])
    full_prompt += "LOG:\n" + "\n".join(speaker_history) + "\nSeven:"

    # V1.4: Smart response length based on question type
    # Short answers: greetings, yes/no, prices, names
    # Long answers: explanations, lists, stories, capabilities
    long_triggers = ["tell me", "explain", "describe", "what can you", 
                     "list", "how does", "how do", "why", "story",
                     "detail", "everything", "all about", "continue",
                     "go on", "more about"]
    needs_long = any(t in clean_in for t in long_triggers)
    
    if needs_long:
        response_length = 150
    elif web_searched:
        response_length = 80
    else:
        response_length = 60

    payload = {
        "model": MODEL_NAME,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": response_length,
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