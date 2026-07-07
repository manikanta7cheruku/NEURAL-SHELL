"""
=============================================================================
LAYER 6: PERSONAL QUESTION FILTER

If user asks a personal question ("what sport do I play")
and there is no memory context for the answer, return "You haven't told me."

This prevents the LLM from hallucinating personal details Seven doesn't know.

Guards against blocking file questions like "how many resumes do I have".
=============================================================================
"""

from brain_modules.layer_result import LayerResult


_PERSONAL_QUESTION_WORDS = [
    "my", "about me", "do i", "did i", "am i",
    "i like", "i love", "i play", "i work", "i study"
]

_QUESTION_STARTS = [
    "what", "which", "who", "when", "where", "how", "do you know"
]


def process(ctx, deps):
    clean_in = ctx.clean_in

    is_personal_question = any(w in clean_in for w in _PERSONAL_QUESTION_WORDS)
    is_question          = any(clean_in.startswith(w) for w in _QUESTION_STARTS)

    _is_file_question = any(fw in clean_in for fw in ctx.FILE_WORDS)

    if (is_question and is_personal_question
            and not ctx.memory_context
            and not ctx.is_command
            and not _is_file_question):
        return LayerResult.stop("You haven't told me that yet.")

    return LayerResult.pass_through()