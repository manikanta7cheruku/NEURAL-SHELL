"""
=============================================================================
LAYER 5: MEMORY SEARCH

Searches ChromaDB for relevant past conversations and facts.
Writes results to ctx.memory_context, which LLM layer includes in prompt.

Skips for: commands, greetings, action commands, visual reports.
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


# Words that signal a live data query or conversational intent where memory search is invalid.
_WEB_INTENT_WORDS = {
    "weather", "temperature", "forecast", "rain", "sunny", "humidity",
    "news", "latest", "breaking", "happened", "update",
    "price", "stock", "market", "crypto", "bitcoin",
    "score", "match", "who won", "game result",
    "trending", "viral", "right now", "currently",
}

_CONVERSATIONAL_INTENTS = {
    "hi", "hello", "hey", "sup", "how are you", "how r u", "how you doing",
    "where are you", "where do you", "who are you", "what are you",
    "thanks", "thank you", "ok", "okay", "cool", "nice", "good job",
    "bye", "goodbye", "see ya", "good night", "good morning",
    "hola", "yo", "greetings", "morning", "afternoon", "evening",
    "yes", "no", "yep", "nope", "sure", "nah", "indeed", "correct",
}


# Self-knowledge tokens and phrases - answered by layer_03_identity from self_model.
# If any of these appear, skip memory search entirely.
# Memory contamination on these questions causes the LLM to confabulate
# system facts from unrelated past conversations.
_SELF_ENTITIES = {
    "version", "build", "release", "patch",
    "model", "llm", "llama",
    "hardware", "specs", "specifications", "ram", "gpu", "cpu", "vram", "processor",
}

_SELF_KNOWLEDGE_PHRASES = {
    "who are you", "what are you", "your name", "who made you", "who created you",
    "what can you do", "what do you do", "your capabilities", "what are your features",
    "tell me about yourself", "introduce yourself", "how can you help",
    "what is my name", "whats my name", "what's my name", "my name",
    "who am i", "do you know me", "do you remember me",
    "where are you from", "where you from", "where do you live",
    "where are you", "where do you run", "where are you hosted",
}

# Opinion question starters — Seven should form a fresh view.
# Injecting memory about past conversations on the same topic
# causes the LLM to defer to recalled context instead of reasoning.
_OPINION_STARTERS = {
    "what do you think", "what do you think about",
    "what are your thoughts", "what is your opinion",
    "what is your take", "how do you feel about",
    "do you think", "do you believe", "do you agree",
    "your view on", "your opinion on", "your thoughts on",
    "would you say", "would you recommend",
    "is it worth", "should i",
    "where do you think", "where would you",
    "where do you want", "where would you like",
    "what would you", "if you could", "if you were",
    "would you rather", "do you prefer", "do you like",
    "what is your favorite", "what is your favourite",
    "what do you enjoy", "what do you hate",
    "what do you love", "what do you dislike",
}


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")
    config       = deps.get("config")

    if ("VISUAL_REPORT:" in ctx.prompt_text
            or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()

    # Skip memory for live data and conversational pleasantries.
    _clean = ctx.clean_in.lower().strip()
    if _clean in _CONVERSATIONAL_INTENTS or any(_clean.startswith(c) for c in _CONVERSATIONAL_INTENTS):
        return LayerResult.pass_through()

    # Skip memory search for short conversational noise (under 2 words)
    # unless it matches some specific search keywords.
    tokens = [t for t in _clean.split() if t]
    if len(tokens) <= 1 and not (tokens and tokens[0] in {"react", "docker", "python", "kubernetes", "git"}):
        print(Fore.CYAN + "[MEMORY] Skipping — ultra-short query, treating as conversational noise")
        return LayerResult.pass_through()

    if any(w in _clean for w in _WEB_INTENT_WORDS):
        print(Fore.CYAN + "[MEMORY] Skipping — live data query")
        return LayerResult.pass_through()

    #Skip memory for self-knowledge queries.
    # These are answered from programmatic self_model, never from ChromaDB.
    clean_tokens = set(_clean.split())
    if (clean_tokens & _SELF_ENTITIES) or any(p in _clean for p in _SELF_KNOWLEDGE_PHRASES):
        print(Fore.CYAN + "[MEMORY] Skipping - self-knowledge query, using ground truth")
        return LayerResult.pass_through()

    # Skip memory for opinion questions.
    # Seven should reason fresh, not defer to recalled past conversations.
    # Memory about past discussions on the topic contaminates the opinion.
    if any(_clean.startswith(op) or op in _clean for op in _OPINION_STARTERS):
        print(Fore.CYAN + "[MEMORY] Skipping — opinion question, fresh reasoning preferred")
        return LayerResult.pass_through()

    search_uid = (
        ctx.speaker_id if ctx.speaker_id not in ("default", "unknown")
        else config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
    )

    try:
        raw_memory = seven_memory.search(ctx.prompt_text, user_id=search_uid)
        if raw_memory and raw_memory.strip():
            # Quiet wrapper. Weak local models will parrot loud framing tokens.
            # Facts are exposed as bullet list, not tagged blocks.
            ctx.memory_context = (
                "What you know about the user:\n"
                + raw_memory
            )
            print(Fore.MAGENTA + "[MEMORY] Found relevant memories!")
    except Exception as _mem_err:
        print(Fore.YELLOW + f"[BRAIN] Memory search skipped: {_mem_err}")

    return LayerResult.pass_through()