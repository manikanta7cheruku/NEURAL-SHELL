"""
=============================================================================
LAYER 7: FACT EXTRACTION

Extracts new facts about the user from their statement and stores in ChromaDB.
Example: "I work at Google" → stores fact "user works at Google".

Runs silently — does not affect the response.
Fires for statements only, not commands.
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


def process(ctx, deps):
    if ("VISUAL_REPORT:" in ctx.prompt_text
            or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()

    seven_memory = deps.get("seven_memory")
    config       = deps.get("config")

    search_uid = (
        ctx.speaker_id if ctx.speaker_id not in ("default", "unknown")
        else config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
    )

    try:
        seven_memory.extract_and_store_facts(ctx.prompt_text, user_id=search_uid)
    except Exception as _fact_err:
        print(Fore.YELLOW + f"[BRAIN] Fact extraction skipped: {_fact_err}")

    return LayerResult.pass_through()