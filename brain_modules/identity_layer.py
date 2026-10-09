"""
brain_modules/identity_layer.py

Two fast-path handlers used by pipeline layers:
    handle_name_setting   ("my name is Mani", "call me Mani")
    handle_tars_controls  ("set your humor to 80", "what is your honesty level")

BUGS FIXED IN THIS REWRITE:
    Name setting
      - "call me" matched anywhere, so "call me later" or "can you call me a
        taxi" renamed the user. Now the sentence must START with a naming
        phrase and the result must pass name validation.
      - Any input containing "my name" plus the substring "to" (as in
        "today", "tomorrow", "stop") was treated as a rename.
      - Questions are never treated as statements.
    TARS controls
      - "direct" matched inside "directory" and "set" matched anywhere, so
        "set up a new directory" asked for an honesty percentage. Matching
        is now whole-word and needs an explicit "your" / "level" / "setting".

The dead greeting/identity code that lived here (it was never wired into the
pipeline, and contained an over-broad greeting match) has been removed.
Greetings are in social_engine, identity in layer_03_identity.
"""

import logging
import re

from brain_modules import fact_extractor, speech_acts

_log = logging.getLogger("seven.identity")

_NAME_RE = re.compile(
    r"^(?:(?:hey|ok|okay|hi)\s+seven[,\s]+|please\s+|seven[,\s]+)?"
    r"(?:my name is(?: now)?|my name's|i am called|i'm called|people call me|you can call me|"
    r"call me|change my name to|rename me to)\s+(?P<name>.+)$",
    re.IGNORECASE,
)
_NOT_NAMES = frozenset({
    "later", "back", "when", "tomorrow", "maybe", "please", "soon", "now", "today",
    "tonight", "if", "crazy", "stupid", "names", "again", "anything", "whatever",
})


def reset_session() -> None:
    """Kept for the brain's reset hook. This module holds no session state now."""


def handle_name_setting(prompt_text, clean_in, speaker_id, speaker_name,
                        seven_memory, USER_NAME):
    """
    Detect and handle a name-setting statement.

    Returns None when the input is not a name statement, otherwise
    (new_name, confirmation). The name is saved to memory and to config, and
    the caller updates its USER_NAME global.
    """
    raw = (prompt_text or "").strip()
    if not raw or speech_acts.is_question(raw):
        return None
    m = _NAME_RE.match(raw.rstrip(".!"))
    if not m:
        return None

    candidate = re.split(r"\b(?:not|please|okay|ok|right)\b", m.group("name"), maxsplit=1,
                         flags=re.IGNORECASE)[0]
    candidate = " ".join(candidate.strip(" .,!?").split()[:2])
    if candidate.lower() in _NOT_NAMES:
        return None
    new_name = fact_extractor.valid_name(candidate)
    if not new_name:
        return None

    system_ids = ("default", "unknown", "voice_user", "")
    try:
        if speaker_id not in system_ids:
            seven_memory.store_fact(f"Speaker {speaker_id}'s name is {new_name}",
                                    category="identity", user_id=speaker_id)
        else:
            import config
            uid = (config.KEY.get("identity", {}).get("user_name", "") or "default").lower()
            seven_memory.store_fact(f"User's name is {new_name}", category="identity", user_id=uid)
            identity = config.KEY.get("identity", {})
            identity["user_name"] = new_name
            config.update_config({"identity": identity})
    except Exception as exc:
        _log.warning("name save partially failed: %s", exc)

    return new_name, f"Got it. {new_name} it is."


# ---------------------------------------------------------------------------
# TARS personality controls
# ---------------------------------------------------------------------------

_SET_VERBS = frozenset({"set", "change", "make", "put", "adjust", "turn"})
_HUMOR_WORDS = frozenset({"humor", "humour", "sarcasm"})
_HONESTY_WORDS = frozenset({"honesty", "brutal"})
_CONTEXT_WORDS = frozenset({"your", "level", "setting", "percent"})
_QUERY_WORDS = frozenset({"what", "current", "level", "how"})


def _humor_label(v: int) -> str:
    return ("deadpan" if v <= 10 else "mostly serious" if v <= 30 else
            "dry wit" if v <= 60 else "TARS mode" if v <= 85 else "maximum sarcasm")


def _honesty_label(v: int) -> str:
    return ("diplomatic" if v <= 20 else "tactful" if v <= 50 else
            "direct" if v <= 80 else "blunt" if v <= 95 else "no filter")


def handle_tars_controls(clean_in, words, config):
    """
    Read or change the humor / honesty sliders by voice or chat.
    Returns a short confirmation, or None when the input is not a control.
    """
    toks = set(words or clean_in.split())
    humor = bool(toks & _HUMOR_WORDS)
    honesty = bool(toks & _HONESTY_WORDS) or ("honest" in toks and "your" in toks)
    if not (humor or honesty):
        return None
    has_context = bool(toks & _CONTEXT_WORDS) or "%" in clean_in
    number = re.search(r"\b(\d{1,3})\b", clean_in)

    if toks & _SET_VERBS and has_context:
        if not number:
            return ("Give me a number. What percentage humor do you want?" if humor
                    else "Give me a number. What percentage honesty do you want?")
        value = max(0, min(100, int(number.group(1))))
        try:
            brain_cfg = config.KEY.get("brain", {})
            if humor:
                brain_cfg["tars_humor"] = value
                config.update_config({"brain": brain_cfg})
                return f"Humor set to {value}%. {_humor_label(value).capitalize()}."
            brain_cfg["tars_honesty"] = value
            config.update_config({"brain": brain_cfg})
            return f"Honesty set to {value}%. {_honesty_label(value).capitalize()}."
        except Exception as exc:
            _log.warning("TARS setting save failed: %s", exc)
            return "Could not save that setting."

    if toks & _QUERY_WORDS and has_context and not (toks & _SET_VERBS):
        brain_cfg = config.KEY.get("brain", {})
        if humor:
            cur = int(brain_cfg.get("tars_humor", 75))
            return f"Humor is at {cur}%. {_humor_label(cur).capitalize()}."
        cur = int(brain_cfg.get("tars_honesty", 85))
        return f"Honesty is at {cur}%. {_honesty_label(cur).capitalize()}."
    return None
