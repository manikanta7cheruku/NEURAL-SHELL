"""
=============================================================================
LAYER 4: TARS PERSONALITY CONTROLS

Catches "set humor to 80" / "set honesty to 60" etc.
Updates config immediately. Returns confirmation.

Also runs mood engine analysis on every input (affects LLM tone).

Uses existing brain_modules/identity_layer.py handle_tars_controls().
=============================================================================
"""

from brain_modules.layer_result import LayerResult
from brain_modules.identity_layer import handle_tars_controls


def process(ctx, deps):
    config      = deps.get("config")
    mood_engine = deps.get("mood_engine")

    # Mood analysis runs on every input
    try:
        mood_engine.analyze_input(ctx.prompt_text)
    except Exception:
        pass

    tars_result = handle_tars_controls(ctx.clean_in, ctx.words, config)
    if tars_result is not None:
        return LayerResult.stop(tars_result)

    return LayerResult.pass_through()