"""
LAYER 6: PERSONAL RECALL GUARD

If the user asked a direct question about something they told Seven and no
fact was found (neither by slot nor by semantic search), say so honestly
instead of letting the model invent a personal detail.

BUG FIXED: the old filter fired on ANY question containing "my", so
"what's wrong with my code" or "how do I clean my keyboard" were answered
with "You haven't told me that yet." It now acts ONLY on parsed recall
questions ("what is my favorite X", "what do I like", "where do I live").
"""

import random

from brain_modules.layer_result import LayerResult


def _unknown_reply(recall) -> str:
    if recall.kind == "likes":
        return "You haven't told me what you like yet."
    if recall.kind == "dislikes":
        return "You haven't told me what you dislike yet."
    return random.choice([
        f"I don't know your {recall.attr} yet. Tell me and I'll remember.",
        f"You haven't told me your {recall.attr} yet.",
    ])


def process(ctx, deps):
    recall = ctx.recall_query
    if recall is None:
        return LayerResult.pass_through()
    config = deps.get("config")
    timeout = float(config.KEY.get("memory", {}).get("retrieval_timeout_ms", 450)) / 1000.0 if config else 0.45
    ctx.resolve_memory(timeout)
    if ctx.memory_facts:
        return LayerResult.pass_through()
    return LayerResult.stop(_unknown_reply(recall))
