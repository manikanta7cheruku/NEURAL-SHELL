"""
hands/files.py
Seven - Smart File Search and Open
Version: 4.0 - Fuzzy + phonetic matching, folder priority, proper scoring.

SCORING RULES:
    1. Specific keywords (not type words) MUST match the filename.
       If none match, score is 0 regardless of extension.
    2. Type keywords (video, photo, resume) filter by extension
       and boost if the type word also appears in the name.
    3. Fuzzy matching via rapidfuzz catches typos.
    4. Phonetic matching via Soundex catches "cheruku" vs "Cheruku".
    5. Folder requests prioritize folder results heavily.

PUBLIC API:
    search_files(query, max_results, user_name) -> list
    open_file(path) -> bool
    format_results_for_speech(results, query, opened) -> str
    format_results_for_chat(results, query) -> dict
    build_file_index(force) -> None
    rescan_drives() -> None
"""

import os
import re
import sqlite3
import subprocess
import string
import threading
import time
from datetime import datetime, timedelta
from colorama import Fore

# -- Fuzzy matching (optional but strongly recommended) --
try:
    from rapidfuzz import fuzz as _fuzz
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False

# -- Database path --
try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception:
    _SEVEN_DATA = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "seven_data"
    )

os.makedirs(_SEVEN_DATA, exist_ok=True)
FILE_INDEX_DB = os.path.join(_SEVEN_DATA, "file_index.db")

MAX_DEPTH = 10
MAX_FILES = 400000
STALE_AFTER = timedelta(hours=6)
_build_lock = threading.Lock()

# -- Search Roots --
SEARCH_ROOTS = []


def _build_search_roots():
    """Auto-detect user directories on ALL mounted drives."""
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

    skip_dirs = {
        "windows", "program files", "program files (x86)",
        "programdata", "recovery", "system volume information",
        "$recycle.bin", "boot", "perflogs", "users",
        "intel", "amd", "nvidia", "msocache", "config.msi",
    }

    drives_found = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if not os.path.exists(drive) or letter == "C":
            continue
        drives_found.append(letter)
        try:
            for entry in os.listdir(drive):
                full = os.path.join(drive, entry)
                if not os.path.isdir(full):
                    continue
                if entry.startswith('$') or entry.startswith('.'):
                    continue
                if entry.lower() in skip_dirs:
                    continue
                candidates.append(full)
                print(Fore.CYAN + f"[FILES] Auto-detected: {full}")
        except (PermissionError, OSError) as e:
            print(Fore.YELLOW + f"[FILES] Cannot read {drive}: {e}")
            continue

    print(Fore.CYAN + f"[FILES] Drives scanned: {', '.join(drives_found) or 'none beyond C:'}")

    try:
        import config
        extra = config.KEY.get("file_search_roots", [])
        if isinstance(extra, list):
            candidates.extend(extra)
    except Exception:
        pass

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
    print(Fore.CYAN + f"[FILES] Search roots: {len(SEARCH_ROOTS)} directories active")


_build_search_roots()


def rescan_drives():
    """Re-detect drives and rebuild index. Call after plugging in new drives."""
    _build_search_roots()
    build_file_index(force=True)


# -- Skip Lists --
_SKIP_DIRS = {
    '$RECYCLE.BIN', 'System Volume Information', 'node_modules',
    '.git', '__pycache__', 'Windows', 'System32', 'SysWOW64',
    'WinSxS', 'Temp', 'temp', '.vs', 'dist', 'build',
    'venv', '.venv', 'env', 'site-packages', 'AppData',
    '.next', '.nuxt', 'target', '.gradle', '.m2',
}

_SKIP_EXTENSIONS = {
    '.dll', '.sys', '.exe', '.msi', '.tmp', '.log', '.ini',
    '.lnk', '.url', '.db', '.sqlite', '.cache', '.pyc',
    '.pyo', '.class', '.o', '.obj', '.lib', '.pdb', '.map',
    '.woff', '.woff2', '.ttf', '.eot', '.ico',
}

# -- Keyword Extraction --
_STOP_WORDS = {
    "open", "show", "find", "my", "the", "a", "an", "to", "me",
    "please", "can", "you", "your", "and", "or", "all", "any",
    "some", "have", "do", "i", "is", "are", "how", "many", "what",
    "where", "which", "get", "bring", "pull", "up", "that", "this",
    "it", "from", "in", "on", "at", "for", "with", "tell", "give",
    "look", "see", "check", "boss", "friend", "friends",
}

_FOLDER_WORDS = {"folder", "directory", "dir", "folders", "directories"}

_COMMON_FOLDERS = {
    "downloads", "documents", "pictures", "screenshots", "desktop",
    "music", "videos", "photos", "images", "movies", "projects",
    "recordings", "captures", "snippets", "wallpapers",
}

_TYPE_MAP = {
    "resume":       [".pdf", ".docx", ".doc"],
    "resumes":      [".pdf", ".docx", ".doc"],
    "cv":           [".pdf", ".docx", ".doc"],
    "pdf":          [".pdf"],
    "document":     [".docx", ".doc", ".odt", ".txt"],
    "documents":    [".docx", ".doc", ".odt", ".txt"],
    "doc":          [".docx", ".doc"],
    "photo":        [".jpg", ".jpeg", ".png", ".heic", ".raw"],
    "photos":       [".jpg", ".jpeg", ".png", ".heic", ".raw"],
    "image":        [".jpg", ".jpeg", ".png", ".svg", ".webp"],
    "images":       [".jpg", ".jpeg", ".png", ".svg", ".webp"],
    "screenshot":   [".jpg", ".jpeg", ".png"],
    "screenshots":  [".jpg", ".jpeg", ".png"],
    "video":        [".mp4", ".mov", ".avi", ".mkv", ".wmv"],
    "videos":       [".mp4", ".mov", ".avi", ".mkv", ".wmv"],
    "music":        [".mp3", ".wav", ".flac", ".aac", ".m4a"],
    "audio":        [".mp3", ".wav", ".flac", ".aac"],
    "presentation": [".pptx", ".ppt", ".key"],
    "spreadsheet":  [".xlsx", ".xls", ".csv"],
    "report":       [".pdf", ".docx", ".xlsx"],
    "invoice":      [".pdf", ".docx"],
    "contract":     [".pdf", ".docx"],
    "project":      [".docx", ".pdf", ".xlsx"],
    "edit":         [".mp4", ".mov", ".prproj", ".aep"],
}


def _extract_keywords(query: str) -> tuple:
    """Extract search keywords, target extensions, and folder intent."""
    words = query.lower().split()
    looking_for_folder = any(w in _FOLDER_WORDS for w in words)

    target_extensions = []
    for word in words:
        if word in _TYPE_MAP and _TYPE_MAP[word]:
            target_extensions.extend(_TYPE_MAP[word])

    # Also detect common folder names as folder intent
    if any(w in _COMMON_FOLDERS for w in words):
        looking_for_folder = True

    keywords = [
        w for w in words
        if w not in _STOP_WORDS and w not in _FOLDER_WORDS and len(w) > 1
    ]
    if not keywords:
        keywords = [w for w in words if len(w) > 1]

    return keywords, list(set(target_extensions)), looking_for_folder


# -- Phonetic Matching --
def _soundex(name: str) -> str:
    """Simple Soundex encoding for phonetic matching."""
    if not name:
        return ""
    name = re.sub(r'[^a-zA-Z]', '', name).upper()
    if not name:
        return ""
    first = name[0]
    mapping = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2',
        'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3', 'L': '4',
        'M': '5', 'N': '5', 'R': '6',
    }
    result = [first]
    prev = mapping.get(first, '0')
    for ch in name[1:]:
        code = mapping.get(ch, '0')
        if code != '0' and code != prev:
            result.append(code)
        prev = code
        if len(result) == 4:
            break
    while len(result) < 4:
        result.append('0')
    return ''.join(result)


# -- Scoring --
def _score_file(filename: str, keywords: list, target_extensions: list,
                modified_time: float, user_name: str = "",
                looking_for_folder: bool = False,
                is_folder: bool = False) -> int:
    """
    Score a file/folder match. Higher is better.

    CRITICAL RULE: If specific keywords exist and NONE match the name,
    score is 0. Type words filter, they do not substitute for name matches.
    """
    name_no_ext = os.path.splitext(filename)[0].lower()
    name_lower = filename.lower()
    ext = os.path.splitext(filename)[1].lower()
    score = 0
    name_words = name_no_ext.replace('_', ' ').replace('-', ' ').replace('.', ' ').split()

    if user_name and user_name.lower() in name_lower:
        score += 25

    # Separate specific keywords from type keywords
    specific_kws = [kw for kw in keywords if kw not in _TYPE_MAP]
    type_kws = [kw for kw in keywords if kw in _TYPE_MAP]

    # -- SPECIFIC KEYWORDS MUST MATCH --
    if specific_kws:
        matched_specific = 0
        for kw in specific_kws:
            kw_lower = kw.lower()
            kw_singular = kw_lower.rstrip('s') if kw_lower.endswith('s') and len(kw_lower) > 3 else kw_lower
            kw_score = 0

            if name_no_ext == kw_lower or name_no_ext == kw_singular:
                kw_score = 1000
            elif name_no_ext.startswith(kw_lower) or name_no_ext.startswith(kw_singular):
                # "trip" starts "trip_goa" (a word) and "tripoli" (a different word): only the first is strong.
                rest = name_no_ext[len(kw_lower if name_no_ext.startswith(kw_lower) else kw_singular):]
                kw_score = 500 if not rest or not rest[0].isalpha() else 120
            elif kw_lower in name_words or kw_singular in name_words:
                kw_score = 300
            elif HAS_FUZZY and len(name_no_ext) >= len(kw_lower) - 1:
                # partial_ratio scores a short name inside the keyword as 100 ("tr" in "trip"), so only fuzzy-match
                # names at least as long as the keyword.
                # Short words fuzz into anything ("trip" ~ "TRIM_2019"), so they need a near-exact match.
                ratio = _fuzz.partial_ratio(kw_lower, name_no_ext)
                if ratio >= (92 if len(kw_lower) <= 5 else 80):
                    kw_score = int(ratio * 2)
            if kw_score == 0 and len(kw_lower) >= 3:
                if _soundex(kw_lower) == _soundex(name_no_ext):
                    kw_score = 150
            if kw_score == 0 and len(kw_lower) >= 5 and (kw_lower in name_lower or kw_singular in name_lower):
                kw_score = 100          # inside a longer word ("budget" in "familybudget2025")

            if kw_score > 0:
                matched_specific += 1
                score += kw_score

        if matched_specific == 0:
            return 0

    # -- TYPE KEYWORDS: name match bonus + extension filter --
    for kw in type_kws:
        kw_lower = kw.lower()
        kw_singular = kw_lower.rstrip('s') if kw_lower.endswith('s') and len(kw_lower) > 3 else kw_lower
        if kw_lower in name_words or kw_singular in name_words:
            score += 200
        elif kw_lower in name_no_ext or kw_singular in name_no_ext:
            score += 100

    if type_kws and target_extensions:
        if ext in target_extensions:
            score += 50
        elif is_folder and not looking_for_folder:
            return 0                    # asked for a video, got a folder
        elif specific_kws and score >= 500:      # strong name match in another format ("resume.txt")
            score = max(0, score - 200)
        else:
            return 0

    # Pure type query (e.g. "open videos")
    if not specific_kws and type_kws and target_extensions:
        if ext in target_extensions:
            score += 20
        else:
            return 0

    if score == 0:
        return 0

    # -- FOLDER PRIORITY --
    if looking_for_folder:
        if is_folder:
            score += 500
        else:
            score = max(0, score - 200)

    # -- RECENCY --
    try:
        age_days = (time.time() - modified_time) / 86400
        if age_days < 7:
            score += 30
        elif age_days < 30:
            score += 15
    except Exception:
        pass

    return score


# -- FTS5 Index --
def _get_conn():
    conn = sqlite3.connect(FILE_INDEX_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_index_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                name_stem  TEXT NOT NULL,
                path       TEXT NOT NULL,
                ext        TEXT,
                size_kb    REAL,
                mtime      REAL,
                parent_dir TEXT,
                is_folder  INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_stem ON files(name_stem)")
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                name_stem,
                content='files',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                INSERT INTO files_fts(rowid, name_stem) VALUES (new.id, new.name_stem);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                INSERT INTO files_fts(files_fts, rowid, name_stem)
                VALUES ('delete', old.id, old.name_stem);
            END
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


_init_index_db()


def _is_index_stale():
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'last_build'"
            ).fetchone()
            if not row:
                return True
            ts = datetime.fromisoformat(row["value"])
            return datetime.now() - ts > STALE_AFTER
    except Exception:
        return True


def _index_count():
    try:
        with _get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    except Exception:
        return 0


def _walk_with_depth(root: str, max_depth: int):
    root = os.path.abspath(root)
    prefix = len(root.split(os.sep))
    for dirpath, dirnames, filenames in os.walk(root):
        depth = len(dirpath.split(os.sep)) - prefix
        if depth >= max_depth:
            dirnames.clear()
        yield dirpath, dirnames, filenames


def build_file_index(force: bool = False):
    """Scan user directories and populate FTS5 index."""
    if not force and not _is_index_stale():
        print(Fore.CYAN + "[FILES] Index fresh, skipping rebuild")
        return

    if not _build_lock.acquire(blocking=False):
        print(Fore.YELLOW + "[FILES] Index build already in progress")
        return

    try:
        t0 = time.time()
        print(Fore.CYAN + "[FILES] Building file index...")

        all_files = []
        scanned = 0

        for root in SEARCH_ROOTS:
            if scanned >= MAX_FILES:
                break
            try:
                for dirpath, dirnames, filenames in _walk_with_depth(root, MAX_DEPTH):
                    if scanned >= MAX_FILES:
                        break
                    dirnames[:] = [
                        d for d in dirnames
                        if not d.startswith('.') and d not in _SKIP_DIRS
                    ]
                    for dname in dirnames:
                        full = os.path.join(dirpath, dname)
                        stem = dname.lower()
                        all_files.append((
                            dname, stem, full, "folder", 0, 0, dirpath, 1
                        ))
                    if scanned and scanned % 4000 < len(filenames):
                        time.sleep(0.03)            # let the rest of the PC breathe during a big scan
                    for fname in filenames:
                        scanned += 1
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in _SKIP_EXTENSIONS:
                            continue
                        if fname.startswith('.') or fname.startswith('~$'):
                            continue
                        full = os.path.join(dirpath, fname)
                        stem = os.path.splitext(fname)[0].lower()
                        try:
                            mtime = os.path.getmtime(full)
                            size_kb = round(os.path.getsize(full) / 1024, 1)
                        except Exception:
                            mtime = 0
                            size_kb = 0
                        all_files.append((
                            fname, stem, full, ext, size_kb, mtime, dirpath, 0
                        ))
            except (PermissionError, OSError):
                continue

        now_iso = datetime.now().isoformat()
        with _get_conn() as conn:
            conn.execute("DELETE FROM files")
            conn.executemany(
                """INSERT INTO files
                   (name, name_stem, path, ext, size_kb, mtime, parent_dir, is_folder)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                all_files
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_build', ?)",
                (now_iso,)
            )
            conn.commit()

        elapsed = time.time() - t0
        print(Fore.GREEN + f"[FILES] Indexed {len(all_files)} items in {elapsed:.1f}s")

    except Exception as e:
        print(Fore.RED + f"[FILES] Index build failed: {e}")
    finally:
        _build_lock.release()


# -- Main Search --
def _get_search_limit(max_results):
    """Prefer explicit arg, else read from config, else default to 8."""
    if max_results is not None and max_results > 0:
        return max_results
    try:
        import config
        val = int(config.KEY.get("brain", {}).get("search_max_results", 8))
        return max(3, min(20, val))
    except Exception:
        return 8


def search_files(query: str, max_results: int = None, user_name: str = "") -> list:
    """Search user directories for files matching a natural language query.

    max_results: if None, reads from config.KEY['brain']['search_max_results'].
    """
    max_results = _get_search_limit(max_results)
    keywords, target_extensions, looking_for_folder = _extract_keywords(query)
    print(Fore.CYAN + f"[FILES] Query: '{query}' | KW: {keywords} | Folder: {looking_for_folder} | Limit: {max_results}")

    if not keywords:
        return []

    idx_count = _index_count()
    results = []

    if idx_count > 0:
        results = _search_fts(keywords, target_extensions, looking_for_folder,
                              max_results, user_name)
        if results is None:
            results = []
    else:
        print(Fore.YELLOW + "[FILES] Index empty, falling back to os.walk")
        results = _search_walk(keywords, target_extensions, looking_for_folder,
                               max_results, user_name)

    # If filename search found few results, also search file content
    if len(results) < max_results:
        try:
            from hands.file_content import search_content
            _specific = [kw for kw in keywords if kw not in _TYPE_MAP]
            if _specific:
                content_hits = search_content(" ".join(_specific),
                                              max_results - len(results))
                seen_paths = {r["path"] for r in results}
                for hit in content_hits:
                    if hit["path"] not in seen_paths:
                        seen_paths.add(hit["path"])
                        results.append({
                            "name": hit["name"],
                            "path": hit["path"],
                            "size_kb": 0,
                            "modified": "",
                            "ext": hit["ext"],  
                            "score": 50,
                            "snippet": hit.get("snippet", ""),
                        })
        except ImportError:
            pass
        except Exception as e:
            print(Fore.YELLOW + f"[FILES] Content search error: {e}")

    # Windows' own search index: files Seven's index skipped, and matches on the folder name
    # ("trip video" -> Videos\Goa trip\VID_0012.mp4).
    if len(results) < max_results or not results or results[0]["score"] < 500:
        results = _merge_windows_search(results, keywords, target_extensions, looking_for_folder, user_name)

    if target_extensions:               # "pdf", "video": every result must be that kind, whichever search found it
        results = [r for r in results if r["ext"] in target_extensions
                   or (looking_for_folder and r["ext"] == "folder")]
    _personal_boost(results)
    results.sort(key=lambda x: x["score"], reverse=True)
    if results:                         # "tnf" should not list NotNFKC.pl next to TNF.mp4
        top = results[0]["score"]
        results = [r for r in results if r["score"] >= top * 0.35]
    return results[:max_results]


CONFIDENT_SCORE = 250     # below this the top result is a guess: list the matches instead of opening one


def _merge_windows_search(results, keywords, target_extensions, looking_for_folder, user_name):
    try:
        from hands import windows_search
    except ImportError:
        return results
    specific = [k for k in keywords if k not in _TYPE_MAP]
    seen = {r["path"].lower() for r in results}
    for row in windows_search.search(specific, target_extensions or None):
        if row["path"].lower() in seen:
            continue
        seen.add(row["path"].lower())
        score = _score_file(row["name"], keywords, target_extensions, row["mtime"], user_name,
                            looking_for_folder, row["is_folder"])
        if score == 0 and row["folder_hit"] and (not target_extensions or row["ext"] in target_extensions):
            score = 250
        if score:
            results.append({"name": row["name"], "path": row["path"], "size_kb": 0, "ext": row["ext"] or "folder",
                            "modified": (datetime.fromtimestamp(row["mtime"]).strftime("%Y-%m-%d %H:%M")
                                         if row["mtime"] else ""),
                            "score": score})
    return results


_USER_PLACES = ("\\desktop\\", "\\documents\\", "\\downloads\\", "\\onedrive\\")


def _personal_boost(results):
    """Prefer what is the user's own: files they opened lately, files with their name, files in their folders."""
    try:
        from hands import windows_search
        recent = windows_search.recent_items()
        owner = windows_search.owner_names()
    except Exception:
        recent, owner = {}, []
    now = time.time()
    for r in results:
        name = r["name"].lower()
        opened = recent.get(name)
        if opened:
            age = (now - opened) / 86400
            r["score"] += 400 if age < 7 else 250 if age < 30 else 120
        if any(w in name for w in owner):
            r["score"] += 150
        if any(place in r["path"].lower() for place in _USER_PLACES):
            r["score"] += 40


_RECENT_RE = re.compile(r"\b(?:last|latest|newest|most recent|recent(?:ly)?)\b")


def latest_file(query: str):
    """"the last pdf I downloaded", "my latest screenshot", "the most recent video I saved".
    Returns the newest matching file as a result dict, or None."""
    q = query.lower()
    if not _RECENT_RE.search(q):
        return None
    exts = sorted({e for w in re.findall(r"[a-z]+", q) for e in _TYPE_MAP.get(w, [])})
    home = os.path.expanduser("~")
    if "download" in q:
        roots = [os.path.join(home, "Downloads")]
    elif "screenshot" in q:
        roots = [os.path.join(home, "Pictures", "Screenshots"), os.path.join(home, "OneDrive", "Pictures", "Screenshots")]
    elif "desktop" in q:
        roots = [os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Desktop")]
    elif "document" in q and not exts:
        roots = [os.path.join(home, "Documents")]
    else:
        roots = [os.path.join(home, d) for d in ("Downloads", "Desktop", "Documents", "Pictures", "Videos", "Music")]
    if not exts and "download" not in q:
        return None
    best = None
    for root in roots:
        try:
            with os.scandir(root) as entries:
                for e in entries:
                    if not e.is_file() or (exts and os.path.splitext(e.name)[1].lower() not in exts):
                        continue
                    if e.name.lower().endswith((".crdownload", ".part", ".tmp", ".ini")):
                        continue
                    mtime = e.stat().st_mtime
                    if best is None or mtime > best[0]:
                        best = (mtime, e.path, e.name)
        except OSError:
            continue
    if not best:
        return None
    return {"name": best[2], "path": best[1], "size_kb": 0, "ext": os.path.splitext(best[2])[1].lower(),
            "modified": datetime.fromtimestamp(best[0]).strftime("%Y-%m-%d %H:%M"), "score": 1000}


def _fts_escape(text: str) -> str:
    tokens = [t for t in text.lower().split() if t]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"' for t in tokens)


def _search_fts(keywords, target_extensions, looking_for_folder,
                max_results, user_name):
    """Search using FTS5 index."""
    try:
        specific_kws = [kw for kw in keywords if kw not in _TYPE_MAP and kw not in _FOLDER_WORDS]
        results = []
        seen = set()

        with _get_conn() as conn:
            # FTS search with specific keywords only
            if specific_kws:
                fts_query = _fts_escape(" ".join(specific_kws))
                rows = conn.execute(
                    """SELECT files.*, files_fts.rank AS fts_rank
                       FROM files_fts
                       JOIN files ON files.id = files_fts.rowid
                       WHERE files_fts MATCH ?
                       ORDER BY files_fts.rank
                       LIMIT 300""",
                    (fts_query,)
                ).fetchall()
            else:
                # Pure type query: get all files with matching extension
                if target_extensions:
                    placeholders = ",".join("?" * len(target_extensions))
                    rows = conn.execute(
                        f"SELECT * FROM files WHERE ext IN ({placeholders}) LIMIT 300",
                        target_extensions
                    ).fetchall()
                else:
                    return []

            for row in rows:
                if row["path"] in seen:
                    continue
                seen.add(row["path"])
                is_folder = bool(row["is_folder"])
                score = _score_file(
                    row["name"], keywords, target_extensions,
                    row["mtime"] or 0, user_name,
                    looking_for_folder, is_folder
                )
                if score == 0:
                    continue
                results.append({
                    "name":     row["name"],
                    "path":     row["path"],
                    "size_kb":  row["size_kb"] or 0,
                    "modified": (datetime.fromtimestamp(row["mtime"]).strftime("%Y-%m-%d %H:%M")
                                 if row["mtime"] else ""),
                    "ext":      row["ext"] or "folder",
                    "score":    score,
                })

            # LIKE fallback for partial matches
            if len(results) < max_results and specific_kws:
                like_q = f"%{specific_kws[0]}%"
                extra = conn.execute(
                    "SELECT * FROM files WHERE name_stem LIKE ? LIMIT 200",
                    (like_q,)
                ).fetchall()
                for row in extra:
                    if row["path"] in seen:
                        continue
                    seen.add(row["path"])
                    is_folder = bool(row["is_folder"])
                    score = _score_file(
                        row["name"], keywords, target_extensions,
                        row["mtime"] or 0, user_name,
                        looking_for_folder, is_folder
                    )
                    if score == 0:
                        continue
                    results.append({
                        "name":     row["name"],
                        "path":     row["path"],
                        "size_kb":  row["size_kb"] or 0,
                        "modified": (datetime.fromtimestamp(row["mtime"]).strftime("%Y-%m-%d %H:%M")
                                     if row["mtime"] else ""),
                        "ext":      row["ext"] or "folder",
                        "score":    score,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        print(Fore.CYAN + f"[FILES] FTS5 found {len(results)} matches")
        return results[:max_results]

    except Exception as e:
        print(Fore.YELLOW + f"[FILES] FTS5 search failed: {e}")
        return None


def _search_walk(keywords, target_extensions, looking_for_folder,
                 max_results, user_name):
    """Fallback os.walk search."""
    results = []
    seen = set()
    scanned = 0

    for root in SEARCH_ROOTS:
        if scanned >= MAX_FILES:
            break
        try:
            for dirpath, dirnames, filenames in _walk_with_depth(root, MAX_DEPTH):
                if scanned >= MAX_FILES:
                    break
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith('.') and d not in _SKIP_DIRS
                ]
                for dname in dirnames:
                    score = _score_file(
                        dname, keywords, [], 0, user_name,
                        looking_for_folder, True
                    )
                    if score == 0:
                        continue
                    full = os.path.join(dirpath, dname)
                    real = os.path.realpath(full)
                    if real in seen:
                        continue
                    seen.add(real)
                    results.append({
                        "name": dname, "path": full, "size_kb": 0,
                        "modified": "", "ext": "folder", "score": score,
                    })
                for fname in filenames:
                    scanned += 1
                    ext = os.path.splitext(fname)[1].lower()
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
                    score = _score_file(
                        fname, keywords, target_extensions,
                        mtime, user_name, looking_for_folder, False
                    )
                    if score == 0:
                        continue
                    seen.add(real)
                    try:
                        size_kb = round(os.path.getsize(full) / 1024, 1)
                        modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        size_kb = 0
                        modified = ""
                    results.append({
                        "name": fname, "path": full, "size_kb": size_kb,
                        "modified": modified, "ext": ext, "score": score,
                    })
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    print(Fore.CYAN + f"[FILES] Walk scanned {scanned}, found {len(results)}")
    return results[:max_results]


# -- Open File / Folder --
def _visible_windows() -> set:
    try:
        import win32gui
        out = set()
        win32gui.EnumWindows(lambda h, _: (out.add(h) if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h)
                                           else None) or True, None)
        return out
    except Exception:
        return set()


def _bring_forward(path: str, before: set = frozenset(), timeout: float = 6.0) -> None:
    """Players and viewers can take a few seconds to show a window, and Windows may open it behind Seven. Wait for
    the window that names the file (or the first new window, since some players title themselves only by app name),
    then bring it to the front."""
    try:
        import win32gui
        from hands.windows import _is_seven_window, _safe_foreground
    except Exception:
        return
    name = os.path.basename(path.rstrip("\\/")).lower()
    stem = os.path.splitext(name)[0]
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if title and not _is_seven_window(hwnd):
                    if name in title or (len(stem) > 2 and stem in title):
                        found.insert(0, hwnd)
                    elif before and hwnd not in before:
                        found.append(hwnd)
            return True
        win32gui.EnumWindows(_cb, None)
        if found:
            try:
                _safe_foreground(found[0])
            except Exception:
                pass
            return
        time.sleep(0.25)


def open_file(path: str) -> bool:
    if os.environ.get("SEVEN_TEST") == "1":          # tests never open the user's files
        return os.path.exists(path)
    try:
        before = _visible_windows()
        if os.path.isdir(path):
            subprocess.Popen(f'explorer "{path}"', shell=True)
        else:
            os.startfile(path)
        threading.Thread(target=_bring_forward, args=(path, before), daemon=True).start()
        print(Fore.GREEN + f"[FILES] Opened: {path}")
        return True
    except Exception as e:
        print(Fore.RED + f"[FILES] Open failed {path}: {e}")
        return False


# -- Response Formatters --
def format_results_for_speech(results: list, query: str,
                               opened: bool = False) -> str:
    """Natural human-like speech. Never speaks filenames aloud."""
    import random

    if not results:
        return random.choice([
            f"I could not find anything for {query}. Want me to check somewhere else?",
            f"Nothing turned up for {query}. Try being more specific?",
            f"Hmm, no luck finding {query}. Do you know roughly where it is?",
        ])

    count = len(results)

    if count == 1:
        if opened:
            return random.choice([
                "Got it, opened it for you.",
                "Found it. Opening now.",
                "Here you go, opening it up.",
                "Alright, it is open.",
            ])
        return random.choice([
            "I found one match. Want me to open it?",
            "Got one result. Opening it now.",
        ])

    if opened:
        top = results[0]
        where = os.path.basename(os.path.dirname(top.get("path", ""))) or "your PC"
        name = top.get("name", "")
        label = name if len(name) <= 48 else "the best match"
        others = count - 1
        return (f"Opened {label} from {where}. "
                f"{others} other match{'es are' if others != 1 else ' is'} in the chat if it's not the one.")

    return random.choice([
        f"I found {count} matches for {query}. Which one did you want?",
        f"Got {count} results. Take a look in the chat and tell me which one.",
        f"There are {count} matches. Check the list and let me know.",
    ])


def format_results_for_chat(results: list, query: str) -> dict:
    return {
        "type":    "file_search",
        "query":   query,
        "count":   len(results),
        "results": [
            {
                "name": r["name"], "path": r["path"],
                "size_kb": r["size_kb"], "modified": r["modified"],
                "ext": r["ext"],
            }
            for r in results
        ],
        "message": (f"Found {len(results)} file(s) matching '{query}'"
                    if results else f"No files found for '{query}'"),
    }