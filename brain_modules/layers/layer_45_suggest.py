"""
=============================================================================
LAYER 4.5b: TASK SUGGESTION

If user says something like "I need to finish X" or "I have to do Y",
suggest adding it as a task (without auto-creating).

User must explicitly say "add task X" to confirm.
Prevents accidental task creation from casual conversation.
=============================================================================
"""

from brain_modules.layer_result import LayerResult


_TASK_SUGGEST_TRIGGERS = [
    "i need to finish", "i need to complete", "i need to do",
    "i have to finish", "i have to complete", "i have to do",
    "i have to submit", "i need to submit",
    "i must finish", "i must complete", "i must do",
    "i should finish", "i should complete",
    "dont forget to", "don't forget to",
]

# Explicit task triggers — if user used these, task layer already handled it
_EXPLICIT_TASK_TRIGGERS = [
    "add task", "add to my tasks", "add to tasks", "create task",
    "make a task", "task:", "todo:", "new task",
]


def process(ctx, deps):
    _has_suggest = any(t in ctx.clean_in for t in _TASK_SUGGEST_TRIGGERS)
    _has_explicit = any(t in ctx.clean_in for t in _EXPLICIT_TASK_TRIGGERS)

    if not _has_suggest or _has_explicit:
        return LayerResult.pass_through()

    # Extract what they need to do
    _suggest_text = ctx.clean_in
    for _st in sorted(_TASK_SUGGEST_TRIGGERS, key=len, reverse=True):
        if _st in _suggest_text:
            _suggest_text = _suggest_text.replace(_st, "").strip()
            break

    for _art in ["the ", "a ", "my "]:
        if _suggest_text.startswith(_art):
            _suggest_text = _suggest_text[len(_art):].strip()
            break

    _suggest_text = _suggest_text.strip('.,!-:;')

    if _suggest_text and len(_suggest_text) > 2:
        return LayerResult.stop(
            f'Want me to add "{_suggest_text}" as a task? '
            f'Say "add task {_suggest_text}" to save it.'
        )

    return LayerResult.pass_through()