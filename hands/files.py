"""
hands/files.py
Seven — Smart File Search and Open
Version: 2.0 — Complete rewrite. No Program Files. Smart scoring. Ambiguity handling.

SCOPE:
    Searches user directories only: Desktop, Documents, Downloads,
    OneDrive, Pictures, Videos, Music. Never system directories.

SCORING LOGIC:
    Exact name match       = 100 pts
    Name starts with kw    = 50  pts
    Keyword is whole word  = 30  pts
    Keyword is substring   = 10  pts
    Recent file (<30 days) = +20 pts
    Extension type match   = +15 pts

LIMITATIONS (honest):
    - Matches filenames only, not file contents
    - Works when filename describes the file ("resume_2025.pdf")
    - Fails when filename is vague ("doc1.pdf", "untitled.docx")
    - For vague files: user should use Commands section to add path manually
"""

import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from colorama import Fore

# ─────────────────────────────────────────────
# SEARCH ROOTS — user directories ONLY
# Never Program Files, never AppData, never Windows
# ─────────────────────────────────────────────
SEARCH_ROOTS = []
MAX_DEPTH    = 5      # Max folder depth to walk
MAX_FILES    = 10000  # Safety cap — stop after this many files scanned

def _build_search_roots():
    global SEARCH_ROOTS
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Videos"),
        os.path.join(home, "Music"),
        os.path.join(home, "OneDrive"),
        os.path.join(home, "OneDrive", "Documents"),
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "OneDrive", "Pictures"),
    ]

    # Add custom search roots from config
    # User can add paths via voice: "seven, add M:\adobe2 to your search folders"
    # Or via Settings UI file_search_roots field
    try:
        import config
        extra = config.KEY.get("file_search_roots", [])
        if isinstance(extra, list):
            candidates.extend(extra)
            if extra:
                print(Fore.CYAN + f"[FILES] Custom roots from config: {extra}")
    except Exception:
        pass
    # Deduplicate resolved paths (OneDrive sometimes symlinks to home)
    seen = set()
    SEARCH_ROOTS = []
    for p in candidates:
        try:
            real = os.path.realpath(p)
            if os.path.exists(p) and real not in seen:
                seen.add(real)
                SEARCH_ROOTS.append(p)
        except Exception:
            pass
    print(Fore.CYAN + f"[FILES] Search roots: {len(SEARCH_ROOTS)} directories")

_build_search_roots()


# ─────────────────────────────────────────────
# SKIP LISTS
# ─────────────────────────────────────────────
_SKIP_DIRS = {
    '$RECYCLE.BIN', 'System Volume Information', 'node_modules',
    '.git', '__pycache__', 'Windows', 'System32', 'SysWOW64',
    'WinSxS', 'Temp', 'temp', '.vs', 'dist', 'build',
    'venv', '.venv', 'env', 'site-packages',
}

# Extensions to always ignore (system, temp, package files)
_SKIP_EXTENSIONS = {
    '.dll', '.sys', '.exe', '.msi', '.tmp', '.log', '.ini',
    '.lnk', '.url', '.db', '.sqlite', '.cache', '.pyc',
    '.pyo', '.class', '.o', '.obj', '.lib', '.pdb',
}


# ─────────────────────────────────────────────
# KEYWORD EXTRACTION
# ─────────────────────────────────────────────
_STOP_WORDS = {
    "open", "show", "find", "my", "the", "a", "an", "to", "me",
    "please", "can", "you", "your", "and", "or", "all", "any",
    "some", "have", "do", "i", "is", "are", "how", "many", "what",
    "where", "which", "get", "bring", "pull", "up", "that", "this",
    "it", "from", "in", "on", "at", "for", "with", "tell", "give",
    "look", "see", "check", "boss", "friend", "friends",
}

# File type words map spoken word → extensions to prioritize
_TYPE_MAP = {
    "resume":       [".pdf", ".docx", ".doc"],
    "cv":           [".pdf", ".docx", ".doc"],
    "pdf":          [".pdf"],
    "document":     [".docx", ".doc", ".odt", ".txt"],
    "doc":          [".docx", ".doc"],
    "photo":        [".jpg", ".jpeg", ".png", ".heic", ".raw"],
    "image":        [".jpg", ".jpeg", ".png", ".svg", ".webp"],
    "screenshot":   [".jpg", ".jpeg", ".png"],
    "video":        [".mp4", ".mov", ".avi", ".mkv", ".wmv"],
    "music":        [".mp3", ".wav", ".flac", ".aac", ".m4a"],
    "audio":        [".mp3", ".wav", ".flac", ".aac"],
    "presentation": [".pptx", ".ppt", ".key"],
    "spreadsheet":  [".xlsx", ".xls", ".csv"],
    "report":       [".pdf", ".docx", ".xlsx"],
    "invoice":      [".pdf", ".docx"],
    "contract":     [".pdf", ".docx"],
    "project":      [".docx", ".pdf", ".xlsx"],
    "edit":         [".mp4", ".mov", ".prproj", ".aep"],
    "folder":       [],   # handled separately
    "directory":    [],
}


def _extract_keywords(query: str) -> tuple:
    """
    Extract search keywords and target extensions from natural language query.

    Returns:
        (keywords: list, target_extensions: list, looking_for_folder: bool)
    """
    words   = query.lower().split()
    looking_for_folder = any(w in words for w in ["folder", "directory", "dir"])

    # Find file type words to get target extensions
    target_extensions = []
    type_keywords     = []
    for word in words:
        if word in _TYPE_MAP and _TYPE_MAP[word]:
            target_extensions.extend(_TYPE_MAP[word])
            type_keywords.append(word)

    # Content keywords — everything that is not a stop word
    keywords = [
        w for w in words
        if w not in _STOP_WORDS and len(w) > 1
    ]

    if not keywords:
        keywords = [w for w in words if len(w) > 1]

    return keywords, list(set(target_extensions)), looking_for_folder


def _score_file(filename: str, keywords: list, target_extensions: list,
                modified_time: float, user_name: str = "") -> int:
    """
    Score a filename. Higher = better match.
    Returns 0 if no keyword matches at all.
    """
    name_no_ext = os.path.splitext(filename)[0].lower()
    name_lower  = filename.lower()
    ext         = os.path.splitext(filename)[1].lower()
    score       = 0

    # Normalize: replace separators with space for word matching
    name_words = name_no_ext.replace('_', ' ').replace('-', ' ').replace('.', ' ').split()

    # Boost files that contain the user's name — more likely to be theirs
    if user_name and user_name.lower() in name_lower:
        score += 25

    matched_any = False
    for kw in keywords:
        kw_lower = kw.lower()

        # Skip type words — they are used for extension filtering, not name matching
        if kw_lower in _TYPE_MAP and kw_lower not in ("resume", "cv", "edit"):
            continue

        if kw_lower in name_words:
            # Exact word match — strongest signal
            score      += 30
            matched_any = True
        elif name_no_ext == kw_lower:
            # Entire filename matches keyword
            score      += 100
            matched_any = True
        elif name_no_ext.startswith(kw_lower):
            # Filename starts with keyword
            score      += 50
            matched_any = True
        elif kw_lower in name_lower:
            # Substring match — weakest
            score      += 10
            matched_any = True

    if not matched_any:
        return 0

    # Extension type bonus
    if target_extensions and ext in target_extensions:
        score += 15

    # Recency bonus — files modified in last 30 days are more relevant
    try:
        age_days = (time.time() - modified_time) / 86400
        if age_days < 7:
            score += 20
        elif age_days < 30:
            score += 10
    except Exception:
        pass

    return score


# ─────────────────────────────────────────────
# MAIN SEARCH FUNCTION
# ─────────────────────────────────────────────

def search_files(query: str, max_results: int = 8, user_name: str = "") -> list:
    """
    Search user directories for files matching a natural language query.

    Returns list of result dicts sorted by relevance.
    Empty list if nothing found.
    """
    keywords, target_extensions, looking_for_folder = _extract_keywords(query)

    print(Fore.CYAN + f"[FILES] Query: '{query}'")
    print(Fore.CYAN + f"[FILES] Keywords: {keywords} | Extensions: {target_extensions} | Folder: {looking_for_folder}")

    if not keywords:
        print(Fore.YELLOW + "[FILES] No keywords extracted — aborting search")
        return []

    results   = []
    seen      = set()
    scanned   = 0

    for root in SEARCH_ROOTS:
        if scanned >= MAX_FILES:
            break
        try:
            for dirpath, dirnames, filenames in _walk_with_depth(root, MAX_DEPTH):
                if scanned >= MAX_FILES:
                    break

                # Prune skip dirs in place
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith('.') and d not in _SKIP_DIRS
                ]

                # Folder search
                if looking_for_folder:
                    for dname in dirnames:
                        score = _score_file(dname, keywords, [], 0)
                        if score == 0:
                            continue
                        full = os.path.join(dirpath, dname)
                        real = os.path.realpath(full)
                        if real in seen:
                            continue
                        seen.add(real)
                        results.append({
                            "name":     dname,
                            "path":     full,
                            "size_kb":  0,
                            "modified": "",
                            "ext":      "folder",
                            "score":    score,
                        })

                # File search
                for fname in filenames:
                    scanned += 1
                    ext = os.path.splitext(fname)[1].lower()

                    # Skip system/temp files
                    if ext in _SKIP_EXTENSIONS:
                        continue
                    if fname.startswith('.') or fname.startswith('~$'):
                        continue

                    full = os.path.join(dirpath, fname)
                    real = os.path.realpath(full)
                    if real in seen:
                        continue

                    try:
                        mtime = os.path.getmtime(full)
                    except Exception:
                        mtime = 0

                    score = _score_file(fname, keywords, target_extensions, mtime, user_name)
                    if score == 0:
                        continue

                    seen.add(real)
                    try:
                        size_kb  = round(os.path.getsize(full) / 1024, 1)
                        modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        size_kb  = 0
                        modified = ""

                    results.append({
                        "name":     fname,
                        "path":     full,
                        "size_kb":  size_kb,
                        "modified": modified,
                        "ext":      ext,
                        "score":    score,
                    })

        except PermissionError:
            continue
        except Exception as e:
            print(Fore.YELLOW + f"[FILES] Walk error in {root}: {e}")
            continue

    print(Fore.CYAN + f"[FILES] Scanned {scanned} files, found {len(results)} matches")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def _walk_with_depth(root: str, max_depth: int):
    """
    os.walk with depth limit. Yields (dirpath, dirnames, filenames).
    Prevents walking deep into system directories.
    """
    root   = os.path.abspath(root)
    prefix = len(root.split(os.sep))

    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(dirpath.split(os.sep)) - prefix
        if depth >= max_depth:
            dirnames.clear()  # Do not go deeper
        yield dirpath, dirnames, filenames


# ─────────────────────────────────────────────
# OPEN FILE / FOLDER
# ─────────────────────────────────────────────

def open_file(path: str) -> bool:
    """Open a file or folder instantly."""
    try:
        if os.path.isdir(path):
            subprocess.Popen(f'explorer "{path}"', shell=True)
        else:
            os.startfile(path)
        print(Fore.GREEN + f"[FILES] Opened: {path}")
        return True
    except Exception as e:
        print(Fore.RED + f"[FILES] Open failed {path}: {e}")
        return False


# ─────────────────────────────────────────────
# RESPONSE FORMATTERS
# ─────────────────────────────────────────────

def format_results_for_speech(results: list, query: str,
                               opened: bool = False) -> str:
    """Short spoken response. TARS-style."""
    if not results:
        return (
            f"Nothing found for '{query}'. "
            f"If you know the path, add it in Commands."
        )

    count = len(results)
    top   = results[0]["name"]

    if count == 1:
        if opened:
            return f"Found it. Opened {top}."
        return f"One match: {top}. Check the chat for the path."

    if count <= 3:
        names = ", ".join(r["name"] for r in results)
        if opened:
            return f"Found {count} matches. Opened the top one: {top}. Others in the chat."
        return f"Found {count}: {names}. Which one did you want?"

    if opened:
        return f"Found {count} matches. Opened the best one: {top}. All paths in the chat."
    return f"Found {count} files for '{query}'. Check the chat — pick the one you want."


def format_results_for_chat(results: list, query: str) -> dict:
    """Structured dict for React chat file results card."""
    return {
        "type":    "file_search",
        "query":   query,
        "count":   len(results),
        "results": [
            {
                "name":     r["name"],
                "path":     r["path"],
                "size_kb":  r["size_kb"],
                "modified": r["modified"],
                "ext":      r["ext"],
            }
            for r in results
        ],
        "message": f"Found {len(results)} file(s) matching '{query}'" if results else f"No files found for '{query}'",
    }