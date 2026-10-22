"""
LAYER 7: LEARNING

Learns from what the user says, without slowing the reply.

    style feedback ("keep answers short")        applied and acknowledged
    corrections ("actually it's Vue, not React") replace the value, history kept
    facts and preferences                        validated, stored with provenance
    goals ("I'm building ...")                   tracked explicitly
    knowledge gaps                               recorded for the curiosity engine

An EXPLICIT "remember ..." gets a short acknowledgement and stops here.
Everything else is learned silently and the reply is generated normally, with a
hint so the model acknowledges naturally instead of repeating information back.
"""

import logging
import random
import re

from brain_modules import correction_detector, fact_extractor, goals, learning
from brain_modules.layer_result import LayerResult
from memory import learning_store

_log = logging.getLogger("seven.layer07")
_TRAILING_REMEMBER = re.compile(r"(?:^|[.!]\s+)(?:please\s+)?remember(?:\s+(?:that|this|it))?\s*[.!]*\s*$", re.IGNORECASE)


def _ack(results, facts) -> str:
    for r, f in zip(results, facts):
        sup = r.get("superseded")
        if sup:
            return f"Got it. {f.value} instead of {sup['old_value']}. I've kept {sup['old_value']} as your earlier choice."
    changed = [(r, f) for r, f in zip(results, facts) if r["status"] == "updated"]
    if changed:
        r, f = changed[0]
        return f"Got it. Changed from {r['previous']} to {f.value}."
    if results and all(r["status"] == "unchanged" for r in results):
        return "Yep, I already had that."
    return random.choice(["Got it.", "Noted.", "Okay, remembered."])


def _open_gaps(ctx, facts, results):
    from brain_modules import curiosity
    key = ctx.speaker_key
    for f, r in zip(facts, results):
        if f.key.startswith("likes:") and f.kind and r["status"] == "created":
            from memory import facts_store
            if not facts_store.get_active_by_key(key, f"favorite_{f.kind}") and "loves" in f.text:
                curiosity.open_gap(key, "favorite_promotion", f"{f.kind}:{f.value}",
                                   {"kind": f.kind, "value": f.value})
        sup = r.get("superseded")
        if sup:
            curiosity.open_gap(key, "reason_change", sup.get("key", f.key) if isinstance(sup, dict) else f.key,
                               {"former": sup["old_value"], "current": f.value, "slot": f.key})


def process(ctx, deps):
    if ("VISUAL_REPORT:" in ctx.prompt_text or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()
    text = ctx.resolved_text or ctx.prompt_text
    key = ctx.speaker_key

    try:
        signals = learning.detect_style_feedback(text)
        if signals:
            learning.apply_style_signals(key, signals)
            if len(ctx.norm_in.split()) <= 10:
                return LayerResult.stop(learning.acknowledgement(signals))
    except Exception as exc:
        _log.debug("style feedback skipped: %s", exc)

    try:
        from memory import fact_service
    except Exception as exc:
        _log.debug("fact service unavailable: %s", exc)
        return LayerResult.pass_through()

    try:
        corr = correction_detector.detect_correction(text)
        if corr and corr.get("old_value") and corr.get("new_value"):
            res = fact_service.apply_correction(key, corr["old_value"], corr["new_value"], text,
                                                source_msg_id=ctx.user_msg_id, conversation_id=ctx.conversation_id)
            if res:
                learning_store.record_outcome(key, "answer", "fact", "corrected", text[:120], ctx.conversation_id)
                from brain_modules import curiosity
                curiosity.open_gap(key, "reason_change", res.get("text", corr["new_value"]),
                                   {"former": corr["old_value"], "current": corr["new_value"],
                                    "slot": res.get("slot", "")})
                return LayerResult.stop(f"Fixed. {corr['new_value']} it is.")
    except Exception as exc:
        _log.debug("correction skipped: %s", exc)

    explicit = False
    try:
        facts = fact_extractor.extract_facts(text, kind_hint=ctx.resolution_kind)
        if facts:
            results = [fact_service.remember(key, f, source_text=text, source_msg_id=ctx.user_msg_id,
                                             conversation_id=ctx.conversation_id) for f in facts]
            _open_gaps(ctx, facts, results)
            explicit = any(f.explicit for f in facts) or bool(_TRAILING_REMEMBER.search(text))
            ack = _ack(results, facts)
            if not explicit:
                shown = next((f for f in facts if f.key.startswith(("likes:", "dislikes:"))), facts[0])
                ctx.hints.append(
                    f"The user just told you: {shown.text}. Acknowledge it naturally in one short sentence with a "
                    "reaction of your own. Do not repeat information about it back to them.")
    except Exception as exc:
        _log.warning("fact learning failed: %s", exc, exc_info=True)
        ack = None

    try:
        new_goals = goals.learn(key, text, ctx.user_msg_id)
        if new_goals and not explicit:
            ctx.hints.append("The user mentioned a goal: " + "; ".join(g["title"] for g in new_goals) +
                             ". Show you understood what they are trying to achieve.")
            from brain_modules import curiosity
            for g in new_goals:
                if g["status"] == "created":
                    curiosity.open_gap(key, "goal_detail", g["title"], {"title": g["title"], "goal_id_ref": g["id"]})
        elif new_goals and explicit and not ack:
            ack = "Got it."
    except Exception as exc:
        _log.debug("goal learning skipped: %s", exc)

    try:
        st = ctx.state
        if st is not None and st.topic:
            n = learning_store.bump_mention(key, st.topic.name)
            if n == 3:
                from brain_modules import curiosity
                curiosity.open_gap(key, "entity_interest", st.topic.name.lower(), {"entity": st.topic.name})
    except Exception as exc:
        _log.debug("mention tracking skipped: %s", exc)

    if explicit and ack:
        return LayerResult.stop(ack)
    return LayerResult.pass_through()
