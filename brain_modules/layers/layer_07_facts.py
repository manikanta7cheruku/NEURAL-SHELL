"""
LAYER 7: LEARNING

Learns from what the user says, without slowing the reply.

    1. STYLE FEEDBACK ("keep answers short", "stop joking") is applied to the
       user's profile immediately and acknowledged in one short line.
    2. CORRECTIONS ("actually it's Vue, not React") replace the stored value.
    3. FACTS ("remember that my favorite framework is React", "I live in X")
       are validated by the extractor and written to SQLite synchronously
       (about a millisecond). The semantic-index write is queued for the
       background worker.

An EXPLICIT "remember ..." gets a brief acknowledgement and stops here
("Got it."), so no model call is spent on it. Implicit statements are learned
silently and the conversation continues naturally.
"""

import logging
import random

from brain_modules import correction_detector, fact_extractor, learning, speech_acts
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer07")


def _ack(results, facts) -> str:
    changed = [(r, f) for r, f in zip(results, facts) if r["status"] == "updated"]
    if changed:
        r, f = changed[0]
        return f"Got it. Changed from {r['previous']} to {f.value}."
    if all(r["status"] == "unchanged" for r in results):
        return "Yep, I already had that."
    return random.choice(["Got it.", "Noted.", "Okay, remembered."])


def process(ctx, deps):
    if ("VISUAL_REPORT:" in ctx.prompt_text or ctx.is_command
            or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()

    text, key = ctx.prompt_text or "", ctx.speaker_key

    # 1. Style feedback
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

    # 2. Corrections
    try:
        corr = correction_detector.detect_correction(text)
        if corr and corr.get("old_value") and corr.get("new_value"):
            res = fact_service.apply_correction(key, corr["old_value"], corr["new_value"], text)
            if res:
                return LayerResult.stop(f"Fixed. {corr['new_value']} it is.")
    except Exception as exc:
        _log.debug("correction skipped: %s", exc)

    # 3. Facts
    try:
        facts = fact_extractor.extract_facts(text)
        if facts:
            results = [fact_service.remember(key, f, source_text=text) for f in facts]
            if any(f.explicit for f in facts):
                return LayerResult.stop(_ack(results, facts))
    except Exception as exc:
        _log.warning("fact learning failed: %s", exc)

    return LayerResult.pass_through()
