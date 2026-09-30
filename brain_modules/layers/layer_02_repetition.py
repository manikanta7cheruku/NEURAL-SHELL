"""
=============================================================================
LAYER 2: REPETITION DETECTION

If user asks the same question repeatedly, respond with short acknowledgement
instead of repeating the full answer.
=============================================================================
"""

from brain_modules.layer_result import LayerResult
from brain_modules.repetition_detector import detect_repetition


def _resolve_thread_id(ctx, deps):
    """
    Normalize speaker_id to match the key used by brain.py when saving.
    Leverages the dynamically refreshed ctx.user_name to avoid stale configuration keys.
    """
    speaker_id = ctx.speaker_id
    if speaker_id in ("default", "unknown") or not speaker_id:
        user_name = getattr(ctx, "user_name", None)
        if user_name and user_name.strip().lower() not in ("admin", "default", "unknown", ""):
            return user_name.strip().lower()
        return "default"
    return speaker_id.strip().lower()


def process(ctx, deps):
    if ctx.is_command or ctx.is_greeting:
        return LayerResult.pass_through()

    thread_id = _resolve_thread_id(ctx, deps)
    
    # Dynamic debugging to trace thread key mismatch in real time
    try:
        from brain_modules.conversation_thread import ConversationThread
        from colorama import Fore
        print(Fore.MAGENTA + f"[LAYER2 DEBUG] Input: '{ctx.clean_in}' | Resolved ID: '{thread_id}'")
        print(Fore.MAGENTA + f"[LAYER2 DEBUG] Active Keys in RAM: {list(ConversationThread._threads.keys())}")
        print(Fore.MAGENTA + f"[LAYER2 DEBUG] Turns for '{thread_id}': {ConversationThread.get_turns(thread_id, limit=5)}")
    except Exception as _dbg_err:
        print(f"[LAYER2 DEBUG] Fail: {_dbg_err}")

    repeat_result = detect_repetition(ctx.clean_in, thread_id)

    # Similar-but-not-identical: silent pass-through.
    # Do NOT inject meta-instructions. 1B parameter models interpret
    # "give different perspective" as "apologize and change stance", which
    # triggers RLHF trained "you're right, I was wrong" reflex responses.
    if repeat_result == "__SIMILAR_DETECTED__":
        return LayerResult.pass_through()

    if repeat_result is not None:
        # Debug trace the interception
        print(Fore.GREEN + f"[LAYER2 INTERCEPT] Repetition detected! Returning cached response.")
        return LayerResult.stop(repeat_result)

    return LayerResult.pass_through()