"""
LAYER 5.6: LIVE-DATA GUARD

Runs right after web search. If the user asked for live information
(weather, news, prices, scores) and no web results arrived, Seven says it
cannot check, instead of letting the model fabricate weather or headlines.
"""

import random

from brain_modules import memory_gate, speech_acts
from brain_modules.layer_result import LayerResult

_EDUCATIONAL = ("what causes", "how does", "why does", "explain", "what is the difference")

_REPLIES = {
    "weather": ["I can't check live weather right now. A weather app will beat any guess from me.",
                "No live weather access at the moment, so I won't guess."],
    "news": ["I can't pull live news right now, and I'd rather not guess at headlines."],
    "prices": ["I can't check live prices right now. I'd only be guessing."],
    "scores": ["I can't check live scores right now."],
}


def process(ctx, deps):
    if ctx.web_searched or ctx.web_context or ctx.is_command or "VISUAL_REPORT:" in ctx.prompt_text:
        return LayerResult.pass_through()
    topic = memory_gate.live_topic(ctx.norm_in)
    if not topic or ctx.norm_in.startswith(_EDUCATIONAL):
        return LayerResult.pass_through()
    config = deps.get("config")
    if config and not config.KEY.get("web", {}).get("enabled", True):
        return LayerResult.stop(f"Web lookups are switched off in my settings, so I can't check live {topic}.")
    return LayerResult.stop(random.choice(_REPLIES[topic]))
