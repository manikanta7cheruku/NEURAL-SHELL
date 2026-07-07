"""
=============================================================================
LAYER 0: INPUT PREPARATION

Runs FIRST. Populates the BrainContext with:
    - Resolved speaker_name (from voice ID or session USER_NAME)
    - clean_in (lowercased, punctuation stripped, filler removed)
    - words, first_word
    - Classifier flags (is_command, is_greeting, is_action_cmd)
    - Acknowledgement filter — returns empty string for "ok", "yeah", etc.

This layer never stops the pipeline unless the input is an acknowledgement.
=============================================================================
"""

from colorama import Fore
from brain_modules.layer_result import LayerResult


_ACKNOWLEDGEMENTS = {
    "good", "okay", "ok", "alright", "yeah", "yep", "yup",
    "sure", "fine", "nice", "cool", "great", "perfect",
    "right", "correct", "exactly", "indeed", "absolutely",
    "understood", "noted", "got it", "i see", "i know",
    "no", "nope", "never mind", "nevermind", "forget it",
    "nothing", "nah", "not really", "not now", "maybe later",
    "that's fine", "thats fine", "that's it", "thats it",
    "that's all", "thats all", "that's good", "thats good",
    "well", "anyway", "moving on", "never mind",
}

_FILLER_STARTS = [
    "and ", "also ", "now ", "then ", "please ",
    "can you ", "could you ", "hey ",
]

_COMMAND_VERBS = [
    "open", "close", "start", "kill", "launch",
    "minimize", "maximize", "maximise", "restore", "snap",
]

_ACTION_CMD_VERBS = [
    "open", "close", "start", "kill", "launch", "minimize", "maximize",
    "maximise", "restore", "snap", "mute", "unmute", "set", "volume",
    "brightness", "play", "pause", "skip", "next", "previous", "stop",
]

_GREETING_STARTS = ["hi", "hey", "hello", "bye", "goodbye", "good"]


def process(ctx, deps):
    seven_memory = deps.get("seven_memory")

    # ── Resolve speaker name ─────────────────────────────────────
    if ctx.speaker_id not in ("default", "unknown"):
        ctx.speaker_name = ctx.speaker_id.title()
        try:
            all_facts = seven_memory.user_facts.get(where={"user_id": ctx.speaker_id})
            if all_facts and all_facts['documents']:
                for doc in all_facts['documents']:
                    doc_lower = doc.lower()
                    if "name is" in doc_lower:
                        found_name = doc.split("is")[-1].strip().rstrip(".")
                        if found_name:
                            ctx.speaker_name = found_name
                            break
                    elif "called" in doc_lower:
                        found_name = doc.split("called")[-1].strip().rstrip(".")
                        if found_name:
                            ctx.speaker_name = found_name
                            break
        except Exception:
            pass
    else:
        ctx.speaker_name = ctx.user_name if ctx.user_name else 'there'

    # ── Clean input ──────────────────────────────────────────────
    clean_in = ctx.prompt_text.lower().strip()
    clean_in = clean_in.replace("?", "").replace(".", "").replace("!", "")
    clean_in = clean_in.replace("'", "").replace(",", "")

    # Strip leading filler
    for _filler in _FILLER_STARTS:
        if clean_in.startswith(_filler):
            clean_in = clean_in[len(_filler):].strip()
            break

    ctx.clean_in   = clean_in
    ctx.words      = clean_in.split()
    ctx.first_word = ctx.words[0] if ctx.words else ""

    # ── Short input filter (acknowledgements) ────────────────────
    if (clean_in in _ACKNOWLEDGEMENTS
            or (len(ctx.words) == 1 and ctx.words[0] in _ACKNOWLEDGEMENTS)):
        print(Fore.YELLOW + f"[BRAIN] Acknowledgement filtered: '{clean_in}'")
        # Empty string = intentional silence for voice loop
        return LayerResult.stop("")

    # ── Classifier flags ─────────────────────────────────────────
    _has_file_word = any(w in ctx.ALWAYS_FILE_WORDS for w in ctx.words)

    ctx.is_command = (
        ctx.first_word in _COMMAND_VERBS
        and not _has_file_word
    )
    ctx.is_greeting    = ctx.first_word in _GREETING_STARTS
    ctx.is_action_cmd  = ctx.first_word in _ACTION_CMD_VERBS

    return LayerResult.pass_through()