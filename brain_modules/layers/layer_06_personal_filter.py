"""
LAYER 6: PERSONAL RECALL GUARD

A direct question about the user that found no evidence gets an honest answer,
never a guess. Where useful it points at what Seven DOES know ("you said you
love Interstellar, is it your favorite?") and remembers that it asked, so the
next message is read as the answer. It never invents a motive or a past.
"""

import random

from brain_modules import conversation_state as cs
from brain_modules.layer_result import LayerResult
from memory import facts_store, learning_store


def _join(vals):
    return vals[0] if len(vals) == 1 else ", ".join(vals[:-1]) + " and " + vals[-1]


def _unknown(ctx, rq) -> str:
    st = ctx.state
    key = ctx.speaker_key
    if rq.kind in ("likes", "dislikes", "typed_likes"):
        what = rq.attr if rq.kind == "typed_likes" else ("things you dislike" if rq.kind == "dislikes" else "what you like")
        return f"You haven't told me {what} yet."
    if rq.kind in ("history", "timeline"):
        return "I don't have an earlier value for that. As far as I know it hasn't changed."
    if rq.kind == "reason":
        from memory import fact_service
        slot = fact_service.reason_slot(key, rq, st)
        if slot and st is not None:
            cs.set_pending(st, "gap:reason", {"slot": slot}, ttl=3)
            return "You haven't told me why. What was the reason?"
        return "I'm not sure which choice you mean, and you haven't told me a reason. What were you thinking of?"
    if rq.key.startswith("favorite_"):
        kind = rq.key[len("favorite_"):]
        rows = facts_store.list_by_prefix(key, f"likes:{kind}:")
        names = [r["raw_value"] for r in rows if r.get("raw_value")][:3]
        if names and st is not None:
            gap_id = learning_store.add_gap(key, "favorite_promotion", f"{kind}:{names[0]}",
                                            {"kind": kind, "value": names[0]}, 6)
            cs.set_pending(st, "gap:favorite_promotion", {"gap_id": gap_id, "kind": kind, "value": names[0]}, ttl=3)
            if len(names) == 1:
                return (f"You haven't told me a favorite {kind}, but you did say you like {names[0]}. "
                        f"Is that your favorite?")
            return f"You haven't named a favorite {kind}, but you've mentioned {_join(names)}. Which one is it?"
    return random.choice([f"I don't know your {rq.attr} yet. Tell me and I'll remember.",
                          f"You haven't told me your {rq.attr} yet."])


def process(ctx, deps):
    rq = ctx.recall_query
    if rq is None:
        return LayerResult.pass_through()
    config = deps.get("config")
    timeout = float(config.KEY.get("memory", {}).get("retrieval_timeout_ms", 450)) / 1000.0 if config else 0.45
    ctx.resolve_memory(timeout)
    if ctx.memory_facts:
        return LayerResult.pass_through()
    return LayerResult.stop(_unknown(ctx, rq))
