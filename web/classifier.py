"""
=============================================================================
PROJECT SEVEN - web/classifier.py (Search Classifier)
Version: 1.4

PURPOSE:
    Decides if a user query needs live web search or can be answered
    from local knowledge (LLM + memory).
    
    Uses keyword detection (fast, no LLM call needed).
    
LOGIC:
    - Time-sensitive words → SEARCH (weather, today, latest, current, now)
    - Real-time data words → SEARCH (price, score, stock, trending)
    - News words → SEARCH (news, happened, update)
    - Personal questions → NO SEARCH (about the user, Seven, memory)
    - Commands → NO SEARCH (open, close, launch)
    - General knowledge → NO SEARCH (LLM knows it)
=============================================================================
"""

# Words that signal the user wants LIVE/CURRENT information
TIME_SENSITIVE = [
    "today", "right now", "currently", "latest", "recent",
    "this week", "this month", "this year", "yesterday",
    "tomorrow", "tonight"
]

REALTIME_DATA = [
    "weather", "temperature", "forecast",
    "price", "stock", "market", "crypto", "bitcoin",
    "score", "match", "game result", "who won",
    "trending", "viral", "popular right now"
]

NEWS_WORDS = [
    "news", "happened", "breaking", "announcement",
    "released", "launched", "died", "elected",
    "war", "earthquake", "disaster"
]

SEARCH_TRIGGERS = [
    "search for", "search about", "look up", "google",
    "find out", "search online", "what is the latest",
    "tell me about the latest", "whats happening"
]

# Words that mean we should NOT search
NO_SEARCH_TRIGGERS = [
    "my name", "your name", "who are you", "who am i",
    "remember", "you know", "i told you", "my favorite",
    "open", "close", "launch", "start", "kill",
    "how are you", "thank you", "hello", "hi", "bye",
    "introduce yourself", "what can you do", "what you can do",
    "tell me what you", "your capabilities", "what are you",
    "you won't", "you wont", "can you", "do you",
    "will you", "are you able"
]


def needs_web_search(user_input):
    """
    Determine if a query needs live web search.
    
    Args:
        user_input: raw user text
        
    Returns:
        tuple: (needs_search: bool, search_query: str or None)
    """
    clean = user_input.lower().strip()
    clean = clean.replace("?", "").replace(".", "").replace("!", "").replace("'", "")
    
    # RULE 1: Never search for personal/identity/command queries
    for trigger in NO_SEARCH_TRIGGERS:
        if trigger in clean:
            return False, None
    
    # RULE 2: Explicit search request
    for trigger in SEARCH_TRIGGERS:
        if trigger in clean:
            # Extract the actual search query
            query = clean
            for t in SEARCH_TRIGGERS:
                query = query.replace(t, "").strip()
            if not query:
                query = clean
            return True, query
    
    # RULE 3: Time-sensitive keywords
    for word in TIME_SENSITIVE:
        if word in clean:
            return True, clean
    
    # RULE 4: Real-time data keywords
    for word in REALTIME_DATA:
        if word in clean:
            return True, clean
    
    # RULE 5: News keywords
    for word in NEWS_WORDS:
        if word in clean:
            return True, clean
    
    # RULE 6: "What is [specific thing]" that LLM might not know
    # Questions about specific people, companies, events after 2023
    specific_indicators = [
        "who is", "what is", "where is",
        "how much", "how many", "when did", "when will",
        "is it true", "did they", "has the"
    ]
    
    # Only trigger if combined with a proper noun hint or specific detail
    for indicator in specific_indicators:
        if clean.startswith(indicator):
            # Check if it's a general knowledge question LLM can handle
            general_knowledge = [
                "python", "java", "programming", "math", "science",
                "history", "geography", "capital", "continent",
                "planet", "element", "formula", "equation"
            ]
            is_general = any(gk in clean for gk in general_knowledge)
            if not is_general:
                # Might need search — but don't force it
                # Return True only if also has time-sensitive context
                pass
    
    return False, None