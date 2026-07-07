"""
=============================================================================
LAYER 2: REPETITION DETECTION

If user asks the same question repeatedly, respond with short acknowledgement
instead of repeating the full answer.

Uses existing brain_modules/identity_layer.py handle_repetition().

Special case: if repetition returns "__SIMILAR_DETECTED__", we do NOT stop —
instead we inject a note into the prompt so LLM handles it differently.
=============================================================================
"""

from brain_modules.layer_result import LayerResult
from brain_modules.identity_layer import handle_repetition


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")
    config       = deps.get("config")

    repeat_result = handle_repetition(
        ctx.clean_in,
        ctx.speaker_id,
        ctx.speaker_name,
        ctx.is_command,
        ctx.is_greeting,
        seven_memory,
        config
    )

    if repeat_result == "__SIMILAR_DETECTED__":
        # Modify prompt in place — LLM will see the note
        ctx.prompt_text = (
            f"[The user asked a similar question before. "
            f"Acknowledge briefly then answer differently.] {ctx.prompt_text}"
        )
        return LayerResult.pass_through()

    if repeat_result is not None:
        return LayerResult.stop(repeat_result)

    return LayerResult.pass_through()