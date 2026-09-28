"""
=============================================================================
hands/app_discovery.py

Universal Windows app discovery + fuzzy launch system.

DISCOVERS APPS FROM:
    1. Start Menu shortcuts (%ProgramData% + %AppData%)
    2. Registry App Paths (HKLM + HKCU)
    3. PATH environment variable (executable scan)
    4. UWP / Microsoft Store apps (via PowerShell Get-StartApps)
    5. Desktop shortcuts (Public + User desktop)

STORES IN:
    seven_data/app_index.db (SQLite + FTS5 for fuzzy search)

USAGE:
    from hands.app_discovery import discover_apps, search_apps, get_app

    discover_apps()               # rescan (5-8 seconds, called at startup)
    hits = search_apps("chrome")  # returns [{name, launch, exe, source}, ...]
    app  = get_app("chrome")      # returns single exact match or None

DESIGN:
    - Rescan cached for 7 days. Manual rescan via discover_apps(force=True).
    - FTS5 for sub-10ms fuzzy queries at any index size.
    - Launch commands stored ready-to-execute (UWP uses shell:AppsFolder\\...).
    - No aliases. No user config. Discovery is authoritative.
=============================================================================
"""

import os
import sys
import sqlite3
import subprocess
import time
import json
import threading
from datetime import datetime, timedelta
from colorama import Fore

# ─────────────────────────────────────────────────────────────────────
# DATABASE PATH
# ─────────────────────────────────────────────────────────────────────
try:
    from seven_paths import paths as _paths
    _SEVEN_DATA = _paths._seven_data
except Exception:
    _SEVEN_DATA = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "seven_data"
    )

os.makedirs(_SEVEN_DATA, exist_ok=True)
APP_INDEX_DB = os.path.join(_SEVEN_DATA, "app_index.db")

_CREATE_NO_WINDOW = 0x08000000

# Rescan interval — 7 days
STALE_AFTER = timedelta(days=7)

# Global lock for concurrent scans
_scan_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────
# EXCLUDE LIST — junk that clutters Start Menu but nobody launches
# ─────────────────────────────────────────────────────────────────────
_EXCLUDE_NAME_PATTERNS = {
    "uninstall", "readme", "release notes", "documentation",
    "license", "help", "manual", "changelog", "modify",
    "repair", "user guide", "getting started", "tutorial",
    "eula", "credits", "about ",
}

_EXCLUDE_EXACT = {
    "cmd", "regedit", "notepad",  # keep these? actually keep them
}
_EXCLUDE_EXACT = set()  # empty — let user launch anything


# ─────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────
def _get_conn():
    conn = sqlite3.connect(APP_INDEX_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    """Create tables + FTS5 virtual table."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                name_lower     TEXT NOT NULL,
                launch_command TEXT NOT NULL,
                exe_name       TEXT,
                exe_path       TEXT,
                source         TEXT NOT NULL,
                icon_path      TEXT,
                indexed_at     TEXT NOT NULL,
                UNIQUE(name_lower, source)
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_apps_name  ON apps(name_lower)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_apps_exe   ON apps(exe_name)")

        # FTS5 virtual table for fuzzy search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS apps_fts USING fts5(
                name_lower,
                content='apps',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)

        # Triggers to keep FTS in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS apps_ai AFTER INSERT ON apps BEGIN
                INSERT INTO apps_fts(rowid, name_lower) VALUES (new.id, new.name_lower);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS apps_ad AFTER DELETE ON apps BEGIN
                INSERT INTO apps_fts(apps_fts, rowid, name_lower) VALUES('delete', old.id, old.name_lower);
            END
        """)

        # Metadata table (last scan timestamp)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        conn.commit()


_init_db()


# ─────────────────────────────────────────────────────────────────────
# NAME CLEANING
# ─────────────────────────────────────────────────────────────────────
def _clean_name(raw: str) -> str:
    """Normalize app display name."""
    n = raw.strip()
    # Remove version suffixes like " 2023", " v1.2"
    # But keep names like "Windows 11" intact — only strip after last known separator
    n = n.replace(".lnk", "").replace(".url", "")
    return n.strip()


def _should_exclude(name: str) -> bool:
    """Filter Start Menu junk."""
    lower = name.lower()
    if lower in _EXCLUDE_EXACT:
        return True
    for pat in _EXCLUDE_NAME_PATTERNS:
        if pat in lower:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────
# DISCOVERY: START MENU
# ─────────────────────────────────────────────────────────────────────
def _resolve_shortcut(lnk_path: str):
    """Resolve .lnk file to target executable using win32com."""
    try:
        import pythoncom
        from win32com.client import Dispatch
        pythoncom.CoInitialize()
        try:
            shell    = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            target   = shortcut.Targetpath
            args     = shortcut.Arguments
            return target, args
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        return None, None


def _scan_start_menu():
    """Scan Start Menu directories for .lnk shortcuts."""
    results = []
    roots = [
        os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                     "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("APPDATA", ""),
                     "Microsoft", "Windows", "Start Menu", "Programs"),
    ]

    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                if not fname.lower().endswith(".lnk"):
                    continue
                lnk_full = os.path.join(dirpath, fname)
                display  = _clean_name(fname[:-4])

                if _should_exclude(display):
                    continue

                target, args = _resolve_shortcut(lnk_full)
                if not target or not target.lower().endswith(".exe"):
                    # UWP shortcuts or non-exe — launch via the .lnk itself
                    launch   = lnk_full
                    exe_name = ""
                    exe_path = ""
                else:
                    if args:
                        launch = f'"{target}" {args}'
                    else:
                        launch = f'"{target}"'
                    exe_name = os.path.basename(target).lower()
                    exe_path = target

                results.append({
                    "name":     display,
                    "launch":   launch,
                    "exe_name": exe_name,
                    "exe_path": exe_path,
                    "source":   "start_menu",
                    "icon":     lnk_full,
                })
    return results


# ─────────────────────────────────────────────────────────────────────
# DISCOVERY: REGISTRY APP PATHS
# ─────────────────────────────────────────────────────────────────────
def _scan_registry():
    """Read App Paths from registry — Windows uses these for `start <app>`."""
    results = []
    try:
        import winreg
    except ImportError:
        return results

    hives = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]

    for hive, subkey in hives:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                        i += 1
                    except OSError:
                        break

                    if not sub.lower().endswith(".exe"):
                        continue

                    try:
                        with winreg.OpenKey(key, sub) as appkey:
                            try:
                                target = winreg.QueryValueEx(appkey, "")[0]
                            except Exception:
                                target = ""

                            if not target or not os.path.isfile(target):
                                continue

                            display = _clean_name(sub[:-4])  # strip .exe
                            if _should_exclude(display):
                                continue

                            results.append({
                                "name":     display,
                                "launch":   f'"{target}"',
                                "exe_name": sub.lower(),
                                "exe_path": target,
                                "source":   "registry",
                                "icon":     target,
                            })
                    except Exception:
                        continue
        except Exception:
            continue

    return results


# ─────────────────────────────────────────────────────────────────────
# DISCOVERY: PATH
# ─────────────────────────────────────────────────────────────────────
def _scan_path():
    """Scan directories in PATH for .exe files."""
    results  = []
    path_env = os.environ.get("PATH", "")
    seen_exe = set()

    for pdir in path_env.split(os.pathsep):
        pdir = pdir.strip().strip('"')
        if not pdir or not os.path.isdir(pdir):
            continue

        try:
            for fname in os.listdir(pdir):
                if not fname.lower().endswith(".exe"):
                    continue
                lower_exe = fname.lower()
                if lower_exe in seen_exe:
                    continue
                seen_exe.add(lower_exe)

                full = os.path.join(pdir, fname)
                if not os.path.isfile(full):
                    continue

                display = _clean_name(fname[:-4])
                if _should_exclude(display):
                    continue

                results.append({
                    "name":     display,
                    "launch":   f'"{full}"',
                    "exe_name": lower_exe,
                    "exe_path": full,
                    "source":   "path",
                    "icon":     full,
                })
        except (PermissionError, OSError):
            continue

    return results


# ─────────────────────────────────────────────────────────────────────
# DISCOVERY: UWP / STORE APPS
# ─────────────────────────────────────────────────────────────────────
def _scan_uwp():
    """
    Use PowerShell Get-StartApps to enumerate UWP and traditional apps.
    Returns list with proper shell:AppsFolder launch commands.
    """
    results = []
    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            "Get-StartApps | ConvertTo-Json -Compress"
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=_CREATE_NO_WINDOW,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return results

        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            data = [data]

        for entry in data:
            name  = entry.get("Name", "").strip()
            appid = entry.get("AppID", "").strip()
            if not name or not appid:
                continue
            if _should_exclude(name):
                continue

            # UWP AppIDs contain '!'. Traditional apps use paths.
            if "!" in appid:
                # UWP — launch via shell:AppsFolder
                launch = f'explorer.exe shell:AppsFolder\\{appid}'
                exe_name = ""
                exe_path = ""
                source   = "uwp"
            else:
                # Traditional exe — Get-StartApps returned the direct path
                if os.path.isfile(appid):
                    launch   = f'"{appid}"'
                    exe_name = os.path.basename(appid).lower()
                    exe_path = appid
                    source   = "start_apps"
                else:
                    launch = f'explorer.exe shell:AppsFolder\\{appid}'
                    exe_name = ""
                    exe_path = ""
                    source   = "uwp"

            results.append({
                "name":     _clean_name(name),
                "launch":   launch,
                "exe_name": exe_name,
                "exe_path": exe_path,
                "source":   source,
                "icon":     exe_path,
            })
    except subprocess.TimeoutExpired:
        print(Fore.YELLOW + "[APP_DISCOVERY] UWP scan timed out")
    except Exception as e:
        print(Fore.YELLOW + f"[APP_DISCOVERY] UWP scan failed: {e}")

    return results


# ─────────────────────────────────────────────────────────────────────
# DISCOVERY: DESKTOP SHORTCUTS
# ─────────────────────────────────────────────────────────────────────
def _scan_desktop():
    """Scan Public + User Desktop for shortcuts."""
    results = []
    roots = [
        os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
    ]

    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            for fname in os.listdir(root):
                low = fname.lower()
                if not low.endswith(".lnk"):
                    continue
                lnk_full = os.path.join(root, fname)
                display  = _clean_name(fname[:-4])

                if _should_exclude(display):
                    continue

                target, args = _resolve_shortcut(lnk_full)
                if not target or not target.lower().endswith(".exe"):
                    launch   = lnk_full
                    exe_name = ""
                    exe_path = ""
                else:
                    launch = f'"{target}" {args}' if args else f'"{target}"'
                    exe_name = os.path.basename(target).lower()
                    exe_path = target

                results.append({
                    "name":     display,
                    "launch":   launch,
                    "exe_name": exe_name,
                    "exe_path": exe_path,
                    "source":   "desktop",
                    "icon":     lnk_full,
                })
        except (PermissionError, OSError):
            continue

    return results


# ─────────────────────────────────────────────────────────────────────
# INDEX MANAGEMENT
# ─────────────────────────────────────────────────────────────────────
def _last_scan_time():
    try:
        with _get_conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", ("last_scan",)).fetchone()
            if row:
                return datetime.fromisoformat(row["value"])
    except Exception:
        pass
    return None


def _is_stale():
    ts = _last_scan_time()
    if ts is None:
        return True
    return datetime.now() - ts > STALE_AFTER


def _write_index(all_apps):
    """Wipe and rewrite entire app index."""
    now_iso = datetime.now().isoformat()
    inserted = 0
    with _get_conn() as conn:
        conn.execute("DELETE FROM apps")

        for app in all_apps:
            name       = app["name"]
            name_lower = name.lower()
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO apps
                       (name, name_lower, launch_command, exe_name, exe_path,
                        source, icon_path, indexed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name,
                        name_lower,
                        app["launch"],
                        app.get("exe_name", ""),
                        app.get("exe_path", ""),
                        app["source"],
                        app.get("icon", ""),
                        now_iso,
                    )
                )
                inserted += conn.total_changes  # rough count
            except Exception:
                continue

        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ("last_scan", now_iso)
        )
        conn.commit()
    return inserted


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────
def discover_apps(force: bool = False, background: bool = False) -> int:
    """
    Scan all sources and rebuild the app index.

    Args:
        force:      If False, skip if index is fresh (<7 days).
        background: If True, run in a daemon thread and return 0 immediately.

    Returns:
        Number of apps indexed (0 if background=True).
    """
    if background:
        threading.Thread(
            target=discover_apps,
            args=(force, False),
            daemon=True,
            name="SevenAppDiscovery",
        ).start()
        return 0

    if not force and not _is_stale():
        print(Fore.CYAN + "[APP_DISCOVERY] Index fresh, skipping scan")
        return 0

    if not _scan_lock.acquire(blocking=False):
        print(Fore.YELLOW + "[APP_DISCOVERY] Scan already in progress")
        return 0

    try:
        t0 = time.time()
        print(Fore.CYAN + "[APP_DISCOVERY] Starting full scan...")

        all_apps = []
        all_apps.extend(_scan_start_menu())
        all_apps.extend(_scan_registry())
        all_apps.extend(_scan_uwp())
        all_apps.extend(_scan_desktop())
        all_apps.extend(_scan_path())

        # Deduplicate by (name_lower, exe_name) preferring earliest source
        seen = {}
        priority = {
            "start_menu": 0, "start_apps": 1, "registry": 2,
            "desktop":    3, "uwp":        4, "path":     5,
        }
        for app in all_apps:
            key = (app["name"].lower(), app.get("exe_name", ""))
            if key not in seen:
                seen[key] = app
            else:
                if priority.get(app["source"], 9) < priority.get(seen[key]["source"], 9):
                    seen[key] = app

        deduped = list(seen.values())
        _write_index(deduped)

        elapsed = time.time() - t0
        print(Fore.GREEN + f"[APP_DISCOVERY] Indexed {len(deduped)} apps in {elapsed:.1f}s")
        return len(deduped)

    except Exception as e:
        print(Fore.RED + f"[APP_DISCOVERY] Scan failed: {e}")
        import traceback; traceback.print_exc()
        return 0
    finally:
        _scan_lock.release()


def _fts_escape(text: str) -> str:
    """Escape FTS5 query — wrap each token to survive special chars."""
    # Split on whitespace, wrap each token in double quotes
    tokens = [t for t in text.lower().split() if t]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"' for t in tokens)


def search_apps(query: str, limit: int = 8) -> list:
    """
    Fuzzy search for apps matching a natural query.

    Returns a scored list of dicts:
        [{name, launch, exe_name, exe_path, source, score}, ...]

    Scoring:
        Exact match (case-insensitive)   → 1000
        Starts-with match                → 500
        Contains match                   → 200
        FTS5 relevance rank              → variable
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    hits = []
    seen_names = set()

    try:
        with _get_conn() as conn:
            # 1. Exact match (highest priority)
            for row in conn.execute(
                "SELECT * FROM apps WHERE name_lower = ? LIMIT 3", (q,)
            ):
                if row["name_lower"] in seen_names:
                    continue
                seen_names.add(row["name_lower"])
                hits.append(_row_to_hit(row, 1000))

            # 2. Starts-with match
            for row in conn.execute(
                "SELECT * FROM apps WHERE name_lower LIKE ? ORDER BY LENGTH(name_lower) ASC LIMIT 10",
                (q + "%",)
            ):
                if row["name_lower"] in seen_names:
                    continue
                seen_names.add(row["name_lower"])
                hits.append(_row_to_hit(row, 500))

            # 3. Exe name match (e.g. "chrome" -> chrome.exe)
            exe_target = f"{q}.exe"
            for row in conn.execute(
                "SELECT * FROM apps WHERE exe_name = ? LIMIT 5",
                (exe_target,)
            ):
                if row["name_lower"] in seen_names:
                    continue
                seen_names.add(row["name_lower"])
                hits.append(_row_to_hit(row, 800))

            # 4. Contains match (for compound queries)
            if len(hits) < limit:
                for row in conn.execute(
                    "SELECT * FROM apps WHERE name_lower LIKE ? LIMIT 15",
                    (f"%{q}%",)
                ):
                    if row["name_lower"] in seen_names:
                        continue
                    seen_names.add(row["name_lower"])
                    hits.append(_row_to_hit(row, 200))

            # 5. FTS5 fuzzy fallback
            if len(hits) < limit:
                try:
                    fts_q = _fts_escape(q)
                    for row in conn.execute(
                        """SELECT apps.*, apps_fts.rank AS fts_rank
                           FROM apps_fts
                           JOIN apps ON apps.id = apps_fts.rowid
                           WHERE apps_fts MATCH ?
                           ORDER BY apps_fts.rank LIMIT 10""",
                        (fts_q,)
                    ):
                        if row["name_lower"] in seen_names:
                            continue
                        seen_names.add(row["name_lower"])
                        # FTS rank is negative; convert to positive score
                        fts_score = max(10, int(100 + (row["fts_rank"] or 0) * 10))
                        hits.append(_row_to_hit(row, fts_score))
                except Exception as fe:
                    print(Fore.YELLOW + f"[APP_DISCOVERY] FTS search failed: {fe}")

    except Exception as e:
        print(Fore.RED + f"[APP_DISCOVERY] Search failed: {e}")
        return []

    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


def _row_to_hit(row, score):
    return {
        "name":     row["name"],
        "launch":   row["launch_command"],
        "exe_name": row["exe_name"] or "",
        "exe_path": row["exe_path"] or "",
        "source":   row["source"],
        "score":    score,
    }


def get_app(name: str):
    """
    Return the single best-matching app, or None if no clear winner.
    Used when caller wants a decision, not a list.
    """
    hits = search_apps(name, limit=3)
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    # Clear winner if top score is significantly higher
    if hits[0]["score"] >= hits[1]["score"] + 200:
        return hits[0]
    # Ambiguous — return None and let caller disambiguate
    return None


def get_all_apps(limit: int = 500):
    """Return all indexed apps. Used by admin UI."""
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM apps ORDER BY name_lower LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_hit(r, 0) for r in rows]
    except Exception:
        return []


def get_index_stats():
    """Return current index statistics."""
    try:
        with _get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
            by_source = {}
            for row in conn.execute("SELECT source, COUNT(*) as c FROM apps GROUP BY source"):
                by_source[row["source"]] = row["c"]
            last = _last_scan_time()
            return {
                "total":     total,
                "by_source": by_source,
                "last_scan": last.isoformat() if last else None,
                "stale":     _is_stale(),
            }
    except Exception:
        return {"total": 0, "by_source": {}, "last_scan": None, "stale": True}