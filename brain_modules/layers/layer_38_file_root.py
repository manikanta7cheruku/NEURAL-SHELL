"""
=============================================================================
LAYER 3.8: FILE SEARCH ROOT REGISTRATION

Catches:
    "add M:\\adobe2 to search folders"
    "remember to look in M:\\edit"
    "search in D:\\Projects"

Registers new folder root in config for future file searches.
=============================================================================
"""

import os
import re
from colorama import Fore
from brain_modules.layer_result import LayerResult


_ADD_ROOT_TRIGGERS = [
    "add to search", "add to your search", "remember to search",
    "search in", "also search", "look in", "search folder",
    "add search folder", "include folder", "include in search",
]


def process(ctx, deps):
    config = deps.get("config")

    _has_add_root = any(t in ctx.clean_in for t in _ADD_ROOT_TRIGGERS)
    _path_match = re.search(r'[a-zA-Z]:\\[^\s]+', ctx.prompt_text)

    if not (_has_add_root and _path_match):
        return LayerResult.pass_through()

    _new_root = _path_match.group(0).rstrip('.,!?')

    if not os.path.exists(_new_root):
        return LayerResult.stop(
            f"That path does not exist: {_new_root}. Check the spelling."
        )

    try:
        _current_roots = config.KEY.get("file_search_roots", [])
        if _new_root not in _current_roots:
            _current_roots.append(_new_root)
            config.update_config({"file_search_roots": _current_roots})
            # Rebuild search roots immediately
            from hands.files import _build_search_roots
            _build_search_roots()
            return LayerResult.stop(
                f"Got it. I will search {_new_root} from now on. "
                f"That folder is now in my search list."
            )
        else:
            return LayerResult.stop(f"Already searching {_new_root}.")
    except Exception as _root_err:
        print(Fore.YELLOW + f"[BRAIN] Root registration failed: {_root_err}")
        return LayerResult.stop("Could not save that folder. Try again.")