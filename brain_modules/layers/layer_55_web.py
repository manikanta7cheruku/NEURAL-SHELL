"""
LAYER 5.5: WEB SEARCH

Asks the injected web provider (deps["web"], default web_provider.DefaultWebProvider)
for live information and records a WebOutcome on the context. The outcome says
exactly what happened (ok, offline, disabled, error, empty), so the guard layer
and the reasoning policy can be honest about it. Tests inject a fake provider.
"""

import logging

from brain_modules import web_provider
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer55")
_provider = web_provider.DefaultWebProvider()


def process(ctx, deps):
    if (ctx.is_command or ctx.is_greeting or ctx.is_action_cmd or "VISUAL_REPORT:" in ctx.prompt_text):
        return LayerResult.pass_through()
    provider = deps.get("web") or _provider
    try:
        outcome = provider.lookup(ctx.resolved_text or ctx.prompt_text, deps.get("config"))
    except Exception as exc:
        _log.warning("web provider crashed: %s", exc, exc_info=True)
        outcome = web_provider.WebOutcome("error", needed=True, detail=str(exc))
    ctx.web_outcome = outcome
    if outcome.status == "ok":
        ctx.web_context, ctx.web_searched = outcome.text, True
    return LayerResult.pass_through()
