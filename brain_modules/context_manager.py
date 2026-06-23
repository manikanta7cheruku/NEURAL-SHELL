"""
=============================================================================
brain_modules/context_manager.py
PROJECT SEVEN -- Conversation History + Prompt Assembler

WHAT THIS FILE DOES:
    1. Manages per-speaker conversation history (CONVO_HISTORY dict)
    2. Trims history to last N turns (sliding window)
    3. Assembles the final prompt string sent to Ollama

WHY THIS IS A SEPARATE FILE:
    brain.py had CONVO_HISTORY as a global variable with history management
    scattered across the think() function. Extracting it here gives us:
    - One place to change history size
    - One place to change prompt assembly format
    - History that can be tested without running the full voice loop

DESIGN PATTERN: Repository Pattern
    ContextManager is a repository for conversation history.
    It owns the storage (CONVO_HISTORY dict) and all access to it.
    No other file touches CONVO_HISTORY directly.

INTERVIEW TALKING POINT:
    "I manage conversation context with a sliding window of 8 turns per
     speaker. Each speaker has their own history keyed by speaker_id.
     This supports multi-user Voice ID -- different people talking to
     Seven get separate conversation threads. The 8-turn limit is
     intentional: local LLMs have limited context windows (4096 tokens).
     Sending 50 turns of history would overflow the context and degrade
     response quality."

CONTEXT WINDOW MATH (interview-ready):
    Ollama options set num_ctx=4096 tokens.
    System prompt: ~400 tokens
    Memory context: ~200 tokens
    Web context: ~300 tokens
    8 turns of history: ~800 tokens
    New question: ~50 tokens
    Total: ~1750 tokens -- leaves 2346 tokens for response generation.
    With 50 turns: ~5000 tokens -- OVERFLOWS. Model wraps, quality drops.

WHY DICT KEYED BY SPEAKER_ID:
    Seven supports Voice ID. Multiple people can use the same machine.
    If Mani and Priya both use Seven, their conversations stay separate.
    dict[speaker_id] = [list of turns]
    This is a simple in-memory solution. Production would use a database.

ALTERNATIVE (interview question):
    "Why not use a database for conversation history?"
    Answer: "For a local voice assistant, in-memory is correct. Conversation
     context is session-scoped -- you want fresh context each time Seven
     starts. Persisting conversation history creates privacy concerns and
     grows unboundedly. ChromaDB already handles long-term memory (facts).
     Short-term context stays in RAM."
=============================================================================
"""

from colorama import Fore

# ---------------------------------------------------------------------------
# CONVERSATION HISTORY STORAGE
# dict keyed by speaker_id -> list of strings
# Each string is either "User: <text>" or "Seven: <text>"
#
# WHY MODULE-LEVEL (not class):
#     brain.py calls these as functions.
#     Module-level dict persists for the session automatically.
#     A class would require instantiation and passing the instance around.
# ---------------------------------------------------------------------------
CONVO_HISTORY = {}

# Maximum turns per speaker kept in context
# One "turn" = one User: line + one Seven: line
# 8 turns = 16 lines. Keeps context window manageable.
MAX_HISTORY_TURNS = 8


def add_user_turn(speaker_id: str, text: str):
    """
    Add a user utterance to this speaker's history.

    CALLED BY: brain.py before sending to LLM.
    Only called for non-command inputs -- commands do not go into history.
    Commands in history pollute the LLM's understanding of conversation.

    WHY WE FILTER COMMANDS:
        If history has "User: open chrome" -> "Seven: Opening chrome."
        The LLM might think this is a conversational pattern and start
        randomly suggesting opening apps. Commands are not conversational.
    """
    if speaker_id not in CONVO_HISTORY:
        CONVO_HISTORY[speaker_id] = []
    CONVO_HISTORY[speaker_id].append(f"User: {text}")
    _trim(speaker_id)


def add_seven_turn(speaker_id: str, text: str):
    """
    Add Seven's response to this speaker's history.

    CALLED BY: brain.py after getting LLM response.
    Only called for non-command responses.
    """
    if speaker_id not in CONVO_HISTORY:
        CONVO_HISTORY[speaker_id] = []
    CONVO_HISTORY[speaker_id].append(f"Seven: {text}")
    _trim(speaker_id)


def get_history(speaker_id: str) -> list:
    """
    Get conversation history for a speaker.
    Returns empty list if speaker has no history yet.
    """
    return CONVO_HISTORY.get(speaker_id, [])


def get_history_string(speaker_id: str) -> str:
    """
    Get conversation history as a formatted string for the LLM prompt.
    Format: "User: ...\nSeven: ...\nUser: ...\nSeven: ..."

    CALLED BY: assemble_prompt() below.
    """
    history = get_history(speaker_id)
    return "\n".join(history)


def clear_history(speaker_id: str = None):
    """
    Clear conversation history.
    If speaker_id given: clear only that speaker's history.
    If None: clear all history (called on memory wipe / session reset).

    CALLED BY: brain.reset_session() and memory wipe endpoint.
    """
    global CONVO_HISTORY
    if speaker_id:
        CONVO_HISTORY.pop(speaker_id, None)
    else:
        CONVO_HISTORY = {}


def _trim(speaker_id: str):
    """
    Keep history within MAX_HISTORY_TURNS * 2 lines.
    (Each turn = 1 User line + 1 Seven line = 2 lines)

    Uses list slicing to keep the MOST RECENT turns.
    Older turns are dropped -- recency is more important than completeness.

    WHY [-limit:] slicing:
        Python negative indexing counts from the end.
        CONVO_HISTORY[speaker_id][-16:] keeps last 16 lines.
        This is O(1) space complexity -- history never grows unboundedly.
    """
    limit = MAX_HISTORY_TURNS * 2  # 8 turns * 2 lines per turn = 16 lines
    if len(CONVO_HISTORY.get(speaker_id, [])) > limit:
        CONVO_HISTORY[speaker_id] = CONVO_HISTORY[speaker_id][-limit:]


def assemble_prompt(
    system_prompt: str,
    speaker_id:    str,
    web_context:     str = "",
    knowledge_context: str = "",
    memory_context:  str = "",
) -> str:
    """
    Assemble the final prompt string sent to Ollama.

    INJECTION ORDER (matters for LLM attention):
        1. System prompt (personality + rules)
        2. Web context (live data -- highest recency)
        3. Knowledge context (offline facts)
        4. Memory context (personal facts about user)
        5. Conversation history (recent turns)
        6. "Seven:" prompt (tells LLM to complete as Seven)

    WHY THIS ORDER:
        LLMs give more attention to text near the end of the prompt.
        "Seven:" at the very end anchors the response.
        System prompt first establishes personality for the whole context.
        Web context before memory because live data is more current.

    INTERVIEW TALKING POINT:
        "Prompt assembly order affects LLM response quality. I put the
         system prompt first to establish personality, then inject context
         from most-recent (web) to most-personal (memory), and end with
         the conversation history. The 'Seven:' suffix is the completion
         anchor -- it tells the LLM to fill in Seven's next response."

    ARGS:
        system_prompt:     from prompt_builder.build_system_prompt()
        speaker_id:        used to fetch this speaker's history
        web_context:       DuckDuckGo results string (empty if no search)
        knowledge_context: local knowledge base results (empty if no match)
        memory_context:    ChromaDB recalled memories (empty if no match)

    RETURNS:
        str -- complete prompt ready to send to Ollama
    """
    parts = [system_prompt, ""]  # System prompt + blank line separator

    # Inject contexts only if they have content
    if web_context:
        parts.append(web_context)
        parts.append("")

    if knowledge_context:
        parts.append(knowledge_context)
        parts.append("")

    if memory_context:
        parts.append(memory_context)
        parts.append("")

    # Conversation history
    history_str = get_history_string(speaker_id)
    if history_str:
        parts.append("LOG:")
        parts.append(history_str)

    # Completion anchor -- LLM fills in after "Seven:"
    parts.append("Seven:")

    return "\n".join(parts)