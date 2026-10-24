"""
hands/windows_search.py

Seven's file search uses three signals from Windows itself, on top of its own file index (hands/files.py):

    Windows Search index   every indexed file on the PC, matched by name or by the folder it is in, so
                           "my trip video" finds Videos\\Goa trip\\VID_0012.mp4
    Recent items           %APPDATA%\\Microsoft\\Windows\\Recent: files the user actually opened lately, the best
                           guess for "my resume"
    The Windows account    the user's real name from their Windows account, so their own resume beats a friend's

All three are read-only and local. Windows Search is a COM call (Search.CollatorDSO); when the service is off, the
search returns nothing and Seven's own index still answers.
"""

import os
import threading
import time
from typing import Dict, List, Optional

_SKIP_SEGMENTS = ("\\node_modules\\", "\\.git\\", "\\site-packages\\", "\\appdata\\", "\\$recycle.bin\\",
                  "\\windows\\", "\\program files", "\\programdata\\", "\\.venv\\", "\\venv\\", "\\dist\\",
                  "\\build\\", "\\__pycache__\\", "\\.next\\", "\\cache\\")
_KIND = {"video": "video", "music": "music", "picture": "picture", "document": "document"}
_lock = threading.Lock()


def _quote(text: str) -> str:
    return text.replace("'", "''").replace("%", "").replace("[", "").replace("]", "")


def search(keywords: List[str], extensions: Optional[List[str]] = None, limit: int = 40) -> List[Dict]:
    """Files whose name or folder contains every keyword. [{name, path, mtime, ext, is_folder, folder_hit}]"""
    keywords = [k for k in keywords if len(k) >= 2][:4]
    if not keywords and not extensions:
        return []
    clauses = [f"(System.FileName LIKE '%{_quote(k)}%' OR System.ItemFolderPathDisplay LIKE '%{_quote(k)}%')"
               for k in keywords]
    if extensions:
        exts = " OR ".join(f"System.FileExtension = '{_quote(e)}'" for e in extensions)
        clauses.append(f"({exts})")
    sql = (f"SELECT TOP {limit * 3} System.ItemPathDisplay, System.DateModified, System.FileExtension "
           f"FROM SystemIndex WHERE SCOPE='file:' AND {' AND '.join(clauses)} ORDER BY System.DateModified DESC")
    rows = []
    try:
        import pythoncom
        import win32com.client
        with _lock:
            pythoncom.CoInitialize()
            try:
                conn = win32com.client.Dispatch("ADODB.Connection")
                conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
                rs = win32com.client.Dispatch("ADODB.Recordset")
                rs.Open(sql, conn)
                while not rs.EOF and len(rows) < limit:
                    path = rs.Fields.Item("System.ItemPathDisplay").Value or ""
                    low = path.lower()
                    if path and not any(seg in low for seg in _SKIP_SEGMENTS):
                        mod = rs.Fields.Item("System.DateModified").Value
                        ext = (rs.Fields.Item("System.FileExtension").Value or "").lower()
                        name = os.path.basename(path)
                        folder = os.path.basename(os.path.dirname(path)).lower()
                        rows.append({"name": name, "path": path, "ext": ext, "is_folder": not ext,
                                     "mtime": mod.timestamp() if hasattr(mod, "timestamp") else 0,
                                     "folder_hit": any(k in folder for k in keywords)})
                    rs.MoveNext()
                rs.Close()
                conn.Close()
            finally:
                pythoncom.CoUninitialize()
    except Exception as exc:
        print(f"[FILES] Windows Search unavailable: {exc}")
    return rows


_recent_cache = {"at": 0.0, "items": {}}


def recent_items() -> Dict[str, float]:
    """{file name (lower): when it was last opened} from Windows Recent items, cached for a minute."""
    if time.time() - _recent_cache["at"] < 60:
        return _recent_cache["items"]
    items = {}
    folder = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent")
    try:
        with os.scandir(folder) as entries:
            for e in entries:
                if e.name.lower().endswith(".lnk"):
                    items[e.name[:-4].lower()] = e.stat().st_mtime
    except OSError:
        pass
    _recent_cache.update(at=time.time(), items=items)
    return items


_owner = None


def owner_names() -> List[str]:
    """Words of the Windows account's display name and user folder ("manikanta", "cheruku")."""
    global _owner
    if _owner is None:
        words = set()
        try:
            import win32api
            words.update(win32api.GetUserNameEx(3).lower().split())         # NameDisplay
        except Exception:
            pass
        words.update(os.path.basename(os.path.expanduser("~")).lower().replace(".", " ").split())
        words.update((os.environ.get("USERNAME") or "").lower().split())
        _owner = sorted(w for w in words if len(w) >= 3 and w.isalpha())
    return _owner
