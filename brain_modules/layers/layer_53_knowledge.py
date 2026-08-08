"""
=============================================================================
LAYER 5.3: KNOWLEDGE BASE SEARCH

Searches local knowledge base (indexed PDFs, docs, etc) for factual queries.
Writes results to ctx.knowledge_context.

v2.0: Removed over-aggressive gate conditions.
      Now searches KB for any non-trivial question when KB has content.
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


# Phrases that explicitly reference uploaded documents
_DOC_TRIGGERS = [
    "in this", "in the file", "in the document", "in the pdf",
    "from the file", "from the document", "uploaded", "indexed",
    "what does it", "what does the", "summarize", "summary",
    "what is in", "what are in", "contents of", "content of",
    "explain this", "explain the", "what's in",
]

# Hard skip — these are clearly not knowledge questions
_HARD_SKIP = [
    "open ", "close ", "play ", "pause ", "mute",
    "volume", "brightness", "remind me", "schedule",
    "what time", "what day", "weather",
]


def process(ctx, deps):
    # Always skip commands and greetings
    if (ctx.is_command or ctx.is_greeting or ctx.is_action_cmd
            or "VISUAL_REPORT:" in ctx.prompt_text):
        return LayerResult.pass_through()

    # Skip short inputs — arithmetic, one-liners, simple factual questions
    # that have nothing to do with uploaded documents.
    # Minimum 5 words. "What comes after 20" is 4 words — should never
    # touch the knowledge base.
    if len(ctx.words) < 5:
        return LayerResult.pass_through()

    # Skip hard-skip system commands
    if any(skip in ctx.clean_in for skip in _HARD_SKIP):
        return LayerResult.pass_through()

    # Check if KB has any content at all — if empty, skip entirely
    try:
        from knowledge.core import knowledge_collection
        if knowledge_collection.count() == 0:
            return LayerResult.pass_through()
    except Exception:
        return LayerResult.pass_through()

    # Doc-reference trigger: user explicitly references uploaded content
    # These bypass ALL other gates — always search
    is_doc_reference = any(t in ctx.clean_in for t in _DOC_TRIGGERS)

    # Only search knowledge base for domain questions or doc references.
    # Generic question words alone ("what", "how", "why") are not sufficient
    # to justify a knowledge search — they match everything including
    # arithmetic, personal questions, and casual conversation.
    # The relevance threshold in knowledge/core.py is the final quality gate,
    # but we avoid the ChromaDB call entirely for clearly non-document queries.
    _DOMAIN_SIGNALS = [
        "explain", "define", "describe", "difference between",
        "compare", "summarize", "summary", "how does", "how do",
        "what is a", "what are", "tell me about", "give me",
        "according to", "based on", "from the", "in the",
        "research", "study", "report", "document", "paper",
        "article", "chapter", "section", "topic", "subject",
        "theory", "concept", "method", "process", "algorithm",
        "history of", "types of", "examples of", "list of",
        "benefits of", "disadvantages of", "advantages of",
    ]
    is_domain_question = any(s in ctx.clean_in for s in _DOMAIN_SIGNALS)
    should_search = is_doc_reference or is_domain_question

    if not should_search:
        return LayerResult.pass_through()

    try:
        from knowledge import search_knowledge
        results = search_knowledge(ctx.prompt_text, top_k=5)
        if results and len(results.strip()) > 50:
            ctx.knowledge_context = results
            print(Fore.CYAN + f"[BRAIN] Knowledge: found relevant content "
                              f"({len(results)} chars)")
        else:
            print(Fore.CYAN + "[BRAIN] Knowledge: no relevant match")
    except ImportError:
        pass
    except Exception as e:
        print(Fore.YELLOW + f"[BRAIN] Knowledge search error: {e}")

    return LayerResult.pass_through()