"""
=============================================================================
LAYER 5.3: KNOWLEDGE BASE SEARCH

Searches local knowledge base (indexed PDFs, docs, etc) for factual queries.
Writes results to ctx.knowledge_context.

Skips for: personal questions, commands, greetings.
Only runs if memory_context is empty (memory has priority).
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


_KNOWLEDGE_TRIGGERS = [
    "what is", "what are", "who is", "who was", "who were",
    "explain", "define", "how does", "how do", "how is",
    "tell me about", "what does", "meaning of", "describe",
    "history of", "why is", "why do", "why does", "when was",
    "when did", "where is", "where was", "difference between"
]

_PERSONAL_WORDS = ["my", "i ", "me ", "about me", "do i", "am i"]


def process(ctx, deps):
    if (ctx.is_command or ctx.is_greeting or ctx.is_action_cmd
            or "VISUAL_REPORT:" in ctx.prompt_text):
        return LayerResult.pass_through()

    is_knowledge_q = any(t in ctx.clean_in for t in _KNOWLEDGE_TRIGGERS)
    is_personal    = any(w in ctx.clean_in for w in _PERSONAL_WORDS)

    if not is_knowledge_q or is_personal or ctx.memory_context:
        return LayerResult.pass_through()

    try:
        from knowledge import search_knowledge
        ctx.knowledge_context = search_knowledge(ctx.prompt_text)
        if ctx.knowledge_context:
            print(Fore.CYAN + "[BRAIN] Knowledge base results found!")
    except ImportError:
        pass
    except Exception as e:
        print(Fore.YELLOW + f"[BRAIN] Knowledge search error: {e}")

    return LayerResult.pass_through()