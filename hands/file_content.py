"""
hands/file_content.py
Seven - Content-Based File Search
Version: 1.0

Extracts text from PDF and DOCX files and indexes into FTS5.
Searches file content alongside filenames for deeper matching.

DEPENDENCIES:
    pip install pypdf python-docx

PUBLIC API:
    build_content_index(force) -> None
    search_content(query, max_results) -> list
    get_content_stats() -> dict
"""

import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from colorama import Fore

try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception:
    _SEVEN_DATA = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "seven_data"
    )

os.makedirs(_SEVEN_DATA, exist_ok=True)
CONTENT_DB = os.path.join(_SEVEN_DATA, "content_index.db")

MAX_FILE_SIZE_MB = 20
MAX_PAGES_PDF = 15
MAX_PARAS_DOCX = 100
STALE_AFTER = timedelta(hours=2)
_build_lock = threading.Lock()

# Supported extensions for content extraction
CONTENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".rtf"}


def _get_conn():
    conn = sqlite3.connect(CONTENT_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL,
                ext       TEXT,
                text      TEXT,
                indexed_at REAL
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                text,
                content='content',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content BEGIN
                INSERT INTO content_fts(rowid, text) VALUES (new.id, new.text);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content BEGIN
                INSERT INTO content_fts(content_fts, rowid, text)
                VALUES ('delete', old.id, old.text);
            END
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


_init_db()


def _is_stale():
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


def _extract_pdf(path: str) -> str:
    """Extract text from PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        pages = min(len(reader.pages), MAX_PAGES_PDF)
        text_parts = []
        for i in range(pages):
            try:
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception:
                continue
        return " ".join(text_parts)[:50000]
    except Exception as e:
        print(Fore.YELLOW + f"[CONTENT] PDF extract failed {path}: {e}")
        return ""


def _extract_docx(path: str) -> str:
    """Extract text from DOCX file."""
    try:
        from docx import Document
        doc = Document(path)
        text_parts = []
        for i, para in enumerate(doc.paragraphs):
            if i >= MAX_PARAS_DOCX:
                break
            if para.text.strip():
                text_parts.append(para.text)
        return " ".join(text_parts)[:50000]
    except Exception as e:
        print(Fore.YELLOW + f"[CONTENT] DOCX extract failed {path}: {e}")
        return ""


def _extract_txt(path: str) -> str:
    """Extract text from plain text files."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(50000)
    except Exception:
        return ""


def _extract_content(path: str, ext: str) -> str:
    """Route to the right extractor based on extension."""
    ext = ext.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    elif ext in (".docx", ".doc"):
        return _extract_docx(path)
    elif ext in (".txt", ".md", ".csv", ".rtf"):
        return _extract_txt(path)
    return ""


def build_content_index(force: bool = False):
    """
    Scan indexed files and extract text content from PDFs and DOCX files.
    Runs in background. Takes 1-5 minutes for large libraries.
    """
    if not force and not _is_stale():
        print(Fore.CYAN + "[CONTENT] Index fresh, skipping rebuild")
        return

    if not _build_lock.acquire(blocking=False):
        print(Fore.YELLOW + "[CONTENT] Build already in progress")
        return

    try:
        t0 = time.time()
        print(Fore.CYAN + "[CONTENT] Building content index...")

        # Get all indexable files from the file index
        try:
            from hands.files import FILE_INDEX_DB
            fconn = sqlite3.connect(FILE_INDEX_DB, timeout=10)
            fconn.row_factory = sqlite3.Row
            files = fconn.execute(
                "SELECT path, name, ext FROM files WHERE is_folder = 0"
            ).fetchall()
            fconn.close()
        except Exception as e:
            print(Fore.YELLOW + f"[CONTENT] Cannot read file index: {e}")
            return

        # Filter to content-extractable files
        candidates = []
        for f in files:
            ext = (f["ext"] or "").lower()
            if ext not in CONTENT_EXTENSIONS:
                continue
            path = f["path"]
            try:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                if size_mb > MAX_FILE_SIZE_MB:
                    continue
            except Exception:
                continue
            candidates.append((path, f["name"], ext))

        print(Fore.CYAN + f"[CONTENT] {len(candidates)} files to extract")

        indexed = 0
        failed = 0

        with _get_conn() as conn:
            for path, name, ext in candidates:
                # Skip if already indexed and file not modified
                existing = conn.execute(
                    "SELECT indexed_at FROM content WHERE file_path = ?",
                    (path,)
                ).fetchone()
                if existing and not force:
                    try:
                        mtime = os.path.getmtime(path)
                        if mtime < existing["indexed_at"]:
                            continue
                    except Exception:
                        pass

                text = _extract_content(path, ext)
                if not text or len(text.strip()) < 20:
                    continue

                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO content
                           (file_path, file_name, ext, text, indexed_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (path, name, ext, text, time.time())
                    )
                    indexed += 1
                except Exception:
                    failed += 1

                if indexed % 50 == 0:
                    conn.commit()
                    print(Fore.CYAN + f"[CONTENT] Progress: {indexed} files indexed")

            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_build', ?)",
                (datetime.now().isoformat(),)
            )
            conn.commit()

        elapsed = time.time() - t0
        print(Fore.GREEN + f"[CONTENT] Indexed {indexed} files in {elapsed:.1f}s ({failed} failed)")

    except Exception as e:
        print(Fore.RED + f"[CONTENT] Build failed: {e}")
    finally:
        _build_lock.release()


def search_content(query: str, max_results: int = 5) -> list:
    """
    Search file contents for a query.
    Returns list of dicts with file_path, file_name, snippet, score.
    """
    if not query or len(query.strip()) < 2:
        return []

    try:
        tokens = [t for t in query.lower().split() if len(t) > 1]
        if not tokens:
            return []
        fts_query = " ".join(f'"{t}"' for t in tokens)

        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT content.file_path, content.file_name, content.ext,
                          snippet(content_fts, 0, '>>>', '<<<', '...', 32) AS snippet,
                          content_fts.rank
                   FROM content_fts
                   JOIN content ON content.id = content_fts.rowid
                   WHERE content_fts MATCH ?
                   ORDER BY content_fts.rank
                   LIMIT ?""",
                (fts_query, max_results * 2)
            ).fetchall()

            results = []
            seen = set()
            for row in rows:
                if row["file_path"] in seen:
                    continue
                seen.add(row["file_path"])
                if not os.path.exists(row["file_path"]):
                    continue
                results.append({
                    "name": row["file_name"],
                    "path": row["file_path"],
                    "ext": row["ext"] or "",
                    "snippet": (row["snippet"] or "")[:200],
                    "score": abs(row["rank"] or 0),
                    "source": "content",
                })

            return results[:max_results]

    except Exception as e:
        print(Fore.YELLOW + f"[CONTENT] Search failed: {e}")
        return []


def get_content_stats() -> dict:
    """Return content index statistics."""
    try:
        with _get_conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'last_build'"
            ).fetchone()
            return {
                "indexed_files": count,
                "last_build": row["value"] if row else "never",
            }
    except Exception:
        return {"indexed_files": 0, "last_build": "never"}