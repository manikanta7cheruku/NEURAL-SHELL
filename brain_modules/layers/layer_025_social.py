"""
LAYER 025: SOCIAL

Handles greetings, "how are you", thanks, goodbyes, presence checks and plain
pushback instantly, without memory, web or the model.

This is what makes "Hey" return "Hey. What's up?" in microseconds and never
mention past conversations, facts or system details. Any non-social input
resets the user's greeting streak, so the next "hey" starts fresh.
"""

from brain_modules import social_engine
from brain_modules.layer_result import LayerResult


def process(ctx, deps):
    if "VISUAL_REPORT:" in ctx.prompt_text:
        return LayerResult.pass_through()
    reply = social_engine.respond(ctx.speaker_key, ctx.norm_in, ctx.speaker_name)
    if reply is None:
        return LayerResult.pass_through()
    return LayerResult.stop(reply)
