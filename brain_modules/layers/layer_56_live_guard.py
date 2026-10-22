"""
LAYER 5.6: LIVE-DATA GUARD

When a question needs fresh information and the web lookup did not succeed,
say exactly why instead of letting the model make something up:

    offline   "I have no internet right now, so I can't check that."
    disabled  web lookups are switched off in Settings
    error     the search service did not respond
    empty     the search found nothing reliable

Time-sensitive questions (weather, news, prices, scores, "latest", "today") are
answered with the honest limit. For other questions the model may answer from
general knowledge, but is told the web was unavailable and must label it.
"""

import random

from brain_modules import memory_gate
from brain_modules.layer_result import LayerResult

_TOPIC = {"weather": "weather", "news": "news", "prices": "prices", "scores": "scores"}


def _message(outcome, topic: str) -> str:
    what = f"the live {topic}" if topic in _TOPIC.values() else "that"
    if outcome.status == "offline":
        return random.choice([f"I have no internet right now, so I can't check {what}.",
                              f"I'm offline at the moment, so I can't look up {what}."])
    if outcome.status == "disabled":
        return f"Web lookups are switched off in my settings, so I can't check {what}."
    if outcome.status == "error":
        return f"The search service didn't respond, so I can't confirm {what} right now."
    return f"I searched but found nothing reliable for {what}."


def process(ctx, deps):
    outcome = ctx.web_outcome
    if ctx.is_command or ctx.web_searched or "VISUAL_REPORT:" in ctx.prompt_text:
        return LayerResult.pass_through()
    norm = ctx.norm_in
    topic = memory_gate.live_topic(norm)
    needed = bool(outcome and outcome.needed) or bool(topic)
    failed = outcome is None or outcome.status in ("offline", "disabled", "error", "empty", "not_needed")
    if not needed or not failed or norm.startswith(("what causes", "how does", "why does", "explain")):
        return LayerResult.pass_through()
    if outcome is None or outcome.status == "not_needed":
        outcome = type("O", (), {"status": "error"})()   # live topic but no search attempted
        if topic:
            return LayerResult.stop(_message(outcome, topic))
        return LayerResult.pass_through()
    if topic or memory_gate.time_sensitive(norm):
        return LayerResult.stop(_message(outcome, topic or "information"))
    ctx.hints.append(f"Web lookup was unavailable ({outcome.status}). If you answer, say it comes from your "
                     "built-in knowledge and may be out of date.")
    return LayerResult.pass_through()
