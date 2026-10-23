"""
brain_modules/settings_control.py

Lets the user read and change Seven's own settings by chat or voice:

    "set honesty to 75%"            absolute
    "turn off streaming"            on / off
    "increase humor by 10"          relative ("a bit" = one step)
    "be a little more honest"       relative, by adjective
    "set your temperature to 0.5"   floats, and 50% / 5 on a 1-10 scale
    "switch your model to llama3.2" checked against installed Ollama models
    "what is your honesty level"    read one setting
    "what are your settings"        read all of them

Every change goes through brain_settings (types, bounds, clamping), is saved
with config.update_config, and is read back before Seven claims it worked.
The brain reads settings on every message, so a change applies to the next
reply. Questions about HOW to change a setting ("how do I change your humor")
are left to the app-help router.
"""

import re
import time
from typing import Callable, Dict, List, Optional, Tuple

from brain_modules import brain_settings

# path -> label, aliases (longest match wins), kind, step for relative changes
SPECS: Dict[str, Dict] = {
    "brain.tars_honesty": {"label": "Honesty", "kind": "percent", "step": 10,
                           "aliases": ["honesty level", "honesty", "bluntness", "directness"],
                           "adjectives": {"honest", "blunt", "direct", "brutal"}},
    "brain.tars_humor": {"label": "Humor", "kind": "percent", "step": 10,
                         "aliases": ["humor level", "humour level", "humor", "humour", "sarcasm", "wit"],
                         "adjectives": {"funny", "funnier", "sarcastic", "witty", "playful"}},
    "brain.temperature": {"label": "Temperature", "kind": "float", "step": 0.1,
                          "aliases": ["temperature", "creativity"]},
    "brain.streaming": {"label": "Streaming", "kind": "bool",
                        "aliases": ["streaming mode", "streaming", "stream replies"]},
    "brain.model_name": {"label": "Model", "kind": "model",
                         "aliases": ["language model", "ai model", "llm", "model"]},
    "brain.follow_up_timeout": {"label": "Reference memory", "kind": "seconds", "step": 15,
                                "aliases": ["reference memory", "follow up timeout", "followup timeout"]},
    "brain.search_max_results": {"label": "File search results", "kind": "int", "step": 2,
                                 "aliases": ["file search results", "search results", "max results"]},
    "brain.auto_open_best_match": {"label": "Auto-open best match", "kind": "bool",
                                   "aliases": ["auto open best match", "auto open", "open best match"]},
    "brain.content_search_enabled": {"label": "Search inside documents", "kind": "bool",
                                     "aliases": ["search inside documents", "document search", "content search"]},
    "brain.prefer_browser_for_unknown": {"label": "Browser fallback for unknown apps", "kind": "bool",
                                         "aliases": ["browser fallback"]},
    "brain.curiosity_level": {"label": "Curiosity", "kind": "choice",
                              "aliases": ["curiosity level", "curiosity", "follow up questions"]},
    "web.enabled": {"label": "Web search", "kind": "bool",
                    "aliases": ["web search", "internet search", "online search", "web lookups"]},
    "privacy.telemetry_enabled": {"label": "Usage statistics", "kind": "bool",
                                  "aliases": ["usage statistics", "usage stats", "telemetry", "analytics"]},
}

_SET_VERBS = {"set", "change", "make", "put", "adjust", "turn", "switch", "bring", "use", "update"}
_UP = {"increase", "raise", "bump", "boost", "up", "higher", "more"}
_DOWN = {"decrease", "lower", "reduce", "drop", "down", "less", "tone"}
_ON = {"on", "enable", "enabled", "activate", "start", "resume"}
_OFF = {"off", "disable", "disabled", "deactivate", "stop", "pause"}
_QUESTION_STARTS = ("what", "whats", "how much", "how high", "how low", "is ", "are ", "show", "tell me",
                    "which", "current")
# "what is your model good at" asks about the model itself, not the model setting.
_ABOUT_MODEL = re.compile(r"\bmodel\b.*\b(?:good at|capable|smart|limits?|parameters|strengths?|weak|better|best at|"
                          r"can (?:it|you) do)\b|\b(?:capable|smart|good) is (?:your|the) model\b")
_HOW_TO = re.compile(r"^(?:how (?:do|can|would|should) i|where (?:do|can|is|are)|how to)\b")
_NEGATION = re.compile(r"\b(?:dont|do not|don't|never|not now)\b")
_WEATHER = re.compile(r"\b(?:outside|weather|degrees?|celsius|fahrenheit|forecast|today|tomorrow|tonight|hot|cold|"
                      r"room|body|fever|cpu|gpu|in [a-z]+$)\b")
_ALL_SETTINGS = re.compile(r"\b(?:your|my|brain|all(?: of)?(?: your)?|current) settings\b|\bsettings (?:are|you have)\b")
_STRIP = re.compile(r"^(?:hey seven|seven|please|can you|could you|would you|will you|i want you to|i'd like you to)\s+")

_SETTING_NOUN = re.compile(r"\b(?:percentage|percent|level|setting|value|score|number|%)")
_HOW_ADJ = re.compile(r"^how (\w+) are you\b")
_FOLLOW_UP = re.compile(r"^(?:just |so )?(?:tell|give|show) me (?:the |that )?(?:number|percentage|value|level)\b|"
                        r"^(?:what(?:s| is) )?the (?:number|percentage|value)$|^(?:the )?number$")
_last = {"path": None, "t": 0.0}                  # setting talked about last, for "just tell me the number"

InstalledModels = Callable[[], Optional[List[str]]]


def _ollama_models() -> Optional[List[str]]:
    """Installed Ollama model names, or None when Ollama can't be reached."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        pass
    return None


_installed_models: InstalledModels = _ollama_models


def set_model_lister(fn: Optional[InstalledModels]) -> None:
    """Tests replace the Ollama lookup."""
    global _installed_models
    _installed_models = fn or _ollama_models


# --------------------------------------------------------------------------
# Reading values
# --------------------------------------------------------------------------

def _cfg(config) -> dict:
    return getattr(config, "KEY", config) or {}


def current(config, path: str):
    return brain_settings.get_effective(config, path)


def _tone_label(path: str, v: int) -> str:
    from brain_modules.identity_layer import _honesty_label, _humor_label
    return (_honesty_label if path == "brain.tars_honesty" else _humor_label)(int(v))


def describe(path: str, value) -> str:
    """'75% (direct)', 'on', '0.5', '90 seconds'."""
    kind = SPECS[path]["kind"]
    if kind == "percent":
        return f"{int(value)}% ({_tone_label(path, value)})"
    if kind == "bool":
        return "on" if value else "off"
    if kind == "float":
        return f"{float(value):g}"
    if kind == "seconds":
        return f"{int(value)} seconds"
    if kind == "model":
        return value or "auto"
    return str(value)


def summary(config) -> str:
    rows = [f"{SPECS[p]['label']} {describe(p, current(config, p))}" for p in (
        "brain.model_name", "brain.tars_honesty", "brain.tars_humor", "brain.temperature", "brain.streaming",
        "brain.curiosity_level", "web.enabled")]
    return "Here's how I'm set up: " + "; ".join(rows) + ". You can change any of these by asking, or in Settings."


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def _clean(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[?!,]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)          # keep decimal points, drop sentence dots
    t = t.replace("’", "'").replace("what's", "whats").replace("it's", "its")
    t = re.sub(r"\s+", " ", t).strip()
    prev = None
    while prev != t:
        prev, t = t, _STRIP.sub("", t)
    return t


def _find_setting(t: str) -> Optional[Tuple[str, str]]:
    best = None
    for path, spec in SPECS.items():
        for alias in spec["aliases"]:
            if re.search(rf"\b{re.escape(alias)}\b", t) and (best is None or len(alias) > len(best[1])):
                best = (path, alias)
    return best


def _number(t: str) -> Optional[Tuple[float, bool]]:
    """(value, had_percent_sign)."""
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(%|percent)?", t)
    if not m:
        return None
    return float(m.group(1)), bool(m.group(2))


def _seconds(t: str) -> Optional[int]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m)\b", t)
    if m:
        n = float(m.group(1))
        return int(round(n * 60 if m.group(2).startswith("m") else n))
    n = _number(t)
    return int(n[0]) if n else None


def _to_value(path: str, raw: float, pct: bool):
    kind = SPECS[path]["kind"]
    if kind == "percent":
        return int(round(raw * 100)) if (0 < raw <= 1 and not pct and raw != int(raw)) else int(round(raw))
    if kind == "float":
        if pct or raw > 10:
            return round(raw / 100.0, 2)
        return round(raw / 10.0, 2) if raw > 1 else round(raw, 2)
    return int(round(raw))


def _model_target(t: str, alias: str) -> Optional[str]:
    m = (re.search(rf"\b{re.escape(alias)}\b\s+(?:to|as)\s+([a-z0-9][a-z0-9._:\-/]*)", t)
         or re.search(rf"\b(?:to|use)\s+([a-z0-9][a-z0-9._:\-/]*)\s+(?:as (?:your |the )?)?{re.escape(alias)}\b", t))
    return m.group(1) if m else None


def parse(text: str) -> Optional[Dict]:
    """
    Returns {"op": "set"|"delta"|"query"|"summary", "path", "value"} or None.
    None means "not a settings request": the pipeline continues untouched.
    """
    t = _clean(text)
    if not t or _HOW_TO.search(t) or _NEGATION.search(t) or _ABOUT_MODEL.search(t):
        return None
    words = set(t.split())
    if _ALL_SETTINGS.search(t) and (t.startswith(_QUESTION_STARTS) or words & {"list", "show"}):
        return {"op": "summary"}

    found = _find_setting(t) or _adjective_name(t)
    if found is None:
        if _FOLLOW_UP.search(t) and _last["path"] and time.time() - _last["t"] < 120:
            return {"op": "query", "path": _last["path"]}
        how = _HOW_ADJ.search(t)
        for path in ("brain.tars_honesty", "brain.tars_humor"):
            if how and how.group(1) in SPECS[path]["adjectives"] | {"humorous", "sarcastic"}:
                return {"op": "query", "path": path}
        return _adjective_request(t)
    path, alias = found
    spec = SPECS[path]
    kind = spec["kind"]

    if path == "brain.temperature" and (_WEATHER.search(t) or not (words & {"your", "model", "setting", "llm"}
                                                                     or words & _SET_VERBS)):
        return None                                   # "what's the temperature outside" is a weather question
    if kind == "model" and not (words & {"your", "the", "language", "ai", "llm", "switch", "use", "change", "set"}):
        return None

    is_question = t.startswith(_QUESTION_STARTS) and not (words & (_SET_VERBS - {"use"}))
    if (len(words) <= 3 and not words & (_SET_VERBS | _ON | _OFF | _UP | _DOWN) and not re.search(r"\d", t)
            and kind != "model"):
        is_question = True                            # "honesty level?", "streaming?"
    if is_question:
        return {"op": "query", "path": path}

    if kind == "bool":
        on, off = bool(words & _ON), bool(words & _OFF)
        if on == off:
            return None
        if not (words & (_SET_VERBS | _ON | _OFF)):
            return None
        return {"op": "set", "path": path, "value": on}

    if kind == "choice":
        allowed = brain_settings.SETTINGS[path][2]
        if words & _OFF and "off" in allowed:
            return {"op": "set", "path": path, "value": "off"}
        for choice in allowed:
            if re.search(rf"\b(?:to|at)\s+{choice}\b", t):
                return {"op": "set", "path": path, "value": choice}
        return None

    if kind == "model":
        target = _model_target(t, alias)
        return {"op": "set", "path": path, "value": target} if target and words & _SET_VERBS else None

    # numeric kinds
    up, down = bool(words & _UP), bool(words & _DOWN)
    if kind == "seconds":
        n = _seconds(t)
    else:
        num = _number(t)
        n = _to_value(path, *num) if num else None
    if up != down and not (n is not None and re.search(r"\b(?:to|at)\s+-?\d", t)):
        step = spec["step"]
        if n is not None and re.search(r"\bby\s+\d", t):
            step = n
        return {"op": "delta", "path": path, "value": step if up else -step}
    if n is None:
        return None
    if not (words & _SET_VERBS or re.search(rf"\b{re.escape(alias)}\s+(?:to|at|of)?\s*-?\d", t)):
        return None
    return {"op": "set", "path": path, "value": n}


def _adjective_name(t: str) -> Optional[Tuple[str, str]]:
    """'your honest percentage', 'funny level': an adjective used as the setting's name."""
    if not _SETTING_NOUN.search(t):
        return None
    for path in ("brain.tars_honesty", "brain.tars_humor"):
        for adj in SPECS[path]["adjectives"] | ({"humorous"} if path == "brain.tars_humor" else set()):
            if re.search(rf"\b{adj}\b", t):
                return path, adj
    return None


def _adjective_request(t: str) -> Optional[Dict]:
    """'be more honest', 'be a bit funnier', 'tone down the sarcasm'."""
    if re.search(r"\btone down (?:the |your )?(?:jokes|sarcasm|humou?r)\b", t):
        return {"op": "delta", "path": "brain.tars_humor", "value": -20}
    m = re.search(r"\b(?:be|sound|get)\s+(?:a (?:bit|little|lot) |slightly |much )?(more|less)?\s*(\w+)\b", t)
    if not m:
        return None
    word = m.group(2)
    if word == "funnier":
        direction = 1
    elif m.group(1):
        direction = 1 if m.group(1) == "more" else -1
    else:
        return None
    for path in ("brain.tars_honesty", "brain.tars_humor"):
        if word in SPECS[path]["adjectives"]:
            return {"op": "delta", "path": path, "value": direction * SPECS[path]["step"]}
    return None


# --------------------------------------------------------------------------
# Applying
# --------------------------------------------------------------------------

def _save(config, path: str, value) -> bool:
    section, key = path.split(".", 1)
    ok = config.update_config({section: {key: value}})
    return bool(ok) and _cfg(config).get(section, {}).get(key) == value


def _apply_model(config, target: str) -> str:
    installed = _installed_models()
    if installed is not None:
        exact = next((m for m in installed if m == target), None)
        base = next((m for m in installed if m.split(":")[0] == target.split(":")[0]), None)
        chosen = exact or base
        if not chosen:
            names = ", ".join(sorted(installed)[:8]) or "none"
            return f"I can't find {target} in your installed models. Installed: {names}."
        target = chosen
    before = current(config, "brain.model_name")
    if before == target:
        return f"I'm already set to {target}."
    if not _save(config, "brain.model_name", target):
        return "I couldn't save that setting, so nothing changed."
    note = "" if installed is not None else " I couldn't reach Ollama to check it's installed."
    return f"Done. I'll use {target} from your next message.{note}"


def apply(request: Dict, config) -> str:
    op = request["op"]
    if op == "summary":
        return summary(config)
    path = request["path"]
    _last.update(path=path, t=time.time())
    label = SPECS[path]["label"]
    before = current(config, path)
    if op == "query":
        return f"{label} is {describe(path, before)}."
    if SPECS[path]["kind"] == "model":
        return _apply_model(config, request["value"])

    wanted = request["value"]
    if op == "delta":
        wanted = round(float(before) + float(wanted), 2)
        if SPECS[path]["kind"] != "float":
            wanted = int(round(wanted))
    accepted, value, note = brain_settings.validate_update(path, wanted)
    if value == before:
        edge = f" That's the {'maximum' if op == 'delta' and request['value'] > 0 else 'minimum'}." \
            if op == "delta" and not accepted else ""
        return f"{label} is already {describe(path, before)}.{edge}"
    if not _save(config, path, value):
        return "I couldn't save that setting, so nothing changed."
    clamp = f" The {note}, so I used that." if not accepted and note else ""
    if SPECS[path]["kind"] in ("bool", "choice"):
        return f"Done. {label} is now {describe(path, value)}.{clamp}"
    return f"Done. {label} is now {describe(path, value)}, was {describe(path, before)}.{clamp}"


def handle(text: str, config) -> Optional[str]:
    """Reply for a settings request, or None when the text isn't one."""
    request = parse(text)
    if request is None:
        return None
    return apply(request, config)
