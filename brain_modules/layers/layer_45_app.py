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

    # Detect "in browser" / "in chrome" / "in edge" force-browser mode
    _force_browser = False
    for _suffix in [" in browser", " in chrome", " in edge",
                    " in firefox", " in web"]:
        if remaining.endswith(_suffix):
            _force_browser = True
            remaining = remaining[:-len(_suffix)].strip()
            break

    # Handle force-browser: open URL directly, skip app launch
    if _force_browser and tag == "OPEN":
        import webbrowser
        _url_name = remaining.lower().strip()
        _url = f"https://{_url_name}.com"
        try:
            webbrowser.open(_url)
            return LayerResult.stop(
                f"Opening {_url_name} in your browser."
            )
        except Exception:
            return LayerResult.stop(
                f"Could not open {_url_name} in the browser."
            )

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

    if tag == "OPEN":
        _validation = _validate_open(apps)
        if _validation:
            return LayerResult.stop(_validation)

    if tag == "CLOSE":
        _validation = _validate_close(apps)
        if _validation:
            return LayerResult.stop(_validation)

        # Check if closing a browser with multiple windows
        _BROWSERS = {"chrome", "firefox", "edge", "brave", "opera", "vivaldi"}
        for _app in apps:
            _app_clean = _app.lower().strip()
            if _app_clean in _BROWSERS and not close_all:
                _win_count = _count_app_windows(_app_clean)
                if _win_count >= 2:
                    from brain_modules.dialogue_manager import set_pending
                    set_pending("close_confirm", {
                        "app": _app_clean,
                        "count": _win_count,
                    }, timeout_sec=30)
                    return LayerResult.stop(
                        f"You have {_win_count} {_app_clean} windows open. "
                        f"Close all of them, just the active one, or cancel?"
                    )

    tags = " ".join([
        f"###{tag}: ALL_{a}" if close_all else f"###{tag}: {a}"
        for a in apps
    ])
    app_list = ", ".join(apps)

    if tag == "OPEN":
        if len(apps) == 1:
            speech = random.choice([
                f"Opening {app_list} for you.",
                f"Sure, launching {app_list}.",
                f"On it, {app_list} coming up.",
                f"Got it, opening {app_list}.",
                f"{app_list}, here we go.",
                f"Alright, {app_list} coming right up.",
            ])
        else:
            speech = random.choice([
                f"Opening {app_list} for you.",
                f"Sure, launching all of those.",
                f"On it, bringing up {app_list}.",
                f"Got it, opening them now.",
            ])
    else:
        if close_all:
            speech = random.choice([
                f"Closing all {app_list} windows now.",
                f"Shutting down every {app_list} for you.",
                f"Killing all {app_list} instances.",
                f"Alright, wiping out {app_list}.",
            ])
        else:
            speech = random.choice([
                f"Closing {app_list} for you.",
                f"Sure, shutting down {app_list}.",
                f"Done, {app_list} closed.",
                f"Got it, {app_list} is gone.",
                f"Alright, closing {app_list}.",
            ])

    return LayerResult.stop(f"{speech} {tags}")


def _validate_open(apps):
    """Return an error message if any app is clearly invalid, else None."""
    for _app in apps:
        _app_clean = _app.lower().strip()
        # Common system app
        if _app_clean in _ALWAYS_CLOSEABLE:
            continue
        # Check app discovery index
        try:
            from hands.app_discovery import search_apps
            hits = search_apps(_app_clean, limit=1)
            if hits:
                continue
        except Exception:
            pass
        # Real software heuristics (fallback when index not ready)
        _words = _app_clean.split()
        _looks_real = (
            len(_words) >= 2 or
            len(_app_clean) >= 4 or
            _app_clean.endswith('.exe') or
            _app_clean.isdigit()
        )
        if _looks_real:
            continue
        # Check web services before rejecting
        _web_services = {
            "github", "youtube", "gmail", "google", "twitter",
            "linkedin", "reddit", "facebook", "instagram",
            "netflix", "amazon", "twitch", "stackoverflow",
            "chatgpt", "claude", "notion", "wikipedia", "spotify",
        }
        if _app_clean in _web_services:
            continue
        return f"I cannot find '{_app}' on your system."
    return None


def _validate_close(apps):
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
        if len(_app_clean) < 3:
            return "Close what? Be more specific."

    return None

def _count_app_windows(app_name: str) -> int:
    """Count visible top-level windows belonging to an app."""
    count = 0
    try:
        import win32gui

        def _callback(hwnd, _):
            nonlocal count
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if app_name in title and len(title) > 3:
                    count += 1

        win32gui.EnumWindows(_callback, None)
    except Exception:
        # Fallback: count processes
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    pname = (proc.info['name'] or '').lower()
                    if app_name in pname:
                        count += 1
                except Exception:
                    pass
            # Rough estimate: processes / 3 for Chrome-like apps
            if app_name in ("chrome", "edge", "brave"):
                count = max(1, count // 3)
        except Exception:
            count = 1
    return max(count, 1)