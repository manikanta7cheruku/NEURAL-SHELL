"""
brain_modules/capabilities.py

The ONE registry of what Seven can do, with live health.

WHY A REGISTRY WITH HEALTH:
    Seven used to describe itself from prompts and a static list, so it could
    run "open camera" and then claim it was a text-only assistant. Now every
    ability is a registered entry that declares what it needs (a module, a
    setting, a plan feature, the internet). Answers about abilities are built
    from the entry PLUS its current status, so Seven says "yes", "yes but you
    are offline", "it is switched off in Settings" or "it failed the last 3
    times" truthfully.

SELF-REGISTRATION:
    A module (a layer, a hands/* tool) can declare
        CAPABILITY = {"id": ..., "title": ..., "summary": ..., "examples": [...], "section": ...}
    at top level. discover() reads those literals with ast (no imports, no side
    effects) and registers them, so new tools appear without editing this file.
"""

import ast
import importlib.util
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_log = logging.getLogger("seven.capabilities")


@dataclass
class Capability:
    id: str
    title: str
    summary: str
    examples: Tuple[str, ...] = ()
    section: str = ""                 # where the user sees or controls it in the app
    keywords: Tuple[str, ...] = ()
    risk: str = "low"                 # low | medium | high (drives confirmation)
    requires: Tuple[Tuple[str, str], ...] = ()   # (type, name): module | config | tier | network


_REGISTRY: Dict[str, Capability] = {}
_overrides: Dict[str, Tuple[str, str]] = {}
_discovered = False

NOT_YET = (
    ("seeing or reading your screen", ("screen", "see", "look", "watch", "display"),
     "Not yet. Screen vision is on my roadmap, but right now I can't see what's on your display."),
    ("clicking or typing in other apps for you", ("click", "type", "mouse", "cursor", "keyboard"),
     "Not yet. I can open, close and arrange apps, but clicking and typing inside them is still to come."),
    ("sending messages or making calls", ("message", "messages", "text", "whatsapp", "call", "calls", "phone"),
     "Not yet. Messaging and calls are planned, but I can't send or place them today."),
    ("sending or reading email", ("email", "emails", "gmail", "inbox"),
     "Not yet. Email is planned, but I can't read or send it today."),
    ("buying things or handling payments", ("buy", "order", "pay", "purchase", "payment", "payments"),
     "No. I don't handle purchases or payments."),
)

_STOP = {"can", "could", "do", "does", "you", "your", "are", "able", "to", "i", "my", "me", "the", "a", "an",
         "it", "is", "possible", "seven", "for", "on", "in", "of", "and", "or", "please", "also", "yes", "what",
         "how", "apps", "app", "support", "help", "with", "this", "that"}


def register(cap: Capability) -> None:
    _REGISTRY[cap.id] = cap


def _builtin() -> None:
    reg = [
        Capability("apps", "Open and close apps", "launch or close installed apps and common websites",
                   ("open chrome", "close spotify", "open camera"), "Console",
                   ("open", "close", "launch", "start", "app", "program", "camera", "browser", "notepad"),
                   "medium", (("module", "hands.core"),)),
        Capability("windows", "Window control", "snap, minimize, maximize, pin, fade and arrange windows",
                   ("snap code to the left", "put chrome and notepad side by side"), "Console",
                   ("window", "windows", "snap", "minimize", "maximize", "layout", "arrange", "monitor"),
                   "low", (("module", "hands.windows"),)),
        Capability("system", "System controls",
                   "volume, brightness, Wi-Fi, Bluetooth, dark mode, night light, do not disturb, airplane mode, media keys, battery",
                   ("set volume to 40", "turn on dark mode"), "Console",
                   ("volume", "brightness", "wifi", "bluetooth", "dark", "mute", "battery", "media", "music"),
                   "medium", (("module", "hands.system"),)),
        Capability("reminders", "Reminders, alarms and timers", "one-off or recurring",
                   ("remind me to stretch in 20 minutes", "set a timer for 10 minutes"), "Schedules",
                   ("remind", "reminder", "reminders", "alarm", "alarms", "timer", "timers", "schedule"),
                   "low", (("module", "hands.scheduler"),)),
        Capability("tasks", "Tasks", "a to-do list you can add to, list and complete",
                   ("add a task to finish the report", "what are my tasks"), "Tasks",
                   ("task", "tasks", "todo", "to-do", "list"), "low", (("module", "backend.routes.tasks"),)),
        Capability("files", "Find and open files", "search your folders by name or by what is inside documents",
                   ("open my resume", "find the invoice pdf"), "Console",
                   ("file", "files", "folder", "document", "documents", "pdf", "resume", "find"),
                   "low", (("module", "hands.files"),)),
        Capability("knowledge", "Your documents", "answer questions from files you add to the knowledge base",
                   ("summarize the report I uploaded",), "Knowledge",
                   ("knowledge", "document", "documents", "upload", "pdf", "notes"),
                   "low", (("module", "knowledge.core"), ("config", "knowledge.enabled"))),
        Capability("web", "Live lookups", "weather, news and prices when you are online",
                   ("what's the weather in Rio",), "Console",
                   ("web", "internet", "online", "weather", "news", "search", "price", "prices", "lookup"),
                   "low", (("network", ""), ("config", "web.enabled"))),
        Capability("workspaces", "Workspaces and triggers", "save and restore sets of apps and run your own voice triggers",
                   ("save this workspace as study",), "Triggers",
                   ("workspace", "workspaces", "trigger", "triggers", "hotkey", "hotkeys", "shortcut"),
                   "low", (("module", "hands.workspace"),)),
        Capability("memory", "Memory", "remember what you tell me, update it when you correct me, and adapt to how you like me to talk",
                   ("remember that my favorite framework is React",), "Memory",
                   ("remember", "memory", "memories", "learn", "forget", "facts"),
                   "low", (("module", "memory.fact_service"),)),
        Capability("voice", "Hands-free voice", "wake word and push to talk", (), "Settings",
                   ("voice", "speak", "microphone", "wake", "talk"), "low", ()),
        Capability("speaker_id", "Speaker recognition", "tell household members apart by voice", (), "Settings",
                   ("speaker", "recognition", "voiceprint", "enroll"), "low", (("tier", "voice_recognition"),)),
    ]
    for cap in reg:
        _REGISTRY.setdefault(cap.id, cap)


def discover(roots: Optional[List[str]] = None) -> int:
    """Register CAPABILITY literals found in module source (no imports executed)."""
    global _discovered
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roots = roots or [os.path.join(base, d) for d in ("hands", "brain_modules/layers", "main_modules")]
    found = 0
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(".py"):
                    continue
                try:
                    tree = ast.parse(open(os.path.join(dirpath, name), encoding="utf-8").read())
                except Exception:
                    continue
                for node in tree.body:
                    if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "CAPABILITY" for t in node.targets):
                        try:
                            d = ast.literal_eval(node.value)
                            register(Capability(
                                d["id"], d["title"], d["summary"], tuple(d.get("examples", ())), d.get("section", ""),
                                tuple(d.get("keywords", ())), d.get("risk", "low"),
                                tuple(tuple(r) for r in d.get("requires", ()))))
                            found += 1
                        except Exception as exc:
                            _log.debug("bad CAPABILITY in %s: %s", name, exc)
    _discovered = True
    return found


def all_capabilities() -> List[Capability]:
    if not _REGISTRY:
        _builtin()
    if not _discovered:
        discover()
    return list(_REGISTRY.values())


def get(cap_id: str) -> Optional[Capability]:
    all_capabilities()
    return _REGISTRY.get(cap_id)


def set_status_override(cap_id: str, state: Optional[str], reason: str = "") -> None:
    """Force a status (tests, diagnostics). state=None removes the override."""
    if state is None:
        _overrides.pop(cap_id, None)
    else:
        _overrides[cap_id] = (state, reason)


def _config_value(path: str):
    try:
        import config
        cur = config.KEY
        for part in path.split("."):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        return cur
    except Exception:
        return True


def status(cap_id: str) -> Tuple[str, str]:
    """(state, reason). state: available | degraded | disabled | unavailable | needs_internet | plan."""
    if cap_id in _overrides:
        return _overrides[cap_id]
    cap = get(cap_id)
    if cap is None:
        return "unavailable", "not registered"
    for kind, name in cap.requires:
        if kind == "module":
            try:
                if importlib.util.find_spec(name) is None:
                    return "unavailable", f"module {name} is not installed"
            except (ImportError, ValueError):
                return "unavailable", f"module {name} is not installed"
        elif kind == "config":
            val = _config_value(name)
            if val is False:
                return "disabled", f"switched off in Settings ({name})"
        elif kind == "tier":
            try:
                from memory import limits
                if not limits.limit(name, 0):
                    return "plan", f"not included in your {limits.tier()} plan"
            except Exception:
                pass
        elif kind == "network":
            try:
                from brain_modules import web_provider
                if not web_provider.is_online():
                    return "needs_internet", "you are offline right now"
            except Exception:
                pass
    try:
        from memory import learning_store
        rel = learning_store.reliability("action", cap_id, window=6)
        if rel["total"] >= 3 and rel["failure_rate"] >= 0.6:
            return "degraded", f"it failed {rel['failed']} of the last {rel['total']} times"
    except Exception:
        pass
    return "available", ""


def _first_example(cap: Capability) -> str:
    return f' Try "{cap.examples[0]}".' if cap.examples else ""


def describe(cap: Capability) -> str:
    """One truthful sentence about a capability including its current state."""
    state, reason = status(cap.id)
    if state == "available":
        return f"Yes. I can {cap.summary}.{_first_example(cap)}"
    if state == "needs_internet":
        return f"Yes, but it needs the internet and {reason}. It covers {cap.summary}."
    if state == "disabled":
        where = f" in {cap.section}" if cap.section else ""
        return f"It's {reason}{where}. Turn it on and I can {cap.summary}."
    if state == "plan":
        return f"That's {reason}. It would let me {cap.summary}."
    if state == "degraded":
        return f"I can normally {cap.summary}, but right now {reason}, so something is wrong with it."
    return f"Not on this install: {reason}."


def find(norm: str, limit: int = 2) -> List[Capability]:
    """Capabilities a question is about, matched on declared keywords and titles."""
    toks = {t for t in norm.split() if t not in _STOP}
    scored = []
    for cap in all_capabilities():
        words = set(cap.keywords) | {w for w in cap.title.lower().split() if w not in _STOP}
        hits = len(toks & words)
        if hits:
            scored.append((hits, cap))
    scored.sort(key=lambda x: -x[0])
    return [c for _h, c in scored[:limit]]


def answer_can_you(norm: str) -> Optional[str]:
    """Answer 'can you ...?' from the registry and current status. None if not a capability question."""
    if not norm.startswith(("can you ", "could you ", "are you able to ", "does seven ", "is it possible", "do you ")):
        return None
    if norm.startswith("do you ") and norm.split()[2:3] and norm.split()[2] not in (
            "support", "work", "handle", "remember", "learn", "know", "understand"):
        return None
    toks = set(norm.split())
    for _label, words, answer in NOT_YET:
        if toks & set(words) and ("screen" in words or toks & {"see", "read", "send", "make", "place", "buy",
                                                                   "click", "type", "control", "order", "pay", "take"}):
            return answer
    hits = find(norm, 1)
    if not hits:
        return None
    # An object-specific request ("can you open chrome") is a command, not a capability question.
    cap = hits[0]
    generic = toks & {"apps", "app", "programs", "applications", "reminders", "alarms", "timers", "files",
                      "windows", "volume", "brightness", "wifi", "bluetooth", "internet", "web", "weather",
                      "things", "stuff", "tasks", "workspaces", "triggers", "documents", "memory"}
    if not generic and not toks & {"remember", "learn"}:
        return None
    return describe(cap)


def describe_for_prompt() -> str:
    """Capability list with live status, given to the model ONLY on capability questions."""
    lines = []
    for cap in all_capabilities():
        state, reason = status(cap.id)
        mark = "available" if state == "available" else f"{state}: {reason}"
        ex = f' (e.g. "{cap.examples[0]}")' if cap.examples else ""
        lines.append(f"- {cap.title} [{mark}]: {cap.summary}{ex}")
    lines.append("Not available yet: " + "; ".join(n[0] for n in NOT_YET) + ".")
    return "\n".join(lines)


def overview() -> str:
    """Deterministic natural-language summary built from the registry and current status."""
    ok, later, off = [], [], []
    for cap in all_capabilities():
        state, reason = status(cap.id)
        (ok if state == "available" else later if state == "needs_internet" else off).append((cap, reason))
    parts = ["Right now these work: " + ", ".join(c.title.lower() for c, _ in ok[:9]) + "."]
    if later:
        parts.append("These need the internet, which you don't have at the moment: "
                     + ", ".join(c.title.lower() for c, _ in later) + ".")
    if off:
        parts.append("Not working right now: " + "; ".join(f"{c.title.lower()} ({r})" for c, r in off[:4]) + ".")
    parts.append("Not available yet: " + ", ".join(n[0] for n in NOT_YET[:3]) + ".")
    return " ".join(parts)


def fallback_summary() -> str:
    """Used when the language model is unreachable."""
    return overview()


# Backward compatible name used by older callers and tests.
CAPABILITIES = tuple({"id": c.id, "title": c.title, "summary": c.summary, "examples": c.examples}
                     for c in (_builtin() or _REGISTRY.values()))
