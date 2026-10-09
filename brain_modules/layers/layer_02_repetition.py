"""
LAYER 2: REPETITION

When the user asks the same genuine question again, answer with the previous
answer plus a brief human remark instead of running the full pipeline.

CHANGES:
    - The thread key now comes from session.resolve_key(), the same key the
      turns are saved under. The old layer computed its own key and the
      mismatch meant repeats were frequently never detected.
    - Debug print statements removed. Failures are logged, not printed.
    - A NameError (Fore used outside the try block that imported it) fixed.
"""

import logging

from brain_modules.layer_result import LayerResult
from brain_modules.repetition_detector import detect_repetition

_log = logging.getLogger("seven.layer02")


def process(ctx, deps):
    if ctx.is_command or ctx.is_greeting or ctx.is_action_cmd:
        return LayerResult.pass_through()
    try:
        reply = detect_repetition(ctx.prompt_text, ctx.speaker_key)
    except Exception as exc:
        _log.debug("repetition check skipped: %s", exc)
        return LayerResult.pass_through()
    if reply:
        _log.info("repeat question answered from previous turn")
        return LayerResult.stop(reply)
    return LayerResult.pass_through()
