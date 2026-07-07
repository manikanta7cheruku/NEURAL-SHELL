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


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")
    config       = deps.get("config")

    if ("VISUAL_REPORT:" in ctx.prompt_text
            or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
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