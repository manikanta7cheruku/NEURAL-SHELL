"""
=============================================================================
LAYER 7: FACT EXTRACTION (ASYNC)

Enqueues fact extraction and correction detection into the idle worker.
Non-blocking: enqueue returns in under 1ms so chat latency stays flat.

Also detects correction intents ("actually, it's PostgreSQL not MySQL")
and enqueues them for structured supersede handling in facts_store.

Runs silently - does not affect the response.
Skips commands, greetings, action commands, visual reports.
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult
from brain_modules import idle_worker
from brain_modules import correction_detector


def process(ctx, deps):
    if ("VISUAL_REPORT:" in ctx.prompt_text
            or ctx.is_command or ctx.is_greeting or ctx.is_action_cmd):
        return LayerResult.pass_through()

    config = deps.get("config")

    speaker_uid = (
        ctx.speaker_id if ctx.speaker_id not in ("default", "unknown")
        else config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
    )

    user_text = ctx.prompt_text or ""

    # 1. Detect correction intent and enqueue if found
    try:
        correction = correction_detector.detect_correction(user_text)
        if correction:
            idle_worker.enqueue("apply_correction", {
                "speaker_id": speaker_uid,
                "old_value":  correction.get("old_value"),
                "new_value":  correction.get("new_value"),
                "raw_text":   correction.get("raw_text"),
            })
    except Exception as _corr_err:
        print(Fore.YELLOW + f"[LAYER07] Correction detect skipped: {_corr_err}")

    # 2. Enqueue heuristic fact extraction (runs on background thread)
    try:
        idle_worker.enqueue("extract_facts", {
            "user_input": user_text,
            "speaker_id": speaker_uid,
        })
    except Exception as _fact_err:
        print(Fore.YELLOW + f"[LAYER07] Fact enqueue skipped: {_fact_err}")

    return LayerResult.pass_through()