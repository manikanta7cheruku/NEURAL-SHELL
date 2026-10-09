"""
LAYER 5: MEMORY

Two paths, both gated:

    1. DIRECT RECALL. "What is my favorite framework?" is answered straight
       from the structured fact store by slot, in about a millisecond, with
       no model call and therefore no chance of hallucination.
    2. SEMANTIC RECALL. Only when the message plausibly depends on something
       the user told Seven (memory_gate.should_search_memory), a similarity
       search over FACTS is started on a background thread. It overlaps with
       the web, knowledge and fact layers, and the LLM layer waits for it only
       briefly. Past conversations are never searched: that is how Seven's
       own old replies used to leak back into new answers.

Everything else, including greetings, commands, general-knowledge questions
and live-data questions, never touches memory.
"""

import logging

from brain_modules import memory_gate
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer05")


def process(ctx, deps):
    if ("VISUAL_REPORT:" in ctx.prompt_text or ctx.is_command
            or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()

    norm = ctx.norm_in
    recall = memory_gate.parse_recall_query(norm)
    if recall is None and not memory_gate.should_search_memory(norm, ctx.prompt_text):
        return LayerResult.pass_through()

    try:
        from memory import fact_service
    except Exception as exc:
        _log.debug("memory unavailable: %s", exc)
        return LayerResult.pass_through()

    config = deps.get("config")
    min_relevance = float(config.KEY.get("memory", {}).get("min_relevance", 0.70)) if config else 0.70

    if recall is not None:
        ctx.recall_query = recall
        try:
            answer = fact_service.answer_recall(ctx.speaker_key, recall)
        except Exception as exc:
            _log.warning("direct recall failed: %s", exc)
            answer = None
        if answer:
            return LayerResult.stop(answer)

    ctx.memory_future = fact_service.semantic_facts_async(
        ctx.speaker_key, ctx.prompt_text, min_relevance=min_relevance, k=3)
    return LayerResult.pass_through()
