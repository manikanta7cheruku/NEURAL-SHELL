"""
LAYER 8: LLM INFERENCE

Final layer. Always stops the pipeline.

How a reply is produced:
    1. Wait briefly for background memory retrieval (never longer than the
       configured timeout).
    2. decision_policy decides chat / grounded / deep and records what is
       UNCERTAIN, which is passed to the model as plain-text evidence status.
    3. Structured chat messages are built (stable persona first, time-limited
       history, then a reference-only block only on turns that need it).
    4. Tokens stream from Ollama through the sanitizer. Delivery modes:
           "token" console SSE, "sentence" voice, "text" one string.
    5. The curiosity engine may append ONE grounded follow-up question.
    6. Only a completed reply is recorded (history, transcript, trace). Failed
       or interrupted replies are never stored, so an error can never become
       a memory.
"""

import logging
import time

from brain_modules import (brain_settings, capabilities, chat_history, conversation_state as cs, curiosity,
                           decision_policy, goals, learning, model_catalog, ollama_client, prompt_builder,
                           speech_acts)
from brain_modules.layer_result import LayerResult
from brain_modules.response_filter import SentenceChunker, StreamSanitizer, clean_final, is_trailer

_log = logging.getLogger("seven.layer08")

_LONG = ("tell me", "explain", "describe", "list", "how does", "how do", "detail", "everything", "all about",
         "continue", "go on", "more about", "difference between", "opinion on", "thoughts on", "think about",
         "best way", "advice", "recommend", "suggestion", "write")
_COUNT = ("count", "list them", "name them", "enumerate", "from 1", "1 to", "one to")
_EARLIER = ("last time", "earlier", "we talked", "we discussed", "i told you", "i mentioned", "remember when",
            "a while ago", "yesterday", "last week")
_EMPTY = "I lost my train of thought. Say that again?"
_UNSUPPORTED = "I don't have that in what you've told me, so I won't guess."


def _rec(name: str, ms: float) -> None:
    try:
        from brain_modules.observability import record_layer_latency
        record_layer_latency(name, ms)
    except Exception:
        pass


def _budget(ctx, is_voice, profile, multiplier) -> int:
    norm = ctx.norm_in
    count = any(speech_acts.has_phrase(norm, t) for t in _COUNT)
    long = any(speech_acts.has_phrase(norm, t) for t in _LONG)
    if is_voice:
        base = 160 if count else 100 if long else 70
    else:
        base = 400 if (count or long) else 160 if ctx.web_searched else 240
    if profile.get("verbosity") == "brief":
        base = min(base, 60 if is_voice else 120)
    elif profile.get("verbosity") == "detailed":
        base = int(base * 1.5)
    return int(base * multiplier)


def _earlier_snippets(ctx):
    """Search OTHER conversations only when the user points at the past."""
    if not any(speech_acts.has_phrase(ctx.norm_in, p) for p in _EARLIER):
        return []
    try:
        from memory import conversation_store
        hits = conversation_store.search(ctx.speaker_key, ctx.resolved_text or ctx.prompt_text, limit=3,
                                         exclude_conv=ctx.conversation_id)
    except Exception as exc:
        _log.debug("history search skipped: %s", exc)
        return []
    notes = []
    for h in hits:
        who = "the user said" if h["role"] == "user" else "Seven replied"
        notes.append(f'From an earlier chat ("{h.get("title") or "untitled"}", {h["ts"][:10]}) {who}: '
                     f'"{h["content"][:160]}". This is what was said, not verified truth.')
    return notes


def process(ctx, deps):
    config = deps.get("config")
    model_name = deps.get("model_name") or config.KEY.get("brain", {}).get("model_name", "llama3")
    brain_cfg = config.KEY.get("brain", {})
    is_voice = ctx.speaker_id not in ("default",)
    key = ctx.speaker_key
    tkey = ctx.thread_key or key
    st = ctx.state or cs.get(tkey)

    original = ctx.prompt_text
    if "===" in original and "User asked:" in original:
        original = original.split("User asked:")[-1].strip()
    is_visual = "VISUAL_REPORT:" in original

    ctx.resolve_memory(float(brain_settings.get_effective(config, "memory.retrieval_timeout_ms")) / 1000.0)
    decision = decision_policy.decide(ctx, config)
    ctx.decision = decision
    if decision.mode == "clarify" and decision.clarify:
        return LayerResult.stop(decision.clarify)

    profile = learning.get_profile(key)
    humor = int(brain_settings.get_effective(config, "brain.tars_humor"))
    honesty = int(brain_settings.get_effective(config, "brain.tars_honesty"))
    try:
        from brain_modules.tone_tracker import get_bias
        hb, ob = get_bias(key)
        humor, honesty = max(0, min(100, humor + hb)), max(0, min(100, honesty + ob))
    except Exception:
        pass

    followup_hint = ""
    try:
        from brain_modules.conversation_thread import ConversationThread
        fu = ConversationThread.get_metadata(tkey, "followup_hint")
        if isinstance(fu, dict):
            followup_hint = fu.get("hint", "")
            ConversationThread.set_metadata(tkey, "followup_hint", None)
    except Exception:
        pass
    reference_hint = ""
    try:
        from brain_modules.dialogue_manager import get_last_action, should_inject_reference_hint
        if should_inject_reference_hint(ctx.clean_in):
            reference_hint = prompt_builder.build_reference_hint(get_last_action())
    except Exception:
        pass

    history = [] if is_visual else chat_history.get_messages(
        tkey, max_age_s=float(brain_settings.get_effective(config, "brain.history_ttl_seconds")))
    ctx.had_history = bool(history)
    goal_titles = [g["title"] for g in goals.relevant(key, ctx.resolved_text or original)]
    notes = list(dict.fromkeys(ctx.hints)) + _earlier_snippets(ctx)

    messages = prompt_builder.build_messages(
        user_text=original, speaker_name=ctx.speaker_name if ctx.speaker_name != "there" else "",
        history=history, humor=humor, honesty=honesty,
        tier=config.KEY.get("license", {}).get("tier", "free"), is_voice=is_voice, profile=profile,
        mood_label=ctx.mood_label, memory_facts=ctx.memory_facts, knowledge_context=ctx.knowledge_context,
        web_context=ctx.web_context, proactive_hint=ctx.proactive_hint, followup_hint=followup_hint,
        reference_hint=reference_hint, include_capabilities=ctx.inject_capabilities,
        capabilities_text=capabilities.describe_for_prompt() if ctx.inject_capabilities else "",
        notes=notes, goals=goal_titles, uncertainty=decision.uncertainty)

    grounded = bool(ctx.web_searched or ctx.knowledge_context or ctx.inject_capabilities)
    gen = brain_settings.generation(config, is_voice, decision, grounded)
    reasoning = brain_settings.get_effective(config, "brain.reasoning_model")
    model = reasoning if (decision.mode == "deep" and reasoning) else model_name
    options = {
        "temperature": gen["temperature"], "num_predict": _budget(ctx, is_voice, profile, gen["token_multiplier"]),
        "repeat_penalty": 1.1, "repeat_last_n": 64, "top_p": 0.9,
        "stop": ["###", "<reference_only>", "</reference_only>"] + (["\n\n"] if is_voice else []),
        "num_ctx": model_catalog.context_window(model),     # constant per model, so Ollama's cache stays warm
    }
    payload = {"model": model, "messages": messages, "keep_alive": "24h", "options": options}

    mode = ctx.stream_mode
    if mode == "sentence" and not brain_settings.get_effective(config, "brain.streaming"):
        mode = "text"
    started = ctx.started_at
    sources = [n for n, v in (("memory", ctx.memory_facts), ("web", ctx.web_searched),
                              ("documents", ctx.knowledge_context), ("goals", goal_titles),
                              ("earlier_chats", any(n.startswith("From an earlier chat") for n in notes))) if v]
    st.trace = {"intent": getattr(ctx.intent, "label", None), "mode": decision.mode, "sources": sources,
                "uncertainty": bool(decision.uncertainty), "model": model, "answered_by": "layer_08_llm"}

    def _finalize(parts, completed, failed):
        if failed or is_visual:
            return
        if not completed:
            # Interrupted mid-reply (the user spoke over Seven): keep what was said in the transcript,
            # but don't learn from or follow up on a half answer.
            partial = "".join(parts).strip()
            if partial and ctx.conversation_id:
                try:
                    from memory import conversation_store
                    conversation_store.add_message(ctx.conversation_id, "assistant", partial,
                                                   source="voice" if is_voice else "chat",
                                                   meta={"interrupted": True})
                except Exception as exc:
                    _log.warning("partial reply not saved: %s", exc)
            return
        text = "".join(parts).strip()
        if not text:
            return
        total_ms = int((time.time() - started) * 1000)
        _rec("llm_total", total_ms)
        st.trace["total_ms"] = total_ms
        try:
            from brain_manager import record_latency
            record_latency(total_ms)
        except Exception:
            pass
        chat_history.add_exchange(tkey, original, text)
        cs.observe_reply(st, text)
        if decision_policy.unsupported_personal_claim(text, ctx):
            try:
                from memory import learning_store
                learning_store.record_outcome(key, "answer", "unsupported_claim", "failed", text[:160],
                                              ctx.conversation_id)
            except Exception:
                pass
        try:
            from brain import save_completed_turn
            save_completed_turn(original, text, ctx.speaker_id, source="voice" if is_voice else "chat",
                                persist=True, conversation_id=ctx.conversation_id, thread_key=tkey)
        except Exception as exc:
            _log.warning("turn save failed: %s", exc)

    def _tokens():
        parts, completed, failed, first_ms = [], False, False, None
        sanitizer, stream = StreamSanitizer(), None
        try:
            stream = ollama_client.stream_chat(payload)
            for token in stream:
                if first_ms is None:
                    first_ms = int((time.time() - started) * 1000)
                    st.trace["first_token_ms"] = first_ms
                    _rec("llm_first_token", first_ms)
                out = sanitizer.feed(token)
                if out:
                    parts.append(out)
                    yield out
                if sanitizer.stopped:
                    break
            tail = sanitizer.flush()
            if tail:
                parts.append(tail)
                yield tail
            if not parts:
                failed = True
                yield _EMPTY
            else:
                q = curiosity.pick_question(ctx, config, "".join(parts))
                if q:
                    parts.append(" " + q)
                    yield " " + q
            completed = True
        except ollama_client.OllamaError as err:
            failed = True
            _log.warning("ollama error (%s): %s", err.kind, err.message)
            yield (capabilities.fallback_summary() if ctx.inject_capabilities and err.kind != "model_missing"
                   else ollama_client.friendly_error(err, model))
        finally:
            if stream is not None:
                stream.close()
            _finalize(parts, completed, failed)

    def _sentences():
        chunker = SentenceChunker()
        for piece in _tokens():
            for sentence in chunker.feed(piece):
                if not is_trailer(sentence):
                    yield sentence
        for sentence in chunker.flush():
            if not is_trailer(sentence):
                yield sentence

    if mode == "token":
        return LayerResult.stop_stream(_tokens())
    if mode == "sentence":
        return LayerResult.stop_stream(_sentences())
    text = clean_final("".join(_tokens()))
    if decision_policy.unsupported_personal_claim(text, ctx):
        return LayerResult.stop(_UNSUPPORTED)
    return LayerResult.stop(text)
