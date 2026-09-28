"""
hands/files.py
Seven - Smart File Search and Open
Version: 3.0 - FTS5 indexed search with os.walk fallback.

INDEX:
    seven_data/file_index.db (SQLite + FTS5)
    Built at startup in background. Refreshed every 30 minutes.
    Falls back to os.walk if index not yet ready.

SCOPE:
    Desktop, Documents, Downloads, Pictures, Videos, Music, OneDrive.
    Never system directories.

PUBLIC API (unchanged from v2):
    search_files(query, max_results, user_name) -> list
    open_file(path) -> bool
    format_results_for_speech(results, query, opened) -> str
    format_results_for_chat(results, query) -> dict
    build_file_index(force) -> None
"""

import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta
from colorama import Fore

# ── Database ────────────────────────────────────────────────────────
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

MAX_DEPTH = 5
MAX_FILES = 15000
STALE_AFTER = timedelta(minutes=30)
_build_lock = threading.Lock()

# ── Search Roots ────────────────────────────────────────────────────
SEARCH_ROOTS = []


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
    print(Fore.CYAN + f"[FILES] Search roots: {len(SEARCH_ROOTS)} directories")


_build_search_roots()

# ── Skip Lists ──────────────────────────────────────────────────────
_SKIP_DIRS = {
    '$RECYCLE.BIN', 'System Volume Information', 'node_modules',
    '.git', '__pycache__', 'Windows', 'System32', 'SysWOW64',
    'WinSxS', 'Temp', 'temp', '.vs', 'dist', 'build',
    'venv', '.venv', 'env', 'site-packages',
}

_SKIP_EXTENSIONS = {
    '.dll', '.sys', '.exe', '.msi', '.tmp', '.log', '.ini',
    '.lnk', '.url', '.db', '.sqlite', '.cache', '.pyc',
    '.pyo', '.class', '.o', '.obj', '.lib', '.pdb',
}

# ── Keyword Extraction ──────────────────────────────────────────────
_STOP_WORDS = {
    "open", "show", "find", "my", "the", "a", "an", "to", "me",
    "please", "can", "you", "your", "and", "or", "all", "any",
    "some", "have", "do", "i", "is", "are", "how", "many", "what",
    "where", "which", "get", "bring", "pull", "up", "that", "this",
    "it", "from", "in", "on", "at", "for", "with", "tell", "give",
    "look", "see", "check", "boss", "friend", "friends",
}

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
}


def _extract_keywords(query: str) -> tuple:
    words = query.lower().split()
    looking_for_folder = any(w in words for w in ["folder", "directory", "dir"])
    target_extensions = []
    for word in words:
        if word in _TYPE_MAP and _TYPE_MAP[word]:
            target_extensions.extend(_TYPE_MAP[word])
    keywords = [w for w in words if w not in _STOP_WORDS and len(w) > 1]
    if not keywords:
        keywords = [w for w in words if len(w) > 1]
    return keywords, list(set(target_extensions)), looking_for_folder


def _score_file(filename: str, keywords: list, target_extensions: list,
                modified_time: float, user_name: str = "") -> int:
    name_no_ext = os.path.splitext(filename)[0].lower()
    name_lower = filename.lower()
    ext = os.path.splitext(filename)[1].lower()
    score = 0
    name_words = name_no_ext.replace('_', ' ').replace('-', ' ').replace('.', ' ').split()

    if user_name and user_name.lower() in name_lower:
        score += 25

    matched_any = False
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in _TYPE_MAP and kw_lower not in ("resume", "cv", "edit"):
            continue
        if kw_lower in name_words:
            score += 30
            matched_any = True
        elif name_no_ext == kw_lower:
            score += 100
            matched_any = True
        elif name_no_ext.startswith(kw_lower):
            score += 50
            matched_any = True
        elif kw_lower in name_lower:
            score += 10
            matched_any = True

    if not matched_any:
        return 0
    if target_extensions and ext in target_extensions:
        score += 15
    try:
        age_days = (time.time() - modified_time) / 86400
        if age_days < 7:
            score += 20
        elif age_days < 30:
            score += 10
    except Exception:
        pass
    return score


# ── FTS5 Index ──────────────────────────────────────────────────────
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
    """
    Scan user directories and populate FTS5 index.
    Called at startup in background thread.
    """
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


# ── Main Search ─────────────────────────────────────────────────────
def search_files(query: str, max_results: int = 8, user_name: str = "") -> list:
    """
    Search user directories for files matching a natural language query.
    Uses FTS5 index if available, falls back to os.walk.
    """
    keywords, target_extensions, looking_for_folder = _extract_keywords(query)
    print(Fore.CYAN + f"[FILES] Query: '{query}' | Keywords: {keywords}")

    if not keywords:
        return []

    idx_count = _index_count()
    if idx_count > 0:
        results = _search_fts(keywords, target_extensions, looking_for_folder,
                              max_results, user_name)
        if results is not None:
            return results

    print(Fore.YELLOW + "[FILES] Index empty, falling back to os.walk")
    return _search_walk(keywords, target_extensions, looking_for_folder,
                        max_results, user_name)


def _fts_escape(text: str) -> str:
    tokens = [t for t in text.lower().split() if t]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"' for t in tokens)


def _search_fts(keywords, target_extensions, looking_for_folder,
                max_results, user_name):
    """Search using FTS5 index. Returns list or None on failure."""
    try:
        fts_query = _fts_escape(" ".join(keywords))
        results = []
        seen = set()

        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT files.*, files_fts.rank AS fts_rank
                   FROM files_fts
                   JOIN files ON files.id = files_fts.rowid
                   WHERE files_fts MATCH ?
                   ORDER BY files_fts.rank
                   LIMIT 200""",
                (fts_query,)
            ).fetchall()

            for row in rows:
                if row["path"] in seen:
                    continue
                seen.add(row["path"])
                if looking_for_folder and not row["is_folder"]:
                    continue

                score = _score_file(
                    row["name"], keywords, target_extensions,
                    row["mtime"] or 0, user_name
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

            if len(results) < max_results:
                like_q = f"%{keywords[0]}%"
                extra = conn.execute(
                    "SELECT * FROM files WHERE name_stem LIKE ? LIMIT 100",
                    (like_q,)
                ).fetchall()
                for row in extra:
                    if row["path"] in seen:
                        continue
                    seen.add(row["path"])
                    score = _score_file(
                        row["name"], keywords, target_extensions,
                        row["mtime"] or 0, user_name
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
    """Fallback os.walk search (identical logic to v2)."""
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
                    score = _score_file(fname, keywords, target_extensions,
                                        mtime, user_name)
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


# ── Open File / Folder ──────────────────────────────────────────────
def open_file(path: str) -> bool:
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


# ── Response Formatters ─────────────────────────────────────────────
def format_results_for_speech(results: list, query: str,
                               opened: bool = False) -> str:
    if not results:
        return f"Nothing found for '{query}'."
    count = len(results)
    top = results[0]["name"]
    if count == 1:
        return f"Found it. Opened {top}." if opened else f"One match: {top}."
    if count <= 3:
        names = ", ".join(r["name"] for r in results)
        if opened:
            return f"Found {count} matches. Opened the top one: {top}."
        return f"Found {count}: {names}. Which one?"
    if opened:
        return f"Found {count} matches. Opened the best one: {top}."
    return f"Found {count} files for '{query}'. Check the chat."


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