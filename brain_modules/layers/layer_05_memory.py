"""
LAYER 5: MEMORY

Direct recall (slots, history, provenance, reasons) is answered from stored
evidence in about a millisecond with no model call. Semantic search over facts
starts on a background thread only when the gate says the message depends on
something the user told Seven. Past conversations are not injected; relevant
snippets can be searched explicitly ("what did we talk about").
"""

import logging

from brain_modules import memory_gate
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer05")
_INTENT_TO_KIND = {"memory_history": "history", "memory_provenance": "provenance", "memory_reason": "reason"}


def process(ctx, deps):
    if ("VISUAL_REPORT:" in ctx.prompt_text or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()
    norm = ctx.norm_in
    recall = memory_gate.parse_recall_query(norm)
    label = getattr(ctx.intent, "label", None)
    # The intent router alone is not enough: "do you know alphabets" resembles "how do you know that", but it is
    # a general question, not one about something Seven said about the user. Require a pointer to the user or to
    # what was just said.
    refers_back = bool({"that", "this", "it", "me", "my", "i", "those", "these"} & set(norm.split()))
    if recall is None and label in _INTENT_TO_KIND and refers_back:
        kind = _INTENT_TO_KIND[label]
        recall = memory_gate.RecallQuery(kind, "", "")
    if recall is None and not memory_gate.should_search_memory(norm, ctx.resolved_text or ctx.prompt_text):
        return LayerResult.pass_through()
    try:
        from memory import fact_service
    except Exception as exc:
        _log.debug("memory unavailable: %s", exc)
        return LayerResult.pass_through()

    config = deps.get("config")
    min_rel = float(config.KEY.get("memory", {}).get("min_relevance", 0.70)) if config else 0.70
    if recall is not None:
        ctx.recall_query = recall
        try:
            answer = fact_service.answer_recall(ctx.speaker_key, recall, ctx.state)
        except Exception as exc:
            _log.warning("direct recall failed: %s", exc, exc_info=True)
            answer = None
        if answer:
            return LayerResult.stop(answer)
    ctx.memory_future = fact_service.semantic_facts_async(ctx.speaker_key, ctx.resolved_text or ctx.prompt_text,
                                                          min_relevance=min_rel, k=3)
    return LayerResult.pass_through()
