"""
LAYER 8: LLM INFERENCE

Final layer. Always stops the pipeline.

HOW A REPLY IS PRODUCED:
    1. Wait briefly for the semantic memory search started earlier (if any).
    2. Build structured chat messages (prompt_builder): stable persona first,
       recent time-limited history, and a reference-only block on the turns
       that need memory, web, documents or capabilities.
    3. Stream tokens from Ollama through the sanitizer, which removes role
       prefixes, echoed tags and any "###" action text.
    4. Deliver in the mode the caller asked for:
           "token"    raw token stream (console, Server-Sent Events)
           "sentence" speakable sentences (voice, first chunk flushed early)
           "text"     one finished string
    5. On completion ONLY, record the exchange (history, session thread,
       latency). A failed or interrupted reply is never stored, so an error
       message can never become a "memory".

Measured and logged per turn: time to first token, total time.
"""

import logging
import time

from brain_modules import capabilities, chat_history, learning, ollama_client, prompt_builder, speech_acts
from brain_modules.layer_result import LayerResult
from brain_modules.response_filter import SentenceChunker, StreamSanitizer, clean_final, is_trailer

_log = logging.getLogger("seven.layer08")

_LONG_TRIGGERS = (
    "tell me", "explain", "describe", "list", "how does", "how do", "detail",
    "everything", "all about", "continue", "go on", "more about", "difference between",
    "opinion on", "thoughts on", "think about", "best way", "advice", "recommend",
    "suggestion", "write",
)
_COUNT_TRIGGERS = ("count", "list them", "name them", "enumerate", "from 1", "1 to", "one to")
_FALLBACK_EMPTY = "I lost my train of thought. Say that again?"


def _rec(name: str, ms: float) -> None:
    try:
        from brain_modules.observability import record_layer_latency
        record_layer_latency(name, ms)
    except Exception:
        pass


def _options(ctx, is_voice, humor, profile, model_name):
    """Generation options. num_ctx stays constant per model so Ollama never reloads it."""
    norm = ctx.norm_in
    count = any(speech_acts.has_phrase(norm, t) for t in _COUNT_TRIGGERS)
    long = any(speech_acts.has_phrase(norm, t) for t in _LONG_TRIGGERS)
    if is_voice:
        budget = 160 if count else 100 if long else 70
    else:
        budget = 400 if (count or long) else 160 if ctx.web_searched else 240
    if profile.get("verbosity") == "brief":
        budget = min(budget, 60 if is_voice else 120)
    elif profile.get("verbosity") == "detailed":
        budget = int(budget * 1.5)

    grounded = ctx.web_searched or bool(ctx.knowledge_context)
    base = 0.35 if is_voice else 0.3
    temperature = 0.2 if grounded else min(0.7, round(base + (humor / 100) * 0.35, 2))
    stops = ["###", "<reference_only>", "</reference_only>"] + (["\n\n"] if is_voice else [])
    return {
        "temperature": temperature, "num_predict": budget, "repeat_penalty": 1.1,
        "repeat_last_n": 64, "top_p": 0.9, "stop": stops,
        "num_ctx": 2048 if "tinyllama" in (model_name or "").lower() else 4096,
    }


def process(ctx, deps):
    config = deps.get("config")
    model_name = deps.get("model_name") or config.KEY.get("brain", {}).get("model_name", "llama3")
    brain_cfg = config.KEY.get("brain", {})
    mem_cfg = config.KEY.get("memory", {})
    is_voice = ctx.speaker_id not in ("default",)
    key = ctx.speaker_key

    original = ctx.prompt_text
    if "===" in original and "User asked:" in original:
        original = original.split("User asked:")[-1].strip()
    is_visual = "VISUAL_REPORT:" in original

    ctx.resolve_memory(float(mem_cfg.get("retrieval_timeout_ms", 450)) / 1000.0)

    profile = learning.get_profile(key)
    humor, honesty = int(brain_cfg.get("tars_humor", 75)), int(brain_cfg.get("tars_honesty", 85))
    try:
        from brain_modules.tone_tracker import get_bias
        h_bias, o_bias = get_bias(key)
        humor, honesty = max(0, min(100, humor + h_bias)), max(0, min(100, honesty + o_bias))
    except Exception:
        pass

    mood_label = "neutral"
    try:
        mood_label = deps["mood_engine"].get_label()
    except Exception:
        pass

    followup_hint = ""
    try:
        from brain_modules.conversation_thread import ConversationThread
        fu = ConversationThread.get_metadata(key, "followup_hint")
        if isinstance(fu, dict):
            followup_hint = fu.get("hint", "")
            ConversationThread.set_metadata(key, "followup_hint", None)
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
        key, max_age_s=float(brain_cfg.get("history_ttl_seconds", 1800)))

    messages = prompt_builder.build_messages(
        user_text=original, speaker_name=ctx.speaker_name if ctx.speaker_name != "there" else "",
        history=history, humor=humor, honesty=honesty,
        tier=config.KEY.get("license", {}).get("tier", "free"), is_voice=is_voice,
        profile=profile, mood_label=mood_label, memory_facts=ctx.memory_facts,
        knowledge_context=ctx.knowledge_context, web_context=ctx.web_context,
        proactive_hint=ctx.proactive_hint, followup_hint=followup_hint,
        reference_hint=reference_hint, include_capabilities=ctx.inject_capabilities,
        capabilities_text=capabilities.describe_for_prompt() if ctx.inject_capabilities else "")

    payload = {"model": model_name, "messages": messages, "keep_alive": "24h",
               "options": _options(ctx, is_voice, humor, profile, model_name)}

    mode = ctx.stream_mode
    if mode == "sentence" and not brain_cfg.get("streaming", True):
        mode = "text"
    started = ctx.started_at

    def _finalize(parts, completed, failed):
        if not completed or failed or is_visual:
            return
        text = "".join(parts).strip()
        if not text:
            return
        total_ms = int((time.time() - started) * 1000)
        _rec("llm_total", total_ms)
        try:
            from brain_manager import record_latency
            record_latency(total_ms)
        except Exception:
            pass
        chat_history.add_exchange(key, original, text)
        try:
            from brain import save_completed_turn
            save_completed_turn(original, text, ctx.speaker_id, source="voice" if is_voice else "chat",
                                persist=True)
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
                    _rec("llm_first_token", first_ms)
                    _log.info("first token after %d ms", first_ms)
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
                yield _FALLBACK_EMPTY
            completed = True
        except ollama_client.OllamaError as err:
            failed = True
            msg = (capabilities.fallback_summary() if ctx.inject_capabilities and err.kind != "model_missing"
                   else ollama_client.friendly_error(err, model_name))
            _log.warning("ollama error (%s): %s", err.kind, err.message)
            yield msg
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
    return LayerResult.stop(clean_final("".join(_tokens())))
