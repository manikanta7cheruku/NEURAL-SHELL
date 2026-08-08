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


# Words that signal a live data query — memory is irrelevant for these.
_WEB_INTENT_WORDS = {
    "weather", "temperature", "forecast", "rain", "sunny", "humidity",
    "news", "latest", "breaking", "happened", "update",
    "price", "stock", "market", "crypto", "bitcoin",
    "score", "match", "who won", "game result",
    "trending", "viral", "right now", "currently",
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
}


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")
    config       = deps.get("config")

    if ("VISUAL_REPORT:" in ctx.prompt_text
            or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()

    # Skip memory for live data queries.
    _clean = ctx.clean_in.lower()
    if any(w in _clean for w in _WEB_INTENT_WORDS):
        print(Fore.CYAN + "[MEMORY] Skipping — live data query")
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
        ctx.memory_context = seven_memory.search(ctx.prompt_text, user_id=search_uid)
    except Exception as _mem_err:
        print(Fore.YELLOW + f"[BRAIN] Memory search skipped: {_mem_err}")

    if ctx.memory_context:
        print(Fore.MAGENTA + "[MEMORY] Found relevant memories!")

    return LayerResult.pass_through()