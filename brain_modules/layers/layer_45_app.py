"""
=============================================================================
LAYER 4.5g: APP OPEN/CLOSE/SEARCH

Catches "open X", "close X", "start X", "kill X", "launch X".
Validates app name (rejects pronouns, gibberish, unknown short words).
Emits ###OPEN: / ###CLOSE: / ###SEARCH: tags with TARS-style speech.

Note: "open my resume" etc are caught by layer_43_file_search first.
=============================================================================
"""

import random
from brain_modules.layer_result import LayerResult


_ALWAYS_CLOSEABLE = {
    "chrome", "firefox", "edge", "notepad", "explorer", "calculator",
    "camera", "photos", "settings", "paint", "word", "excel",
    "powerpoint", "outlook", "teams", "discord", "spotify",
    "whatsapp", "telegram", "zoom", "obs", "vlc", "code",
    "vscode", "terminal", "cmd", "powershell", "task manager",
    "snipping tool", "copilot", "clock", "calendar", "mail",
    "maps", "store", "xbox", "winamp", "notepad++", "brave",
    "opera", "skype", "slack", "premiere", "premiere pro",
    "adobe premiere", "adobe premiere pro", "after effects",
    "photoshop", "illustrator", "lightroom", "audacity",
    "davinci", "davinci resolve", "figma", "blender",
    "autocad", "solidworks", "matlab", "android studio",
    "intellij", "pycharm", "webstorm", "rider", "clion",
    "unity", "unreal", "godot", "steam", "epic games",
    "origin", "battle.net", "valorant", "minecraft",
}

_INVALID_TARGETS = {
    "me", "it", "this", "that", "the", "a", "an",
    "and", "or", "all", "everything", "them", "those",
    "these", "here", "there", "now", "app", "window",
}

_SELF_WORDS = {"seven", "yourself", "self", "you", "assistant", "ai"}
_ACTIVE_WINDOW_WORDS = {
    "it", "this", "that", "the window", "current", "active", "foreground"
}


def process(ctx, deps):
    if ctx.first_word not in ["open", "close", "start", "kill", "launch"]:
        return LayerResult.pass_through()

    config = deps.get("config")
    command_verb = ctx.first_word
    remaining    = ctx.clean_in

    for verb in ["open", "close", "start", "kill", "launch"]:
        if remaining.startswith(verb):
            remaining = remaining[len(verb):].strip()
            break

    tag       = "OPEN" if command_verb in ["open", "start", "launch"] else "CLOSE"
    close_all = False

    if tag == "CLOSE" and remaining.startswith("all "):
        close_all = True
        remaining = remaining[4:].strip()

    for _art in ["the ", "a ", "an "]:
        if remaining.startswith(_art):
            remaining = remaining[len(_art):].strip()
            break

    # Self-referential open commands
    if remaining.lower().strip() in _SELF_WORDS and tag == "OPEN":
        return LayerResult.stop(
            "I am already running. You are talking to me right now."
        )

    if not remaining:
        return LayerResult.pass_through()

    _normalized = remaining.replace(" and ", ",").replace(" & ", ",")
    apps = [a.strip() for a in _normalized.split(",") if a.strip()]
    if not apps:
        apps = [remaining.strip()]

    _cmd_paths   = config.KEY.get("commands", {}).get("app_paths", {})
    _cmd_aliases = config.KEY.get("commands", {}).get("app_aliases", {})

    if tag == "OPEN":
        _validation = _validate_open(apps, _cmd_paths, _cmd_aliases)
        if _validation:
            return LayerResult.stop(_validation)

    if tag == "CLOSE":
        _validation = _validate_close(apps, _cmd_paths)
        if _validation:
            return LayerResult.stop(_validation)

    tags = " ".join([
        f"###{tag}: ALL_{a}" if close_all else f"###{tag}: {a}"
        for a in apps
    ])
    app_list = ", ".join(apps)

    if tag == "OPEN":
        speech = random.choice([
            f"Opening {app_list}.",
            f"On it. {app_list} coming up.",
            f"{app_list}, coming right up.",
            f"Launching {app_list}.",
        ])
    else:
        speech = (
            random.choice([
                f"Closing all {app_list}.",
                f"Shutting down every {app_list}.",
                f"Killing all {app_list} instances."
            ])
            if close_all else
            random.choice([
                f"Closing {app_list}.",
                f"Shutting down {app_list}.",
                f"Done with {app_list}."
            ])
        )

    return LayerResult.stop(f"{speech} {tags}")


def _validate_open(apps, cmd_paths, cmd_aliases):
    """Return an error message if any app is invalid, else None."""
    for _app in apps:
        _app_clean = _app.lower().strip()
        # Known configured app
        if _app_clean in cmd_paths or _app_clean in cmd_aliases:
            continue
        # Common system app
        if _app_clean in _ALWAYS_CLOSEABLE:
            continue
        # Real software heuristics
        _words = _app_clean.split()
        _looks_real = (
            len(_words) >= 2 or           # "premiere pro"
            len(_app_clean) >= 6 or       # "spotify"
            _app_clean.endswith('.exe')
        )
        if _looks_real:
            continue
        return (
            f"I don't see '{_app}' installed. "
            f"If it is a custom file or folder, add it in Commands."
        )
    return None


def _validate_close(apps, cmd_paths):
    """Return response for special close cases, else None."""
    for _app in apps:
        _app_clean = _app.lower().strip()

        # "close it" / "close this" → close active window
        if _app_clean in _ACTIVE_WINDOW_WORDS:
            try:
                import pyautogui as _pag
                _pag.hotkey('alt', 'f4')
            except Exception:
                pass
            return "Closed."

        if _app_clean in _INVALID_TARGETS:
            return "Close which app? Be specific."

        # Reject gibberish
        _has_vowel = any(v in _app_clean for v in "aeiou")
        if not _has_vowel and len(_app_clean) > 3:
            return "That does not look like an app name. What did you want to close?"

        # Reject very short unknown words
        if len(_app_clean) < 3 and _app_clean not in cmd_paths:
            return "Close what? Be more specific."

    return None