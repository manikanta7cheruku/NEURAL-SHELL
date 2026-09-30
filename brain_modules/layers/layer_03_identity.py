"""
Layer 03: Identity and Self-Knowledge Layer

Fast-paths self-knowledge queries (hardware, version, model, capabilities,
identity, origin) directly from the ground-truth self_model with zero LLM latency.
Uses varied natural responses to prevent robotic repetition.
"""

import re
import random
from typing import Optional
from brain_modules.layer_result import LayerResult
from brain_modules import self_model

# Entity keywords for intent extraction
_VERSION_NOUNS = {"version", "build", "release", "patch", "edition"}
_MODEL_NOUNS = {"model", "llm", "weights", "checkpoint", "llama", "parameters"}
_HARDWARE_NOUNS = {
    "hardware", "specs", "specifications", "ram", "memory", "gpu", "cpu",
    "processor", "graphics", "vram", "disk", "storage", "machine", "rig", "device"
}

# User name queries. If input contains 'my name' plus a question marker,
# this is a user-name query, NOT a Seven identity query.
_USER_NAME_MARKERS = {"my name", "am i", "know me", "remember me"}

_IDENTITY_PHRASES = [
    "who are you", "what are you", "your name", "whats your name",
    "what your name", "who made you", "who created you", "who built you",
    "tell me about yourself", "introduce yourself", "your identity",
    "you are who", "you who", "state your name",
]

_ORIGIN_PHRASES = [
    "where are you from", "where you from", "where u from",
    "where do you live", "where are you located",
    "where are you hosted", "where do you run", "where are you",
    "where do you run from", "where you at",
]

_CAPABILITY_PHRASES = [
    "what can you do", "what are your capabilities", "what do you do",
    "what are your features", "how can you help", "what are your skills",
    "help me with", "what functions do you have", "what you can do",
    "what can you help",
]

_QUERY_STARTERS = {"what", "which", "show", "tell", "current", "how", "display", "check", "who", "where"}


def _classify_intent(text: str) -> Optional[str]:
    """
    Classifies self-knowledge intent based on token and phrase matching.
    Contractions (what's, you're, where's) are normalized before matching
    so weak local models never see identity questions.
    """
    # Normalize contractions BEFORE stripping punctuation
    normalized = text.lower()
    normalized = normalized.replace("what's", "whats")
    normalized = normalized.replace("who's", "whos")
    normalized = normalized.replace("where's", "wheres")
    normalized = normalized.replace("you're", "youre")
    normalized = normalized.replace("what is", "whats")
    normalized = normalized.replace("who is", "whos")
    normalized = normalized.replace("where is", "wheres")

    cleaned = re.sub(r"[^\w\s]", " ", normalized).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    tokens = set(cleaned.split())

    # 0. Reject user-name queries. "What's my name" is NOT a Seven identity question.
    # Those are handled by Layer 05 memory or Layer 08 LLM with proper context.
    for marker in _USER_NAME_MARKERS:
        if marker in cleaned:
            return None

    # 1. Identity phrases (Seven's own identity)
    for phrase in _IDENTITY_PHRASES:
        if phrase in cleaned:
            return "identity"

    # 2. Origin phrases
    for phrase in _ORIGIN_PHRASES:
        if phrase in cleaned:
            return "origin"

    # 3. Capability phrases
    for phrase in _CAPABILITY_PHRASES:
        if phrase in cleaned:
            return "capabilities"

    # 4. Version queries
    if tokens & _VERSION_NOUNS:
        return "version"

    # 5. Model / LLM queries
    if tokens & _MODEL_NOUNS:
        return "model"

    # 6. Hardware / System Specs queries
    if tokens & _HARDWARE_NOUNS:
        if tokens & _QUERY_STARTERS or "my" in tokens or "your" in tokens or "this" in tokens or "system" in tokens:
            return "hardware"

    return None


def _answer_identity() -> str:
    state = self_model.get_runtime_state()
    options = [
        f"I am {state['name']}, an intelligent local AI operating system created by {state['creator']}. I run entirely on your local machine.",
        f"I'm {state['name']}. Built by {state['creator']}, I operate as your fully local AI assistant with direct system automation.",
        f"I'm {state['name']}, running locally on this machine. I was built by {state['creator']} to handle tasks, automation, and intelligence without cloud reliance.",
    ]
    return random.choice(options)


def _answer_origin() -> str:
    state = self_model.get_runtime_state()
    options = [
        f"I run completely locally on this {state['os']} machine. No cloud servers, no remote telemetry.",
        f"I'm hosted right here on your local system, engineered by {state['creator']}.",
        f"I don't live in the cloud. I operate directly from your local hardware on {state['os']}.",
    ]
    return random.choice(options)


def _answer_version() -> str:
    state = self_model.get_runtime_state()
    options = [
        f"Seven OS version {state['version']} ({state['license_tier'].capitalize()} Tier).",
        f"Currently running build v{state['version']} under the {state['license_tier'].capitalize()} license.",
        f"You are running Seven OS v{state['version']}.",
    ]
    return random.choice(options)


def _answer_model() -> str:
    state = self_model.get_runtime_state()
    options = [
        f"Running local model {state['model_name']} via Ollama.",
        f"Active model is {state['model_name']}, executing fully on local compute.",
        f"I am powered by {state['model_name']} running locally through Ollama.",
    ]
    return random.choice(options)


def _answer_hardware() -> str:
    state = self_model.get_runtime_state()
    hw = state["hardware"]
    gpu_part = f", GPU: {hw['gpu_name']} ({hw['vram_gb']}GB VRAM)" if hw.get("gpu_name") and hw["gpu_name"] != "Integrated Graphics" else ""
    return (
        f"Host System: {state['os']}, {hw['ram_gb']}GB RAM, "
        f"CPU: {hw['cpu_name']} ({hw['cpu_cores']} cores){gpu_part}."
    )


def _answer_capabilities() -> str:
    state = self_model.get_runtime_state()
    caps = ", ".join(state["capabilities"][:5])
    return f"I can assist with {caps}, and local system automation. What would you like to work on?"


def _answer_user_name(ctx) -> Optional[str]:
    """
    Answer 'what is my name' from context and config.
    Returns None if name unknown so LLM can offer to remember it.
    """
    # Priority 1: ctx.user_name from brain.py (freshest, config-backed)
    user_name = getattr(ctx, "user_name", None) or getattr(ctx, "speaker_name", None)
    if user_name and user_name.strip().lower() not in ("admin", "there", "default", "unknown", ""):
        options = [
            f"Your name is {user_name}.",
            f"You are {user_name}.",
            f"{user_name}. That is what you told me.",
        ]
        return random.choice(options)

    return None


def _is_user_name_query(text: str) -> bool:
    """Detect user-name questions distinctly from Seven-identity questions."""
    normalized = text.lower()
    normalized = normalized.replace("what's", "whats").replace("what is", "whats")
    cleaned = re.sub(r"[^\w\s]", " ", normalized).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    patterns = [
        "whats my name", "what my name", "my name",
        "who am i", "do you know me", "do you remember me",
        "know my name", "remember my name", "recall my name",
    ]
    for p in patterns:
        if p in cleaned:
            return True
    return False


def process(ctx, deps=None) -> LayerResult:
    """
    Top-level pipeline process function called by pipeline.py.
    """
    raw_text = getattr(ctx, "clean_in", None) or getattr(ctx, "prompt_text", None) or getattr(ctx, "user_input", "")
    user_input = str(raw_text).strip()

    if not user_input:
        return LayerResult.pass_through()

    # User name queries route to dedicated answerer, not Seven identity block
    if _is_user_name_query(user_input):
        reply = _answer_user_name(ctx)
        if reply:
            return LayerResult.stop(reply)
        return LayerResult.stop("You have not told me your name yet. Say 'my name is ...' and I will remember it.")

    intent = _classify_intent(user_input)

    if intent == "version":
        return LayerResult.stop(_answer_version())
    if intent == "model":
        return LayerResult.stop(_answer_model())
    if intent == "hardware":
        return LayerResult.stop(_answer_hardware())
    if intent == "identity":
        return LayerResult.stop(_answer_identity())
    if intent == "origin":
        return LayerResult.stop(_answer_origin())
    if intent == "capabilities":
        return LayerResult.stop(_answer_capabilities())

    return LayerResult.pass_through()