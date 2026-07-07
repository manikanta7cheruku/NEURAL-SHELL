"""
=============================================================================
LAYER 8: LLM INFERENCE (Ollama)

Final layer. Always stops the pipeline with a response.

Two paths:
    Streaming     → returns ("__STREAM__", generator) to main.py
    Non-streaming → returns final response string

Uses context.memory_context, knowledge_context, web_context accumulated
by earlier layers. Builds full prompt with system_prompt + those contexts.

Response length adapts to question type:
    Count triggers  → 200 tokens
    Long triggers   → 120 tokens
    Web search      → 80 tokens
    Default         → 50 tokens

INTERVIEW TALKING POINT:
    "Layer 8 is where the expensive work happens.
     Everything before it is designed to avoid reaching this layer.
     A well-tuned Seven handles 60-70% of inputs without ever calling Ollama.
     Latency for those responses is under 5 milliseconds."
=============================================================================
"""

import time as _time
import requests
from colorama import Fore
from brain_modules.layer_result import LayerResult


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

_LONG_TRIGGERS = [
    "tell me", "explain", "describe", "what can you",
    "list", "how does", "how do", "why", "story",
    "detail", "everything", "all about", "continue",
    "go on", "more about", "your capabilities",
    "what are you capable", "what do you do",
    "what you can do", "capable of"
]

_COUNT_TRIGGERS = [
    "count", "1 to", "one to", "from 1", "from one",
    "list them", "name them", "enumerate"
]


def process(ctx, deps):
    config     = deps.get("config")
    model_name = deps.get("model_name")

    # Store original input in history
    _original_input = ctx.prompt_text
    if "===" in _original_input and "User asked:" in _original_input:
        _original_input = _original_input.split("User asked:")[-1].strip()

    if "VISUAL_REPORT:" not in _original_input and not ctx.is_action_cmd:
        try:
            from brain_modules.context_manager import add_user_turn
            add_user_turn(ctx.speaker_id, _original_input)
        except Exception:
            pass

    # Build system prompt
    _brain_cfg = config.KEY.get('brain', {})
    _humor     = int(_brain_cfg.get('tars_humor',   75))
    _honesty   = int(_brain_cfg.get('tars_honesty', 85))

    from brain_modules.prompt_builder  import build_system_prompt
    from brain_modules.context_manager import assemble_prompt

    _tier = config.KEY.get("license", {}).get("tier", "free")
    system_prompt = build_system_prompt(
        speaker_name = ctx.speaker_name,
        humor        = _humor,
        honesty      = _honesty,
        tier         = _tier,
    )

    full_prompt = assemble_prompt(
        system_prompt     = system_prompt,
        speaker_id        = ctx.speaker_id,
        web_context       = ctx.web_context,
        knowledge_context = ctx.knowledge_context,
        memory_context    = ctx.memory_context,
    )

    # Determine response length
    needs_long  = any(t in ctx.clean_in for t in _LONG_TRIGGERS)
    needs_count = any(t in ctx.clean_in for t in _COUNT_TRIGGERS)

    if needs_count:
        response_length = 200
    elif needs_long:
        response_length = 120
    elif ctx.web_searched:
        response_length = 80
    else:
        response_length = 50

    payload = {
        "model":   model_name,
        "prompt":  full_prompt,
        "stream":  False,
        "options": {
            "temperature":    0.3,
            "num_predict":    min(response_length, 150),
            "repeat_penalty": 1.2,
            "stop":           ["User:", "System:", "Seven:", "(Note", "(note",
                               "Note to self", "\n\n"],
            "num_ctx":        4096
        }
    }

    # ── Streaming path ───────────────────────────────────────────
    use_streaming = config.KEY.get('brain', {}).get('streaming', False)

    if use_streaming:
        from brain_modules.ollama_client import stream_sentences
        start_time = _time.time()
        speaker_id = ctx.speaker_id
        prompt_text = ctx.prompt_text

        def _sentence_gen():
            full_reply = []
            for sentence in stream_sentences(full_prompt, payload):
                full_reply.append(sentence)
                yield sentence

            complete_reply = " ".join(full_reply)
            elapsed = int((_time.time() - start_time) * 1000)

            try:
                from brain_manager import record_latency
                record_latency(elapsed)
            except Exception:
                pass

            if "VISUAL_REPORT:" not in prompt_text:
                try:
                    from brain_modules.context_manager import add_seven_turn
                    add_seven_turn(speaker_id, complete_reply)
                except Exception:
                    pass

        return LayerResult.stop_stream(_sentence_gen())

    # ── Non-streaming path ───────────────────────────────────────
    start_time = _time.time()

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)

        elapsed = int((_time.time() - start_time) * 1000)
        try:
            from brain_manager import record_latency
            record_latency(elapsed)
        except Exception:
            pass

        if r.status_code == 200:
            reply = r.json().get("response", "").strip() or "Listening."
            reply = _clean_response(reply)

            if "VISUAL_REPORT:" not in ctx.prompt_text:
                try:
                    from brain_modules.context_manager import add_seven_turn
                    add_seven_turn(ctx.speaker_id, reply)
                except Exception:
                    pass

            return LayerResult.stop(reply)

        print(Fore.RED + f"[BRAIN] Ollama status {r.status_code}")
        return LayerResult.stop("My brain hiccupped. Try again.")

    except requests.exceptions.ConnectionError:
        print(Fore.RED + "[BRAIN] Cannot connect to Ollama.")
        return LayerResult.stop(
            "I can't reach my brain. Run 'ollama serve' in a terminal first."
        )
    except requests.exceptions.Timeout:
        print(Fore.RED + "[BRAIN] Ollama timeout.")
        return LayerResult.stop("My brain took too long. Try again.")
    except Exception as e:
        print(Fore.RED + f"[BRAIN] Unexpected error: {e}")
        return LayerResult.stop("Something went wrong with my thinking.")


def _clean_response(text):
    """
    Strip robotic trailing phrases that LLMs append regardless of system prompt.
    These come from RLHF training — the model learned to end responses with
    assistant-style prompts. We remove them post-generation.
    """
    if not text:
        return text

    _trailers = [
        "go ahead.", "go ahead",
        "what do you need?", "what do you need",
        "what's your next request?", "whats your next request",
        "how can i help?", "how can i help you?",
        "is there anything else?", "is there anything else i can help",
        "let me know if you need anything", "let me know if",
        "feel free to ask", "feel free to",
        "anything else?", "anything else i can",
        "what would you like", "what else can i",
        "i'm here if you need", "im here if",
        "just let me know", "just ask if",
        "what's next?", "whats next",
        "what can i do for you", "how may i help",
        "ready when you are", "standing by",
        "awaiting your", "next command",
    ]

    text_lower = text.lower().rstrip()

    for trailer in _trailers:
        if text_lower.endswith(trailer):
            cut = len(text) - len(trailer)
            text = text[:cut].rstrip(" .,!-—")
            text_lower = text.lower().rstrip()
            break

    import re
    text = re.sub(r'\s*[/\\]+\s*$', '', text).strip()

    return text.strip()