"""
LAYER 035: SELF-KNOWLEDGE ROUTER

Semantic intent recognition for questions ABOUT Seven (abilities, how the app
works, where data lives, status) and about the user's goals. Answers come from
live sources in self_knowledge, never from a model's guess. Memory-related
intents (history, provenance, reasons) are only tagged here; the memory layer
answers them from stored evidence.
"""

import logging

from brain_modules import goals, intent_router, lifecycle, self_knowledge, speech_acts
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer035")
_ANSWERED_HERE = {"capability_list", "capability_check", "app_help", "data_flow", "status_check"}
_REQUEST_STARTS = ("tell", "show", "explain", "list", "describe")


def process(ctx, deps):
    if "VISUAL_REPORT:" in ctx.prompt_text or ctx.is_command or ctx.is_action_cmd:
        return LayerResult.pass_through()
    text = ctx.resolved_text or ctx.prompt_text
    reply = None
    try:
        # One resolver owns "I finished X" / "forget X" / "complete my X task" for goals AND tasks.
        reply = lifecycle.handle(ctx, deps)
    except Exception as exc:
        _log.warning("lifecycle skipped: %s", exc, exc_info=True)
    if reply is None:
        try:
            reply = goals.handle_lifecycle(ctx.speaker_key, text)      # "what are my goals"
        except Exception as exc:
            _log.debug("goal query skipped: %s", exc)
    if reply:
        return LayerResult.stop(reply)

    first = ctx.norm_in.split(" ", 1)[0] if ctx.norm_in else ""
    if not (speech_acts.is_question(text, ctx.norm_in) or first in _REQUEST_STARTS):
        return LayerResult.pass_through()
    try:
        route = intent_router.route(ctx.norm_in)
    except Exception as exc:
        _log.warning("router failed: %s", exc)
        return LayerResult.pass_through()
    ctx.intent = route
    if route.label in _ANSWERED_HERE:
        try:
            answer = self_knowledge.answer(route.label, ctx, deps.get("config"))
        except Exception as exc:
            _log.warning("self-knowledge failed: %s", exc, exc_info=True)
            answer = None
        if answer:
            return LayerResult.stop(answer)
    return LayerResult.pass_through()
