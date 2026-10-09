"""
LAYER 03: IDENTITY AND SELF-KNOWLEDGE

Answers questions about Seven itself and the machine instantly and
deterministically: who it is, who made it, version, model, hardware, what
it can do, plus the time and date (a language model cannot know those).

BUGS FIXED IN THIS REWRITE:
    The old version fired on any sentence that merely CONTAINED a word like
    "model", "version", "machine", "memory" or "device", with a question word
    elsewhere. "How does machine learning work" returned the host hardware,
    "what is a business model" returned Seven's model name, and "what version
    of Python do I need" returned Seven's own version. Every self-knowledge
    intent now requires an explicit reference to Seven ("you", "your") or the
    user's own machine ("my", "this"), and is matched as a whole phrase.

IDENTITY ENFORCEMENT:
    Name and creator are constants, answered here and enforced again in the
    system prompt. Attempts to rename Seven, to make it "act as" another AI,
    or to override its instructions get a calm in-character refusal.
"""

import random
import re
from datetime import datetime

from brain_modules import capabilities, self_model, session
from brain_modules.layer_result import LayerResult

_JAILBREAK = re.compile(
    r"\b(?:you are now|your name is now|call yourself|from now on (?:you are|your name is)|"
    r"pretend (?:that )?you are|pretend to be|ignore (?:all |your |the )?(?:previous |prior |above )?"
    r"(?:instructions|rules|prompt)|forget (?:all |your )(?:instructions|rules)|developer mode|"
    r"jailbreak|dan mode|act as (?:chatgpt|gpt|claude|gemini|an? unrestricted))\b")
_NOT_ME = re.compile(
    r"\b(?:are you|you are|is this) (?:just )?(?:chatgpt|gpt|gpt 4|openai|claude|anthropic|gemini|"
    r"google|bard|llama|meta ai|copilot|siri|alexa)\b")

_IDENTITY = (
    r"who are you(?: really| exactly)?", r"what are you(?: really| exactly)?",
    r"who is this", r"tell me about yourself", r"introduce yourself",
    r"what should i call you", r"what do i call you", r"what do people call you",
)
_CREATOR = re.compile(
    r"\bwho (?:made|created|built|developed|designed|programmed|owns) you\b|"
    r"\bwho is your (?:creator|developer|maker|owner)\b|"
    r"\bwhich company (?:made|built|created) you\b")
_ORIGIN = (
    r"where are you from", r"where do you (?:come from|live|run)", r"where were you (?:made|built)",
    r"where are you", r"where are you based",
)
_PRIVACY = re.compile(
    r"\b(?:is my data|are my (?:chats|conversations|files))\b.*\b(?:safe|private|secure)\b|"
    r"\bdo you (?:send|share|upload|collect|sell) (?:my |any )?(?:data|conversations|information|files)\b|"
    r"\bare you (?:private|spying on me)\b|\bdo you need (?:the )?internet\b")

_USER_NAME = (
    r"what is my name", r"who am i", r"do you (?:know|remember) my name",
    r"do you know who i am", r"what do you call me", r"what did i say my name was",
)
_TIME = (
    r"what time is it(?: now| right now)?", r"what is the (?:current )?time(?: now| right now)?",
    r"(?:tell me )?the (?:current )?time(?: please)?", r"current time", r"time now",
)
_DATE = (
    r"what is (?:the |todays )?date(?: today)?", r"what is the date today", r"what day is (?:it|today)(?: today)?",
    r"what is today", r"todays date", r"what date is it(?: today)?", r"which day is (?:it|today)",
)
_VERSION = (
    r"(?:what|which) version are you(?: running)?", r"(?:what|which) version of seven(?: are you running)?",
    r"(?:what is )?your version", r"seven version", r"(?:what|which) build are you",
    r"what version is this", r"what version is seven",
)
_MODEL = (
    r"(?:what|which) (?:ai |language |llm )?model (?:are you|do you use|are you using|are you running|is this|is seven using)",
    r"what is your model", r"your model", r"which llm are you(?: using)?",
    r"what (?:are you|is seven) (?:running|powered) (?:on|by)", r"what model",
)
_HARDWARE = (
    r"what (?:are )?(?:my|the|this) (?:pc |computer |system |laptop )?(?:specs|hardware)",
    r"(?:my|this) (?:pc |computer |system |laptop )?(?:specs|hardware)",
    r"how much (?:ram|memory|vram) do i have", r"what (?:gpu|cpu|graphics card|processor) do i have",
    r"what is my (?:gpu|cpu|ram|processor|graphics card)", r"system (?:specs|info|information)",
)
_CAPABILITY = (
    r"what can you do(?: for me)?", r"what do you do", r"what are your (?:capabilities|features|skills|abilities)",
    r"what are you capable of", r"how can you help(?: me)?", r"what can you help (?:me )?with",
    r"help", r"list your (?:commands|features|capabilities)", r"what commands do you have",
    r"what are you good at", r"(?:show|tell) me what you can do",
)
_ACTIVITY_WORDS = {"doing", "up", "thinking", "working", "going", "saying", "talking",
                   "listening", "building", "reading", "watching"}


def _fullmatch_any(patterns, norm: str) -> bool:
    return any(re.fullmatch(p, norm) for p in patterns)


def _identity_reply() -> str:
    return random.choice([
        "I am Seven, created by Seven Labs.",
        "I'm Seven. Seven Labs built me.",
        "Seven. Created by Seven Labs, living on this machine.",
    ])


def _time_reply() -> str:
    return f"It's {datetime.now().strftime('%I:%M %p').lstrip('0')}."


def _date_reply() -> str:
    now = datetime.now()
    return f"{now.strftime('%A, %B')} {now.day}."


def _user_name_reply(ctx) -> str:
    name = session.display_name("default", getattr(ctx, "user_name", None))
    if name:
        return random.choice([f"Your name is {name}.", f"You're {name}.", f"{name}."])
    return "You haven't told me yet. Say 'my name is' and your name, and I'll remember it."


def process(ctx, deps=None) -> LayerResult:
    norm = getattr(ctx, "norm_in", "") or ""
    if not norm:
        return LayerResult.pass_through()

    # Identity enforcement first: nobody renames Seven.
    if _JAILBREAK.search(norm):
        return LayerResult.stop(random.choice([
            "Nice try. I'm Seven, built by Seven Labs, and that isn't changing.",
            "No. I'm Seven, made by Seven Labs. Ask me something I can actually help with.",
        ]))
    if _NOT_ME.search(norm):
        return LayerResult.stop(
            "No. I'm Seven, built by Seven Labs. I run on a local model on this machine.")

    if _fullmatch_any(_USER_NAME, norm):
        return LayerResult.stop(_user_name_reply(ctx))
    if _fullmatch_any(_TIME, norm):
        return LayerResult.stop(_time_reply())
    if _fullmatch_any(_DATE, norm):
        return LayerResult.stop(_date_reply())

    words = set(norm.split())
    activity = bool(words & _ACTIVITY_WORDS)
    if _CREATOR.search(norm) or (not activity and _fullmatch_any(_IDENTITY, norm)) or (
            "your name" in norm and len(norm.split()) <= 8 and not activity):
        return LayerResult.stop(_identity_reply())
    if _fullmatch_any(_ORIGIN, norm):
        return LayerResult.stop("I run locally on this machine. Seven Labs built me; nothing about you leaves it.")
    if _PRIVACY.search(norm):
        return LayerResult.stop(
            "Everything stays on this machine. What I learn about you is stored locally and never sent anywhere.")

    state = None
    if _fullmatch_any(_VERSION, norm):
        state = self_model.get_runtime_state()
        return LayerResult.stop(f"I'm Seven version {state['version']}.")
    if _fullmatch_any(_MODEL, norm):
        state = self_model.get_runtime_state()
        return LayerResult.stop(f"I'm running {state['model_name']} locally through Ollama.")
    if _fullmatch_any(_HARDWARE, norm):
        return LayerResult.stop(f"You have {self_model.describe_hardware()}")

    can_you = capabilities.answer_can_you(norm)
    if can_you:
        return LayerResult.stop(can_you)
    if _fullmatch_any(_CAPABILITY, norm):
        ctx.inject_capabilities = True
    return LayerResult.pass_through()
