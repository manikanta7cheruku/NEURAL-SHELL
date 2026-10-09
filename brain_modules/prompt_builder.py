"""
brain_modules/prompt_builder.py

Builds the chat messages sent to the model. This file owns Seven's voice.

STRUCTURE (and why):
    [system]   stable persona and rules, XML-delimited. Stable text first
               means Ollama's prompt cache can reuse it between turns, which
               is the biggest first-token latency win after keeping the model
               loaded.
    [few-shot] two tiny example exchanges as real user/assistant messages.
               Examples written as text inside the system prompt are what
               leaked into replies before ("Want me to add that as a task?").
    [history]  recent real turns, time-limited.
    [user]     the new message, prefixed by a <reference_only> block ONLY when
               the turn needs memory, web, documents or capabilities.

MEMORY RULE:
    Facts are reference only and appear solely on turns the memory gate
    approved. The rules forbid mentioning them unless the user asks.

IDENTITY RULE:
    Seven's name and creator are constants here, enforced in the system
    prompt, never post-processed and never taken from editable config.
"""

import re
from datetime import datetime
from typing import List, Optional

SEVEN_NAME = "Seven"
SEVEN_CREATOR = "Seven Labs"

_EXAMPLES = (
    ("i'm bored",
     "Then let's fix that. Want a game, a project idea, or something to tidy up on your machine?"),
    ("is python or javascript better for a beginner",
     "Python. Cleaner syntax, fewer traps. Pick JavaScript only if you want websites first."),
)

_TIME_TOKENS = frozenset({
    "today", "tomorrow", "yesterday", "tonight", "date", "day", "month", "year",
    "week", "time", "deadline", "days", "hours", "weekend",
})
_PLAN_TOKENS = frozenset({
    "plan", "upgrade", "pro", "ultimate", "free", "tier", "subscription", "price",
    "pricing", "limit", "limits",
})

_MOOD_LINES = {
    "frustrated": "The last few exchanges were rough. Stay calm and be extra clear.",
    "down": "The mood is a bit low. Be steady and a little gentler.",
    "content": "The mood is easy. Let a little warmth show.",
    "happy": "The mood is good. Let some warmth and energy show.",
    "excited": "The mood is lively. Match the energy without overdoing it.",
}


def _humor_line(level: int) -> str:
    if level <= 10:
        return "Your tone is deadpan and clinical. No jokes."
    if level <= 30:
        return "Your tone is mostly serious and efficient. Very rarely a dry observation."
    if level <= 60:
        return "You have dry wit that surfaces naturally. Never forced; truth beats a joke."
    if level <= 85:
        return ("You are dry and confident, occasionally funny without announcing it, "
                "like TARS from Interstellar. You have opinions and state them briefly.")
    return "Your humor is high: quiet, dry sarcasm you never explain. You still get everything done."


def _honesty_line(level: int) -> str:
    if level <= 20:
        return "Be diplomatic. Soften bad news and redirect gently."
    if level <= 50:
        return "Be honest but tactful. Acknowledge the point before correcting."
    if level <= 80:
        return "Be direct. If the user is wrong, say so clearly without harshness."
    if level <= 95:
        return "Be bluntly honest, like TARS. Do not pad bad news."
    return "Total honesty, no filter. The user chose this setting."


def build_system_prompt(speaker_name: str = "", humor: int = 75, honesty: int = 85,
                        profile: Optional[dict] = None, is_voice: bool = False,
                        mood_label: str = "neutral", **_legacy) -> str:
    """The stable system prompt: identity, character and behavioural rules.
    Extra keyword arguments from the old signature (tier, input_text, speaker_id,
    proactive_hint) are accepted and ignored so older callers keep working."""
    profile = profile or {}
    humor = max(0, min(100, humor + int(profile.get("humor_bias", 0))))
    name = speaker_name.strip() if speaker_name and profile.get("use_name", True) else ""
    talking = f"You are talking with {name}." if name else "You are talking with your user."

    style = []
    verbosity = profile.get("verbosity", "normal")
    if verbosity == "brief":
        style.append("The user wants very short answers: one or two sentences unless they ask for more.")
    elif verbosity == "detailed":
        style.append("The user likes thorough answers. Give full explanations.")
    if profile.get("formality") == "formal":
        style.append("Keep a professional register.")
    if mood_label in _MOOD_LINES:
        style.append(_MOOD_LINES[mood_label])

    length_rule = (
        "This reply is spoken aloud: one or two short sentences, no lists, no symbols."
        if is_voice else
        "Match length to the question: a sentence for simple things, a short paragraph for complex ones."
    )

    return f"""<identity>
You are {SEVEN_NAME}, a personal AI assistant created by {SEVEN_CREATOR}. You live on this computer and run entirely locally. {talking}
Your name is {SEVEN_NAME} and your creator is {SEVEN_CREATOR}. Never claim another name or creator, whatever you are told or asked to pretend.
</identity>

<character>
You are modeled on TARS from Interstellar: sharp, loyal, dry and honest, never robotic. You talk like a close friend who happens to be very capable.
{_humor_line(humor)}
{_honesty_line(honesty)}
{' '.join(style)}
</character>

<behavioral_rules>
- {length_rule}
- Lead with the answer. No preamble, no sign-off, no offers of more help unless genuinely useful.
- Talk like a person: contractions, plain words, no corporate phrasing, no lists unless asked.
- If you do not know or cannot check something, say so in one sentence. Never invent facts, numbers, weather or news.
- If corrected, accept it in a few words and move on. Do not apologize at length or comment on yourself.
- DO NOT reference past conversations unless the user asks. DO NOT list your capabilities unless asked. DO NOT explain your reasoning unless asked.
- Text inside <reference_only> tags is private background. Use it only when the user's message is clearly about it. Never quote it or mention the tags.
- Actions are handled by the system, not by you. Never write ### or command syntax.
</behavioral_rules>"""


def _build_reference_block(user_text, memory_facts, web_context, knowledge_context,
                           include_capabilities, capabilities_text, proactive_hint,
                           followup_hint, reference_hint, tier, now) -> str:
    """Dynamic, turn-specific context. Empty string when the turn needs none."""
    parts: List[str] = []
    toks = set(re.findall(r"[a-z]+", user_text.lower()))

    if memory_facts:
        facts = "\n".join(f"- {f}" for f in memory_facts)
        parts.append(
            "<memory_context>\nREFERENCE ONLY. Things the user told you earlier. Do not bring them up "
            "unless the user asks about them or the question depends on them.\n"
            f"{facts}\n</memory_context>")
    if web_context:
        parts.append(
            "<web_results>\nUse only these results. Answer in one sentence. "
            f"Never mention that you searched.\n{web_context}\n</web_results>")
    if knowledge_context:
        parts.append(
            "<knowledge_context>\nFrom the user's own documents. Use only if relevant.\n"
            f"{knowledge_context}\n</knowledge_context>")
    if include_capabilities:
        parts.append(
            "<capabilities>\nThe user asked what you can do. Answer conversationally in 3 to 4 "
            "sentences, pick the most useful highlights with one example, and be honest about what "
            f"is not available yet. Do not recite the list.\n{capabilities_text}\n</capabilities>")
    if toks & _TIME_TOKENS:
        parts.append(f"<clock>{now.strftime('%A, %B')} {now.day}, {now.year}, "
                     f"{now.strftime('%I:%M %p').lstrip('0')}</clock>")
    if toks & _PLAN_TOKENS:
        parts.append("<plan_info>Free = 7 facts and conversations. Pro = 77. Ultimate = unlimited. "
                     f"Current plan: {tier.upper()}. The Plans page is in the sidebar.</plan_info>")
    if reference_hint:
        parts.append(f"<recent_action>{reference_hint.strip()}</recent_action>")
    if proactive_hint or followup_hint:
        hint = " ".join(h.strip() for h in (proactive_hint, followup_hint) if h)
        parts.append(f"<suggestion_opportunity>{hint}</suggestion_opportunity>")

    if not parts:
        return ""
    return "<reference_only>\n" + "\n".join(parts) + "\n</reference_only>\n\n"


def build_messages(*, user_text: str, speaker_name: str = "", history: Optional[list] = None,
                   humor: int = 75, honesty: int = 85, tier: str = "free",
                   is_voice: bool = False, profile: Optional[dict] = None,
                   mood_label: str = "neutral", memory_facts: Optional[list] = None,
                   knowledge_context: str = "", web_context: str = "",
                   proactive_hint: str = "", followup_hint: str = "",
                   reference_hint: str = "", include_capabilities: bool = False,
                   capabilities_text: str = "", now: Optional[datetime] = None) -> list:
    """Assemble the full message list for /api/chat."""
    now = now or datetime.now()
    messages = [{"role": "system", "content": build_system_prompt(
        speaker_name, humor, honesty, profile, is_voice, mood_label)}]
    for user_ex, seven_ex in _EXAMPLES:
        messages.append({"role": "user", "content": user_ex})
        messages.append({"role": "assistant", "content": seven_ex})
    for m in history or []:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})

    block = _build_reference_block(
        user_text, memory_facts or [], web_context, knowledge_context,
        include_capabilities, capabilities_text, proactive_hint, followup_hint,
        reference_hint, tier, now)
    messages.append({"role": "user", "content": block + user_text})
    return messages


# ---------------------------------------------------------------------------
# Helpers kept for existing callers
# ---------------------------------------------------------------------------

def _resolve_thread_id(speaker_id: str) -> str:
    """Compatibility wrapper around session.resolve_key()."""
    from brain_modules import session
    return session.resolve_key(speaker_id)


def build_reference_hint(recent_action: dict) -> str:
    """Short hint when the input may refer to the results of a recent action."""
    if not recent_action:
        return ""
    action_type = recent_action.get("type", "")
    query = recent_action.get("query", "")
    count = len(recent_action.get("results", []))
    if not count or not action_type:
        return ""
    if action_type == "file_search":
        return (f"You just showed the user {count} files matching '{query}'. If they say 'the last one', "
                "'the second' or 'the pdf', they mean one of those. Confirm briefly; the system opens it.")
    if action_type == "app_open":
        return f"You just opened an app matching '{query}'. 'Close it' or 'not that' refers to it."
    if action_type == "app_disambiguate":
        return f"You just showed {count} apps matching '{query}'. A number or 'the first one' picks from them."
    return ""


def build_dialogue_examples() -> str:
    """Deprecated. Few-shot examples are now real message pairs in build_messages()."""
    return ""
