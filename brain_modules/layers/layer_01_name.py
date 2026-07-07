"""
=============================================================================
LAYER 1: NAME SETTING

Detects "my name is X" / "call me X" and saves name to memory.
Returns confirmation immediately. Does not hit LLM.

Uses existing brain_modules/identity_layer.py handle_name_setting().
=============================================================================
"""

from brain_modules.layer_result import LayerResult
from brain_modules.identity_layer import handle_name_setting


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")

    name_result = handle_name_setting(
        ctx.prompt_text,
        ctx.clean_in,
        ctx.speaker_id,
        ctx.speaker_name,
        seven_memory,
        ctx.user_name
    )

    if name_result is None:
        return LayerResult.pass_through()

    # handle_name_setting returns either a string or (new_name, response) tuple
    if isinstance(name_result, tuple):
        new_name, response = name_result
        ctx.new_user_name = new_name  # brain.py will apply this to global USER_NAME
        ctx.speaker_name  = new_name
        return LayerResult.stop(response)

    return LayerResult.stop(name_result)