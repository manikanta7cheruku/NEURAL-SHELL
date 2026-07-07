"""
=============================================================================
LAYER 5.9: APP HISTORY QUERY

Catches "what apps did I open today" / "which apps did you launch".
Reads from memory/command_log.py and returns recent app history.
=============================================================================
"""

from brain_modules.layer_result import LayerResult


def process(ctx, deps):
    clean_in = ctx.clean_in

    _is_app_history = (
        ("what" in clean_in or "which" in clean_in)
        and ("app" in clean_in or "open" in clean_in)
        and ("today" in clean_in or "did i" in clean_in or "did you" in clean_in)
    )

    if not _is_app_history:
        return LayerResult.pass_through()

    from memory.command_log import command_log
    stats  = command_log.get_stats()
    recent = stats.get('recent', [])

    if recent:
        app_list = ", ".join([f"{r['action']} {r['target']}" for r in recent[:5]])
        return LayerResult.stop(f"Recent commands: {app_list}.")

    return LayerResult.stop("No apps opened in this session yet.")