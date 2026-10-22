"""
LAYER 1: NAME SETTING

"My name is 77" saves the name. If the same message says more ("My name is 77.
Remember that my favorite language is Python"), the rest is NOT dropped: it
continues through the pipeline and the name acknowledgement is put in front of
the final reply.
"""

from brain_modules import identity_layer
from brain_modules.layer_result import LayerResult
from brain_modules.layers import layer_00_input_prep as prep


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")
    result = identity_layer.handle_name_setting(
        ctx.prompt_text, ctx.clean_in, ctx.speaker_id, ctx.speaker_name, seven_memory, ctx.user_name)
    if result is None:
        return LayerResult.pass_through()
    new_name, response = result
    ctx.new_user_name = new_name
    ctx.speaker_name = new_name
    rest = identity_layer.name_remainder(ctx.prompt_text)
    if rest and len(rest.split()) >= 3:
        ctx.prefix_acks.append(response)
        ctx.prompt_text = rest
        prep.prepare(ctx)
        return LayerResult.pass_through()
    return LayerResult.stop(response)
