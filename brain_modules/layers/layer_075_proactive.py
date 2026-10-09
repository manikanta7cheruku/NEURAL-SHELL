"""
=============================================================================
LAYER 075: PROACTIVE INTENT INJECTION

Runs after Layer 07 facts and before Layer 08 LLM.
Detects proactive suggestion opportunities and injects a positive-framed
hint into ctx.proactive_hint. The prompt builder consumes this hint at
Layer 08 to weave a natural suggestion into the LLM response.

WHY POSITIVE FRAMING:
    The 1B model treats negative meta-instructions ("do not repeat",
    "give different perspective") as apology triggers. Phase 3 removed
    all such injections. This layer follows the same rule: hints are
    permissive suggestions, never commands or corrections.

SKIP CONDITIONS:
    - Commands, greetings, action commands (already routed)
    - Visual reports
    - Speaker on cooldown (handled inside proactive_engine)
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult
from brain_modules import proactive_engine


def process(ctx, deps):
    # Skip non-conversational flows
    if ("VISUAL_REPORT:" in ctx.prompt_text
            or ctx.is_command
            or ctx.is_greeting
            or ctx.is_action_cmd):
        return LayerResult.pass_through()

    config = deps.get("config")

    # Resolve stable speaker id for cooldown tracking
    speaker_uid = (
        ctx.speaker_id
        if ctx.speaker_id not in ("default", "unknown")
        else config.KEY.get("identity", {}).get("user_name", "default").lower() or "default"
    )

    try:
        suggestion = proactive_engine.detect_intent(ctx.prompt_text, speaker_uid)
    except Exception as _e:
        print(Fore.YELLOW + f"[LAYER075] Proactive detect skipped: {_e}")
        return LayerResult.pass_through()

    if not suggestion:
        return LayerResult.pass_through()

    # Inject positive-framed hint. Prompt builder will attach to system prompt.
    ctx.proactive_hint = suggestion["hint"]

    # Mark cooldown so we do not spam suggestions turn after turn
    try:
        proactive_engine.mark_suggestion_sent(speaker_uid)
    except Exception:
        pass

    print(Fore.CYAN + f"[LAYER075] Proactive hint injected: category={suggestion['category']}")

    return LayerResult.pass_through()