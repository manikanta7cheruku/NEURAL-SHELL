"""
LAYER 0: INPUT PREPARATION

Populates the BrainContext: resolved speaker, cleaned input (clean_in, norm_in,
words) and classifier flags. prepare() is reusable so later layers can
re-prepare after the text changes (name statement remainders, clarified
references).

Acknowledgements ("ok", "yeah") are silent, EXCEPT while Seven is waiting for
an answer to a question it asked; then "yeah" means yes.
"""

import logging

from brain_modules import conversation_state as cs
from brain_modules import session, speech_acts
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer00")

_ACKNOWLEDGEMENTS = {"okay", "ok", "alright", "yeah", "yep", "yup", "got it", "understood",
                     "noted", "cool", "nice", "great", "perfect"}
_FILLER_STARTS = ["and ", "also ", "now ", "then ", "please ", "can you ", "could you ", "hey ", "seven "]
_COMMAND_VERBS = ["open", "close", "start", "kill", "launch", "minimize", "maximize", "maximise", "restore", "snap"]
_ACTION_CMD_VERBS = _COMMAND_VERBS + ["mute", "unmute", "set", "volume", "brightness", "play", "pause",
                                      "skip", "next", "previous", "stop"]
_SYSTEM_IDS = {"default", "unknown", "voice_user", "speaker", "user"}


def _enrolled_speaker_name(speaker_id: str):
    """Name of an enrolled voice profile, read only if memory is already loaded."""
    try:
        from memory import core as memory_core
        inst = getattr(memory_core, "_instance", None)
        if inst is None:
            return None
        for doc in (inst.user_facts.get(where={"user_id": speaker_id}) or {}).get("documents", []):
            low = doc.lower()
            name = (doc.split("is")[-1] if "name is" in low else doc.split("called")[-1] if "called" in low else "")
            name = name.strip().rstrip(".")
            if name:
                return name
    except Exception as exc:
        _log.debug("speaker name lookup skipped: %s", exc)
    return None


def prepare(ctx) -> None:
    """(Re)compute cleaned input and flags from ctx.prompt_text."""
    clean_in = ctx.prompt_text.lower().strip()
    for ch in ("?", ".", "!", "'", ","):
        clean_in = clean_in.replace(ch, "")
    for filler in _FILLER_STARTS:
        if clean_in.startswith(filler):
            clean_in = clean_in[len(filler):].strip()
            break
    ctx.clean_in, ctx.words = clean_in, clean_in.split()
    ctx.first_word = ctx.words[0] if ctx.words else ""
    ctx.norm_in = speech_acts.normalize(ctx.prompt_text)
    has_file_word = any(w in ctx.ALWAYS_FILE_WORDS for w in ctx.words)
    ctx.is_command = ctx.first_word in _COMMAND_VERBS and not has_file_word
    ctx.is_action_cmd = ctx.first_word in _ACTION_CMD_VERBS
    ctx.is_greeting = speech_acts.is_greeting(ctx.norm_in)


def process(ctx, deps):
    if ctx.speaker_id in _SYSTEM_IDS:
        ctx.speaker_name = ctx.user_name if ctx.user_name else "there"
    else:
        ctx.speaker_name = _enrolled_speaker_name(ctx.speaker_id) or ctx.speaker_id.title()
    ctx.speaker_key = ctx.speaker_key or session.resolve_key(ctx.speaker_id, ctx.user_name)
    prepare(ctx)
    waiting = bool(ctx.thread_key) and cs.active_pending(cs.get(ctx.thread_key)) is not None
    if ctx.clean_in in _ACKNOWLEDGEMENTS and not waiting:
        return LayerResult.stop("")
    return LayerResult.pass_through()
