"""
brain_modules/capabilities.py

The registry of what Seven can really do today, and what it cannot do yet.

WHY A REGISTRY:
    "What can you do?" used to be answered from a hardcoded string that
    drifted from reality, or by the model improvising (and over-promising).
    Now there is one honest list. The LLM receives it ONLY when the user asks
    about capabilities, and direct "can you ...?" questions are answered from
    it deterministically, including a plain "not yet" for things that are
    still on the roadmap (screen vision, messaging, and so on).

Add a capability here when it ships; nothing else needs to change.
"""

import re
from typing import Optional

CAPABILITIES = (
    {"id": "apps", "title": "Open and close apps",
     "summary": "launch or close installed apps and common websites",
     "examples": ("open chrome", "close spotify")},
    {"id": "windows", "title": "Window control",
     "summary": "snap, minimize, maximize, pin, fade and arrange windows side by side",
     "examples": ("snap code to the left", "put chrome and notepad side by side")},
    {"id": "system", "title": "System controls",
     "summary": "volume, brightness, Wi-Fi, Bluetooth, dark mode, night light, do not disturb, airplane mode, media keys, battery",
     "examples": ("set volume to 40", "turn on dark mode")},
    {"id": "reminders", "title": "Reminders, alarms and timers",
     "summary": "one-off or recurring",
     "examples": ("remind me to stretch in 20 minutes", "set a timer for 10 minutes")},
    {"id": "tasks", "title": "Tasks",
     "summary": "keep a to-do list you can add to, list and complete",
     "examples": ("add a task to finish the report", "what are my tasks")},
    {"id": "files", "title": "Find and open files",
     "summary": "search your folders by name or by what is inside documents",
     "examples": ("open my resume", "find the invoice pdf")},
    {"id": "knowledge", "title": "Your documents",
     "summary": "answer questions from files you add to the knowledge base",
     "examples": ("summarize the report I uploaded",)},
    {"id": "web", "title": "Live lookups",
     "summary": "weather, news and prices when you are online",
     "examples": ("what's the weather in Rio",)},
    {"id": "workspaces", "title": "Workspaces and triggers",
     "summary": "save and restore sets of apps and run your own voice triggers",
     "examples": ("save this workspace as study",)},
    {"id": "memory", "title": "Memory",
     "summary": "remember what you tell me, update it when you correct me, and adapt to how you like me to talk",
     "examples": ("remember that my favorite framework is React",)},
    {"id": "voice", "title": "Hands-free voice",
     "summary": "wake word, push to talk and speaker recognition",
     "examples": ()},
)

NOT_YET = (
    "seeing or reading your screen",
    "clicking or typing in other apps for you",
    "sending messages or making calls",
    "sending email",
    "buying things or handling payments",
)

# (regex on normalised text, supported, answer)
_CAN_YOU = (
    (r"(?:see|look at|watch|read) (?:my|the) screen",
     False, "Not yet. Screen vision is on my roadmap, but right now I can't see what's on your display."),
    (r"(?:click|type|control) (?:things )?(?:in|on) (?:my|other) (?:apps?|screen|computer|pc)",
     False, "Not yet. I can open, close and arrange apps, but clicking and typing inside them is still to come."),
    (r"(?:send|write|read) (?:my )?(?:messages?|texts?|whatsapp|emails?)",
     False, "Not yet. Messaging and email are planned, but I can't send or read them today."),
    (r"(?:make|take|place) (?:phone )?calls?",
     False, "No, not yet. Calls are on the roadmap."),
    (r"(?:buy|order|pay for|purchase)",
     False, "No. I don't handle purchases or payments."),
    (r"(?:open|close|launch|start) (?:apps?|programs?|applications?)",
     True, "Yes. Say 'open chrome' or 'close spotify' and it's done."),
    (r"(?:set|make|create) (?:reminders?|alarms?|timers?)",
     True, "Yes. Try 'remind me to stretch in 20 minutes' or 'set a timer for 10 minutes'."),
    (r"(?:search|find|open) (?:my )?files?",
     True, "Yes. Tell me what you're looking for, like 'open my resume'."),
    (r"(?:search|look up|check) (?:the )?(?:web|internet|online)",
     True, "Yes, for live things like weather and news, when you're online."),
    (r"(?:remember|learn)(?: things| stuff| about me)?",
     True, "Yes. Tell me something and I'll keep it. Correct me and I'll update it."),
    (r"(?:control|change|adjust) (?:the )?(?:volume|brightness|wi ?fi|bluetooth)",
     True, "Yes. Volume, brightness, Wi-Fi and Bluetooth are all covered."),
    (r"(?:manage|arrange|snap|move) (?:my )?windows?",
     True, "Yes. I can snap, minimize, maximize and arrange windows."),
)


def describe_for_prompt() -> str:
    """Compact capability list injected into the prompt ONLY on capability questions."""
    lines = []
    for cap in CAPABILITIES:
        ex = f' (e.g. "{cap["examples"][0]}")' if cap["examples"] else ""
        lines.append(f"- {cap['title']}: {cap['summary']}{ex}")
    lines.append("Not available yet: " + "; ".join(NOT_YET) + ".")
    return "\n".join(lines)


def fallback_summary() -> str:
    """Deterministic capability summary for when the language model is unreachable."""
    return ("I can open and close apps, arrange your windows, control volume and brightness, "
            "set reminders and timers, keep your tasks, find files, answer from your documents, "
            "look up live weather and news, and remember what you tell me. "
            "I can't see your screen or send messages yet.")


def answer_can_you(norm: str) -> Optional[str]:
    """
    Answer a generic "can you ...?" question straight from the registry.
    Only fires on object-free questions, so "can you open chrome" still runs
    as the command it is.
    """
    if not norm.startswith(("can you ", "could you ", "are you able to ", "do you ")):
        return None
    for pattern, _supported, answer in _CAN_YOU:
        if re.search(pattern, norm):
            return answer
    return None
