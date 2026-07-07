"""
=============================================================================
LAYER 3: IDENTITY OVERRIDES

Catches "who are you", "what is your name", greetings, etc.
Returns hand-crafted responses without hitting LLM.

Uses existing brain_modules/identity_layer.py handle_identity().
=============================================================================
"""

from brain_modules.layer_result import LayerResult
from brain_modules.identity_layer import handle_identity


def process(ctx, deps):
    config = deps.get("config")

    identity_result = handle_identity(
        ctx.clean_in,
        ctx.words,
        ctx.speaker_id,
        ctx.speaker_name,
        config
    )

    if identity_result is not None:
        return LayerResult.stop(identity_result)

    return LayerResult.pass_through()