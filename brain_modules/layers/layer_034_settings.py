"""
LAYER 034: SETTINGS CONTROL

"set honesty to 75%", "turn off streaming", "switch your model to llama3.2",
"what are your settings". Runs before the self-knowledge router so a settings
change is never mistaken for a question about the app. Everything else passes
through untouched (see brain_modules/settings_control.py).
"""

import logging

from brain_modules import settings_control
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer034")


def process(ctx, deps):
    if "VISUAL_REPORT:" in ctx.prompt_text:
        return LayerResult.pass_through()
    try:
        reply = settings_control.handle(ctx.prompt_text, deps.get("config"))
    except Exception as exc:
        _log.warning("settings control failed: %s", exc, exc_info=True)
        return LayerResult.pass_through()
    return LayerResult.stop(reply) if reply else LayerResult.pass_through()
