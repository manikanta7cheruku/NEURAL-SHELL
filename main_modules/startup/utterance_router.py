"""
main_modules/startup/utterance_router.py
What Seven does with something it just heard, decided in one place so every outcome is a named decision and none is a silent
`continue`.

The voice loop used to decide this inline, and several branches threw the person's words away without a word to anyone: the
next thing said after interrupting Seven was swallowed unless it was "continue"; "thanks", "okay" and "yeah" were treated as
Whisper noise even as the answer to Seven's own question; "wait, what's the weather" paused Seven and "goodbye" closed it;
anything said while a reminder was being spoken was dropped. Now decide() returns one of:

    process           act on `text` (the wake word, if any, already removed)
    wake_only         "Hey Seven" on its own: chime and open the follow-up window
    resume_interrupted  "continue" after Seven was interrupted
    pause / resume / kill    the control words, matched as whole phrases (see control_match)
    wait_speaking     Seven is talking: wait for it to finish, then process
    drop              not for Seven: `reason` says why, in words the voice log shows

Pure: the loop passes everything in, so the tests can give it any situation.
"""
import re
from dataclasses import dataclass

# Never a request, in any situation: what Whisper invents from silence.
JUNK = {"you", "the", ".", "..", "...", "", "thanks for watching", "thank you for watching"}
# Whisper also invents these from silence, but they are what a person says to Seven's own question: allowed when Seven has just
# spoken or is waiting for an answer.
ACKNOWLEDGEMENTS = {"thank you", "thanks", "bye"}
FILLER = re.compile(r"\b(please|hey|ok|okay|now|just|seven)\b")
RESUME_WORDS = ("continue", "resume", "go on", "go ahead", "keep going", "carry on")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", (text or "").lower())).strip()


def control_match(text: str, phrases, address_required=()) -> bool:
    """Is this whole utterance one of the control phrases? "stop listening" and "stop listening please" are; "wait, what's the
    weather" is not (it used to pause Seven: any short sentence containing "wait" did). A single word counts only when it is
    nearly all that was said, and the ones in `address_required` ("goodbye", "shutdown") only when Seven is addressed by name, so
    saying goodbye to someone else does not close it."""
    t = normalize(text)
    core = normalize(FILLER.sub(" ", t))
    for phrase in phrases:
        p = normalize(phrase)
        if not p:
            continue
        pw = p.split()
        if p in ("seven", "hey seven", "ok seven", "okay seven"):                 # the name itself, as a control phrase
            if t in ("seven", "hey seven", "ok seven", "okay seven"):
                return True
            continue
        hit = any(cand == p or (len(pw) >= 2 and cand.startswith(p + " ") and len(cand.split()) <= len(pw) + 2) for cand in (core, t))
        if hit and len(pw) == 1 and p in address_required and "seven" not in t.split():
            continue
        if hit:
            return True
    return False


@dataclass
class Decision:
    action: str
    text: str = ""
    reason: str = ""
    wake_found: bool = False


def decide(text, *, mode, wake_words, active, follow_up_open, pending, interrupted, speaking,
           wake_ctl=(), pause_ctl=(), kill_ctl=(), wake_check=None) -> Decision:
    """The decision for one heard utterance. `follow_up_open`: Seven has just spoken, so the next words are an answer.
    `pending`: a question of Seven's is waiting. `interrupted`: Seven was stopped mid-answer."""
    raw = (text or "").strip()
    found = False
    if mode == "wake" and active:
        if wake_check is None:
            from ears.wake_word import check_and_strip as wake_check
        stripped, found = wake_check(raw, wake_words)
        if found:
            raw = stripped
            if len(raw.strip(" ,.!?")) < 2:
                return Decision("wake_only", wake_found=True, reason="wake word: listening for your request")
        elif not (follow_up_open or pending):
            return Decision("drop", text=raw[:80], reason="no wake word")

    lower = raw.lower().strip()
    clean = normalize(raw)
    answering = follow_up_open or pending
    if clean in JUNK or len(lower) < 2:
        return Decision("drop", text=raw[:80], reason="too little to act on")
    if clean in ACKNOWLEDGEMENTS and not answering:
        return Decision("drop", text=raw[:80], reason="a stray 'thanks' with nothing to thank")

    if interrupted and any(re.search(r"\b" + re.escape(w) + r"\b", lower) for w in RESUME_WORDS):
        return Decision("resume_interrupted", text=raw, wake_found=found)

    if control_match(raw, kill_ctl, address_required=("goodbye", "shutdown")):
        return Decision("kill", text=raw, wake_found=found)
    if not active and control_match(raw, wake_ctl):
        return Decision("resume", text=raw, wake_found=found)
    if active and control_match(raw, pause_ctl):
        return Decision("pause", text=raw, wake_found=found)
    if not active:
        return Decision("drop", text=raw[:80], reason="standby: say 'wake up' to continue")
    if speaking:
        return Decision("wait_speaking", text=raw, wake_found=found)
    return Decision("process", text=raw, wake_found=found)
