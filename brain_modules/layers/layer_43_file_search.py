"""
=============================================================================
LAYER 4.3: FILE SEARCH INTENT

Catches "open my resume", "find my cv", "show pdf" etc.
Bypasses LLM. Uses hands/files.py filesystem crawler.

Detects "clear file phrases":
    - "my resume", "my cv" etc → file intent
    - "how many pdfs", "any documents" → file query
    - File type word + folder/file/my → clear file phrase

Skips if the phrase matches a configured app path/alias
(so "open notes" opens Notes app, not searching for files named notes).
=============================================================================
"""

import traceback
from colorama import Fore
from brain_modules.layer_result import LayerResult


_FILE_INTENT_TRIGGERS = [
    "my resume", "my cv", "my document", "my file", "my photo",
    "my image", "my video", "my pdf", "my report", "my project",
    "show resume", "find resume", "open resume", "open cv",
    "show my", "find my", "where is my",
]

_OPEN_INTENTS = [
    "open", "show", "find", "display", "launch", "pull up",
    "bring up", "view", "look at", "see my", "access"
]

_QUERY_INTENTS = [
    "how many", "do i have", "any", "list", "show all",
    "find all", "what files", "search for"
]


def process(ctx, deps):
    config = deps.get("config")

    _has_file_intent = any(t in ctx.clean_in for t in _FILE_INTENT_TRIGGERS)
    _has_open_intent = any(t in ctx.clean_in for t in _OPEN_INTENTS)

    _has_file_query = (
        any(fw in ctx.clean_in for fw in ctx.FILE_WORDS)
        and any(q in ctx.clean_in for q in _QUERY_INTENTS)
    )

    _cmd_paths_check   = config.KEY.get("commands", {}).get("app_paths", {})
    _cmd_aliases_check = config.KEY.get("commands", {}).get("app_aliases", {})
    _is_configured     = any(k in ctx.clean_in for k in _cmd_paths_check) or \
                         any(k in ctx.clean_in for k in _cmd_aliases_check)

    _has_file_type = any(fw in ctx.clean_in for fw in ctx.FILE_WORDS)

    _clear_file_phrase = _has_file_intent or _has_file_query or (
        _has_file_type and (
            any(w in ctx.clean_in for w in ["my ", "folder", "file"]) or
            any(w in ctx.clean_in for w in ctx.ALWAYS_FILE_WORDS)
        )
    )

    if not (_has_file_type and _clear_file_phrase and not _is_configured):
        return LayerResult.pass_through()

    try:
        from hands.files import (
            search_files, open_file,
            format_results_for_speech, format_results_for_chat
        )

        _search_terms = [fw for fw in ctx.FILE_WORDS if fw in ctx.clean_in]
        _orig_words = ctx.prompt_text.split()
        _proper = [w.lower() for w in _orig_words
                   if w[0].isupper() and w.lower() not in
                   {"open", "show", "find", "my", "the", "a", "can", "you"}]
        _search_query = " ".join(_search_terms + _proper) or ctx.clean_in

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
            return LayerResult.stop(
                f"I searched Desktop, Documents, Downloads, and OneDrive "
                f"but found nothing matching '{_search_query}'. "
                f"Add the exact path in Commands if you know where it is."
            )

        # Build voice response
        _names = [r["name"] for r in results]
        _count = len(results)

        if _count == 1:
            _list_str = f"one file: {_names[0]}"
        elif _count == 2:
            _list_str = f"two files: {_names[0]} and {_names[1]}"
        else:
            _list_str = f"{_count} files: {', '.join(_names[:3])}"
            if _count > 3:
                _list_str += f" and {_count - 3} more"

        # Open if user asked to open
        if _has_open_intent or _has_file_intent:
            open_file(results[0]["path"])
            if _count == 1:
                return LayerResult.stop(
                    f"Found and opened {_names[0]}. Path is in the chat."
                )
            return LayerResult.stop(
                f"Found {_list_str}. "
                f"Opened the top match: {_names[0]}. "
                f"All paths are in the chat."
            )

        # Count/list query — just report
        return LayerResult.stop(
            f"Found {_list_str}. "
            f"Full paths and details are in the chat below."
        )

    except Exception as _file_err:
        print(Fore.YELLOW + f"[BRAIN] File search failed: {_file_err}")
        traceback.print_exc()
        # Fall through to LLM on error
        return LayerResult.pass_through()