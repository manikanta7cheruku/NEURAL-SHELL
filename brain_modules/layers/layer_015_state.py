"""
LAYER 015: CONVERSATION STATE

1. If Seven asked something and is waiting, read this message as the answer
   (yes/no to "is it your favorite?", a reason, an alias confirmation, a
   confirmation of a risky action).
2. Update working memory and resolve references ("I love that movie" ->
   "I love Interstellar"), or ask which one when it is ambiguous.
"""

import logging
import re

from brain_modules import conversation_state as cs
from brain_modules import correction_detector, fact_extractor, memory_gate, speech_acts
from brain_modules.layer_result import LayerResult
from brain_modules.layers import layer_00_input_prep as prep
from memory import learning_store

_log = logging.getLogger("seven.layer015")


def _answer_gap(ctx, st, pend, kind_answer, text):
    gap_id = pend.data.get("gap_id")
    kind = pend.type.split(":", 1)[1] if ":" in pend.type else pend.type

    def done(status="answered"):
        if gap_id:
            learning_store.set_gap_status(gap_id, status)
        learning_store.record_outcome(ctx.speaker_key, "question", kind, status, conversation_id=ctx.conversation_id)
        st.pending = None
        st.ignored = 0 if status == "answered" else st.ignored

    if kind == "favorite_promotion":
        if kind_answer == "yes":
            from memory import fact_service
            k, v = pend.data["kind"], pend.data["value"]
            fact_service.remember(ctx.speaker_key, fact_extractor.ExtractedFact(
                f"favorite_{k}", v, f"User's favorite {k} is {v}", "preference", 0.95, True),
                source_text=text, source_msg_id=ctx.user_msg_id, conversation_id=ctx.conversation_id)
            done()
            return LayerResult.stop(f"Noted. {v} is your favorite {k}.")
        if kind_answer == "no":
            done()
            return LayerResult.stop("Got it. One of several, then.")
    elif kind in ("reason_change", "reason", "goal_detail"):
        if kind_answer == "no" or speech_acts.normalize(text) in ("i dont know", "no reason", "not sure", "idk"):
            done("declined")
            return LayerResult.stop("Fair enough.")
        other_intent = (bool(fact_extractor.extract_facts(text)) or bool(correction_detector.detect_correction(text))
                        or speech_acts.is_question(text))
        if kind_answer == "other" and 2 <= len(text.split()) <= 40 and not other_intent:
            if kind == "goal_detail":
                learning_store.set_goal_detail(int(pend.data["goal_id_ref"]), text)
            else:
                from memory import fact_service
                slot = pend.data.get("slot") or pend.data.get("current_slot")
                rf = fact_extractor.reason_fact(slot, text) if slot else None
                if rf:
                    fact_service.remember(ctx.speaker_key, rf, source_text=text, source_msg_id=ctx.user_msg_id,
                                          conversation_id=ctx.conversation_id, origin="explicit")
            done()
            ctx.hints.append("The user just answered your question. Acknowledge it in one short, natural sentence.")
            return None
    # Anything else: the user moved on.
    st.ignored += 1
    st.pending = None
    if gap_id:
        learning_store.set_gap_status(gap_id, "open" if st.ignored < 2 else "declined")
    return None


def _handle_pending(ctx, deps, st, pend, text):
    ans = cs.classify_answer(text)
    if pend.type.startswith("gap:") or pend.type == "reason_for":
        if pend.type == "reason_for":
            pend.type = "gap:reason"
        return _answer_gap(ctx, st, pend, ans, text)
    if pend.type == "alias_confirm":
        st.pending = None
        if ans == "yes":
            try:
                import config
                aliases = dict(config.KEY.get("commands", {}).get("app_aliases", {}))
                aliases[pend.data["alias"]] = pend.data["target"]
                config.update_config({"commands": {"app_aliases": aliases}})
                learning_store.record_outcome(ctx.speaker_key, "routing", "alias", "success", pend.data["alias"])
                return LayerResult.stop(f"Done. When you say \"{pend.data['alias']}\" I'll open {pend.data['target']}.")
            except Exception as exc:
                _log.warning("alias save failed: %s", exc)
                return LayerResult.stop("I couldn't save that shortcut.")
        return LayerResult.stop("Okay, I won't remember that.") if ans == "no" else None
    if pend.type == "confirm_action":
        st.pending = None
        if ans == "yes":
            ctx.confirmed = True
            return LayerResult.stop(f"Okay. {pend.data['tags']}")
        if ans == "no":
            return LayerResult.stop("Okay, leaving it as it is.")
        return None
    if pend.type == "open_file_suggestion":
        st.pending = None
        if ans == "yes":
            from hands.files import open_file
            name = pend.data["name"]
            return LayerResult.stop(f"Opening {name}." if open_file(pend.data["path"]) else f"Windows couldn't open {name}.")
        if ans == "no":
            return LayerResult.stop("Okay. Tell me another part of the name and I'll look again.")
        return None
    if pend.type == "file_where":
        st.pending = None
        low = text.lower().strip(" .!?")
        # "in the system", "on my pc", "in downloads", "on S drive": every drive was already searched, so a place
        # can't find more. Say so plainly and ask for what can help, a different word from the name.
        m = re.fullmatch(r"(?:it'?s |its |maybe |probably )?(?:somewhere )?(?:in|on|inside|under) (?:the |my |this )?(.+?)", low)
        if m and len(m.group(1).split()) <= 4:
            place = m.group(1)
            whole = re.fullmatch(r"(?:system|pc|computer|laptop|drives?|disk|machine)", place)
            where = "every drive I can see on this PC" if whole else f"every drive I can see, {place} included"
            return LayerResult.stop(f"I searched {where}, and nothing is named like \"{pend.data['query']}\". "
                                    "Another word from the file name would help me find it.")
        return None
    if pend.type == "clarify_ref":
        st.pending = None
        low = text.lower()
        for name in pend.data["names"]:
            if name.lower() in low:
                ctx.prompt_text = pend.data["original"].replace(pend.data["phrase"], name, 1)
                prep.prepare(ctx)
                return None
        return None
    return None


def process(ctx, deps):
    st = cs.get(ctx.thread_key)
    ctx.state = st
    ctx.mood_label = "neutral"
    try:
        ctx.mood_label = deps["mood_engine"].get_label()
    except Exception:
        pass

    pend = cs.active_pending(st)
    if pend:
        reply = _handle_pending(ctx, deps, st, pend, ctx.prompt_text)
        if reply is not None:
            return reply

    cs.observe_user(st, ctx.prompt_text)
    if memory_gate.parse_recall_query(ctx.norm_in) is not None:
        ctx.resolved_text = ctx.prompt_text   # memory resolves "that language" from stored slots
        return LayerResult.pass_through()
    res = cs.resolve(ctx.prompt_text, st)
    ctx.resolved_text = res.text
    ctx.resolution_kind = res.kind
    if res.substitutions:
        phrase, name = res.substitutions[0]
        ctx.hints.append(f'In the user\'s message, "{phrase}" refers to {name}.')
        ctx.norm_in = speech_acts.normalize(res.text)
    elif res.ambiguous:
        m = cs._RE_REF.search(ctx.prompt_text) or cs._RE_BARE.search(ctx.prompt_text)
        cs.set_pending(st, "clarify_ref", {"names": res.ambiguous, "original": ctx.prompt_text,
                                           "phrase": m.group(0) if m else ""}, ttl=2)
        ctx.ambiguity = res.ambiguous
        return LayerResult.stop(f"Do you mean {' or '.join(res.ambiguous[:3])}?")
    return LayerResult.pass_through()
