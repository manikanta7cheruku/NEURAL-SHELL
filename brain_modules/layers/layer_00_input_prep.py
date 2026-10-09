"""
LAYER 0: INPUT PREPARATION

Runs first. Populates the BrainContext with the resolved speaker, the cleaned
input (clean_in, norm_in, words) and the classifier flags.

CHANGES:
    - The old version queried ChromaDB for the speaker's name on EVERY message.
      That put a database read (and, on the first message, the embedding model
      load) in front of every reply. Names now come from config and the
      session module; Chroma is consulted only if it is already loaded.
    - is_greeting is true only when the WHOLE utterance is a greeting, not
      whenever the first word is "hi", "hey", "good" ("good idea" is not one).
    - norm_in is added: contraction-expanded, punctuation-free, matched by
      whole words everywhere downstream.
"""

import logging

from brain_modules import session, speech_acts
from brain_modules.layer_result import LayerResult

_log = logging.getLogger("seven.layer00")

_ACKNOWLEDGEMENTS = {
    "okay", "ok", "alright", "yeah", "yep", "yup", "got it", "understood",
    "noted", "cool", "nice", "great", "perfect",
}
_FILLER_STARTS = [
    "and ", "also ", "now ", "then ", "please ", "can you ", "could you ",
    "hey ", "seven ",
]
_COMMAND_VERBS = [
    "open", "close", "start", "kill", "launch", "minimize", "maximize",
    "maximise", "restore", "snap",
]
_ACTION_CMD_VERBS = [
    "open", "close", "start", "kill", "launch", "minimize", "maximize",
    "maximise", "restore", "snap", "mute", "unmute", "set", "volume",
    "brightness", "play", "pause", "skip", "next", "previous", "stop",
]
_SYSTEM_IDS = {"default", "unknown", "voice_user", "speaker", "user"}


def _enrolled_speaker_name(speaker_id: str):
    """Name of an enrolled voice profile, read only if memory is already loaded."""
    try:
        from memory import core as memory_core
        inst = getattr(memory_core, "_instance", None)
        if inst is None:
            return None
        facts = inst.user_facts.get(where={"user_id": speaker_id})
        for doc in (facts or {}).get("documents", []):
            low = doc.lower()
            if "name is" in low:
                name = doc.split("is")[-1].strip().rstrip(".")
            elif "called" in low:
                name = doc.split("called")[-1].strip().rstrip(".")
            else:
                continue
            if name:
                return name
    except Exception as exc:
        _log.debug("speaker name lookup skipped: %s", exc)
    return None


def process(ctx, deps):
    # Speaker identity
    if ctx.speaker_id in _SYSTEM_IDS:
        ctx.speaker_name = ctx.user_name if ctx.user_name else "there"
    else:
        ctx.speaker_name = _enrolled_speaker_name(ctx.speaker_id) or ctx.speaker_id.title()
    ctx.speaker_key = session.resolve_key(ctx.speaker_id, ctx.user_name)

    # Cleaned input
    clean_in = ctx.prompt_text.lower().strip()
    for ch in ("?", ".", "!", "'", ","):
        clean_in = clean_in.replace(ch, "")
    for filler in _FILLER_STARTS:
        if clean_in.startswith(filler):
            clean_in = clean_in[len(filler):].strip()
            break

    ctx.clean_in = clean_in
    ctx.words = clean_in.split()
    ctx.first_word = ctx.words[0] if ctx.words else ""
    ctx.norm_in = speech_acts.normalize(ctx.prompt_text)

    # Acknowledgements need no reply (intentional silence)
    if clean_in in _ACKNOWLEDGEMENTS:
        return LayerResult.stop("")

    has_file_word = any(w in ctx.ALWAYS_FILE_WORDS for w in ctx.words)
    ctx.is_command = ctx.first_word in _COMMAND_VERBS and not has_file_word
    ctx.is_action_cmd = ctx.first_word in _ACTION_CMD_VERBS
    ctx.is_greeting = speech_acts.is_greeting(ctx.norm_in)
    return LayerResult.pass_through()
