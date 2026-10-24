"""
=============================================================================
LAYER 4.3: FILE SEARCH INTENT

Catches "open my resume", "find my cv", "open gokarna video",
"open download folder", "open 0517" etc.

Bypasses LLM. Uses hands/files.py filesystem search.

NEW in v4:
    - "open files" / "open explorer" bypass to layer 4.5 (app open)
    - Folder-first detection for "download folder", "screenshots" etc.
    - Any "open X" where X is not a known app tries file search
    - Proper speech formatting (no robotic filename reading)
=============================================================================
"""

import os
import re
import traceback
from colorama import Fore
from brain_modules.layer_result import LayerResult


_EXPLORER_WORDS = {
    "files", "file explorer", "explorer", "file manager",
    "my computer", "this pc", "my pc",
}

_FOLDER_SHORTCUT_WORDS = {
    "downloads", "download", "documents", "document",
    "pictures", "picture", "photos", "videos", "video",
    "music", "desktop", "screenshots", "screenshot",
    "recordings", "captures", "onedrive", "recent",
    "startup", "appdata", "roaming", "temp",
}

_OPEN_INTENTS = [
    "open", "show", "find", "display", "launch", "pull up",
    "bring up", "view", "look at", "see my", "access"
]

_QUERY_INTENTS = [
    "how many", "do i have", "any", "list", "show all",
    "find all", "what files", "search for"
]

_FILE_INTENT_TRIGGERS = [
    "my resume", "my cv", "my document", "my file", "my photo",
    "my image", "my video", "my pdf", "my report", "my project",
    "show resume", "find resume", "open resume", "open cv",
    "show my", "find my", "where is my",
]


def _is_likely_app(target: str) -> bool:
    """Check if the target is clearly an app, not a file."""
    clean = target.lower().strip()

    if clean in _EXPLORER_WORDS:
        return True

    try:
        from hands.app_launcher import is_known_app
        if is_known_app(clean):
            return True
    except Exception:
        pass

    try:
        from brain_modules.layers.layer_45_app import _ALWAYS_CLOSEABLE
        if clean in _ALWAYS_CLOSEABLE:
            return True
    except Exception:
        pass

    try:
        from hands.app_discovery import search_apps
        hits = search_apps(clean, limit=1)
        if hits and hits[0].get("score", 0) > 500:
            return True
    except Exception:
        pass

    web_services = {
        "github", "youtube", "gmail", "google", "twitter", "x",
        "linkedin", "reddit", "facebook", "instagram", "netflix",
        "amazon", "twitch", "stackoverflow", "chatgpt", "claude",
        "notion", "wikipedia", "spotify", "discord", "telegram",
        "whatsapp", "zoom", "teams", "slack",
    }
    if clean in web_services:
        return True

    if clean.endswith(('.com', '.org', '.net', '.io', '.dev')):
        return True

    return False


_ATTACHED_REF = re.compile(r"^(?:open|show|view|display) (?:the|this|that|my) (?:pdf|document|doc|file|notes|slides|sheet)$")


def _open_attached(ctx):
    """In a chat with an attached document, "open the pdf" means that document, not a search of the PC."""
    if not _ATTACHED_REF.match(ctx.clean_in.strip(" .!?")):
        return None
    try:
        from knowledge import store
        ids = store.attached(ctx.conversation_id)
    except Exception:
        return None
    if not ids:
        return None
    doc = store.get(ids[-1])
    return f"Opened {doc['name']}." if store.open_original(doc["id"]) else f"I couldn't open {doc['name']}."


def _open_latest(ctx):
    """"open the last pdf I downloaded", "show my latest screenshot": the newest matching file, by date."""
    try:
        from hands.files import latest_file, open_file
        hit = latest_file(ctx.clean_in)
    except Exception:
        return None
    if not hit:
        return None
    where = os.path.basename(os.path.dirname(hit["path"]))
    if not open_file(hit["path"]):
        return f"I found {hit['name']} in {where} but Windows couldn't open it."
    return f"Opened {hit['name']} from {where}, saved {hit['modified']}."


def process(ctx, deps):
    if ctx.first_word not in ["open", "show", "find", "display",
                               "launch", "view", "pull", "bring"]:
        return LayerResult.pass_through()
    if re.search(r"\b(?:workspaces?|triggers?)\b", ctx.clean_in):
        return LayerResult.pass_through()          # Seven's own workspaces and triggers, never files
    attached = _open_attached(ctx)
    if attached:
        return LayerResult.stop(attached)
    newest = _open_latest(ctx)
    if newest:
        return LayerResult.stop(newest)

    config = deps.get("config")

    _has_open_intent = any(t in ctx.clean_in for t in _OPEN_INTENTS)
    _has_file_intent = any(t in ctx.clean_in for t in _FILE_INTENT_TRIGGERS)
    _has_file_query = (
        any(fw in ctx.clean_in for fw in ctx.FILE_WORDS)
        and any(q in ctx.clean_in for q in _QUERY_INTENTS)
    )
    _has_file_type = any(fw in ctx.clean_in for fw in ctx.FILE_WORDS)

    # Extract target (everything after the verb)
    remaining = ctx.clean_in
    for verb in ["open", "show", "find", "display", "launch",
                 "pull up", "bring up", "view"]:
        if remaining.startswith(verb):
            remaining = remaining[len(verb):].strip()
            break

    if not remaining:
        return LayerResult.pass_through()

    # Remove articles
    for art in ["the ", "a ", "an ", "my "]:
        if remaining.startswith(art):
            remaining = remaining[len(art):].strip()
            break

    # Bypass: "open files" / "open explorer" -> let layer 4.5 handle as app
    if remaining.lower().strip() in _EXPLORER_WORDS:
        return LayerResult.pass_through()

    # Bypass: "open downloads folder" / "open screenshots" etc.
    # These are special folder shortcuts handled by app_launcher
    _remaining_clean = remaining.lower().strip()
    _remaining_clean = _remaining_clean.replace(" folder", "").replace(" directory", "").strip()
    if _remaining_clean in _FOLDER_SHORTCUT_WORDS:
        return LayerResult.pass_through()

    # Bypass: clearly an app name -> let layer 4.5 handle
    if _is_likely_app(remaining) and not _has_file_type and not _has_file_intent:
        return LayerResult.pass_through()

    # Determine if this should trigger file search
    _clear_file_phrase = (
        _has_file_intent
        or _has_file_query
        or _has_file_type
        or any(w in remaining for w in ["folder", "directory", "dir"])
        or not _is_likely_app(remaining)
    )

    if not _clear_file_phrase:
        return LayerResult.pass_through()

    try:
        from hands.files import (
            search_files, open_file,
            format_results_for_speech, format_results_for_chat
        )

        # Build search query from the remaining text
        _search_query = remaining

        _uname = config.KEY.get("identity", {}).get("user_name", "")
        results = search_files(_search_query, user_name=_uname)

        # Push results to frontend chat
        try:
            from backend.api_server import set_state as _api_set_file
            chat_data = format_results_for_chat(results, _search_query)
            _api_set_file("file_search_results", chat_data)
        except Exception:
            pass

        if not results:
            # No files found. If it looked like an app, pass through to layer 4.5
            if _is_likely_app(remaining):
                return LayerResult.pass_through()
            speech = format_results_for_speech([], _search_query)
            return LayerResult.stop(speech)

        # Decide if we will auto-open the top result
        # "my photos from goa" asks for several files: show the list instead of opening one of them.
        _plural = bool(re.search(r"\b(?:photos|pictures|images|videos|files|documents|pdfs|screenshots|songs|"
                                 r"recordings|notes)\b", remaining))
        from hands.files import CONFIDENT_SCORE
        _will_open = ((_has_open_intent or _has_file_intent) and not _plural
                      and results[0].get("score", 0) >= CONFIDENT_SCORE)
        _opened_idx = 0 if _will_open else None

        # Remember this search in working memory for reference resolution
        # opened_index tells the resolver which item "it" / "again" refers to
        try:
            from brain_modules.dialogue_manager import remember_action
            remember_action(
                "file_search",
                _search_query,
                results,
                opened_index=_opened_idx,
            )
        except Exception as _mem_err:
            print(Fore.YELLOW + f"[LAYER43] Memory store skipped: {_mem_err}")

        # Open if user asked to open
        if _will_open:
            open_file(results[0]["path"])
            speech = format_results_for_speech(results, _search_query, opened=True)
            return LayerResult.stop(speech)

        # Just report
        speech = format_results_for_speech(results, _search_query, opened=False)
        return LayerResult.stop(speech)

    except Exception as _file_err:
        print(Fore.YELLOW + f"[BRAIN] File search failed: {_file_err}")
        traceback.print_exc()
        return LayerResult.pass_through()