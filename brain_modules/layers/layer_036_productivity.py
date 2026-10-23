"""
LAYER 036: TASKS, SCHEDULES, TRIGGERS AND WORKSPACES

Answers "show my tasks", "what are my reminders", "what triggers do I have",
creates tasks and fires triggers or workspaces by name. Runs before file
search so "show my tasks" is never treated as a file lookup. See
brain_modules/productivity.py.
"""

import logging

from brain_modules import productivity
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer036")


def process(ctx, deps):
    if "VISUAL_REPORT:" in ctx.prompt_text:
        return LayerResult.pass_through()
    try:
        reply = productivity.handle(ctx.prompt_text, getattr(ctx, "speaker_id", None))
    except Exception as exc:
        _log.warning("productivity layer failed: %s", exc, exc_info=True)
        return LayerResult.pass_through()
    return LayerResult.stop(reply) if reply else LayerResult.pass_through()
