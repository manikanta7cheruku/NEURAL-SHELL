"""
hands/workspace_modules/document_capture.py
Universal Dynamic Process & Document Inspector.
Thread-safe, non-blocking, guarded against Windows process locks.
"""

import os
import sys
import re
from colorama import Fore

try:
    import psutil
    import win32gui
    import win32process
    import win32con
except ImportError:
    pass


# Universal file path regex (absolute paths on Windows)
_ABS_PATH_REGEX = re.compile(r'([a-zA-Z]:\\[^<>:"/\\|?*\r\n]+\.[a-zA-Z0-9_-]{1,12})')

# Universal document/project filename regex
_DOC_FILENAME_REGEX = re.compile(r'([\w\-. ]+\.[a-zA-Z0-9_-]{1,12})')

# System processes to never parse for document files
_SYSTEM_EXES = {
    "explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
    "textinputhost.exe", "runtimebroker.exe", "applicationframehost.exe",
    "taskmgr.exe", "systemsettings.exe", "seven.exe", "electron.exe",
    "python.exe", "pythonw.exe"
}


def capture_open_documents(apps: list) -> list:
    """
    Universal Dynamic Inspector: Enriches any app config in-place with its
    live file, project, directory, and document metadata.
    Guarded to NEVER block or hang the Python main thread.
    """
    for app in apps:
        exe_path = (app.get("exe_path") or "").lower()
        exe_name = os.path.basename(exe_path).lower() if exe_path else ""
        title    = (app.get("name") or (app.get("window") or {}).get("title") or "")
        pid      = app.get("pid")

        if exe_name in _SYSTEM_EXES or not exe_name:
            continue

        detected_files = set()
        detected_cwd   = None

        # ── LAYER 1: Dynamic Process Command-Line Inspection ──
        if pid:
            try:
                proc = psutil.Process(pid)
                with proc.oneshot():
                    # Safely extract cwd without hanging on elevated/UWP processes
                    try:
                        detected_cwd = proc.cwd()
                    except (psutil.AccessDenied, psutil.NoSuchProcess, Exception):
                        detected_cwd = None

                    # Safely extract cmdline
                    try:
                        cmdline = proc.cmdline()
                    except (psutil.AccessDenied, psutil.NoSuchProcess, Exception):
                        cmdline = []

                    for arg in cmdline[1:]:
                        if arg.startswith("--profile-directory="):
                            app["profile_dir"] = arg.split("=", 1)[1].strip('"').strip("'")
                            continue

                        clean_arg = arg.strip().strip('"').strip("'")
                        if os.path.isfile(clean_arg):
                            detected_files.add(os.path.abspath(clean_arg))
                        elif os.path.isdir(clean_arg) and not app.get("workspace_path"):
                            app["working_dir"] = os.path.abspath(clean_arg)
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass

        # ── LAYER 2: Window Title Path & Project Detection ──
        if title:
            title_paths = _ABS_PATH_REGEX.findall(title)
            for p in title_paths:
                if os.path.isfile(p):
                    detected_files.add(os.path.abspath(p))

            if not detected_files:
                resolved = _resolve_filename_from_title(title, detected_cwd)
                if resolved:
                    detected_files.add(resolved)

            # ── LAYER 2b: Office document detection ──
            # Office apps use titles like "Report.docx - Word" or "Budget - Excel"
            if not detected_files and exe_name in (
                "winword.exe", "excel.exe", "powerpnt.exe"
            ):
                office_file = _resolve_office_document(title, exe_name)
                if office_file:
                    detected_files.add(office_file)

        # Store results
        if detected_files:
            app["open_files"] = sorted(list(detected_files))

        if detected_cwd and not app.get("working_dir") and os.path.isdir(detected_cwd):
            app["working_dir"] = detected_cwd

    return apps


def _resolve_filename_from_title(title: str, cwd: str = None) -> str:
    """
    Extracts filename from title and attempts to locate it in CWD or standard User folders.
    """
    parts = re.split(r'[-–—•|]', title)
    candidate_tokens = [p.strip() for p in parts if p.strip()]

    candidates = []
    for tok in candidate_tokens:
        matches = _DOC_FILENAME_REGEX.findall(tok)
        for m in matches:
            if len(m) > 4 and not m.lower().endswith(".exe"):
                candidates.append(m)

    search_dirs = []
    if cwd and os.path.isdir(cwd):
        search_dirs.append(cwd)

    user_home = os.path.expanduser("~")
    search_dirs.extend([
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Downloads"),
    ])

    for fname in candidates:
        for sdir in search_dirs:
            full_path = os.path.join(sdir, fname)
            if os.path.isfile(full_path):
                return os.path.abspath(full_path)

    return None


def restore_open_files(open_files: list) -> int:
    """
    Reopens saved project or document files using shell association.
    """
    if not open_files:
        return 0

    opened = 0
    for fpath in open_files:
        try:
            if os.path.exists(fpath):
                os.startfile(fpath)
                opened += 1
                print(Fore.GREEN + f"  [WORKSPACE] Reopened live document: {fpath}")
        except Exception as e:
            print(Fore.YELLOW + f"  [WORKSPACE] Could not reopen {fpath}: {e}")

    return opened

def _resolve_office_document(title: str, exe_name: str) -> str:
    """
    Resolve Office document file path from window title.
    Handles: "Report.docx - Word", "Budget.xlsx - Excel", "Slides - PowerPoint"
    """
    import glob

    # Extract filename from title (before " - Word/Excel/PowerPoint")
    parts = re.split(r'\s+[-–—]\s+', title)
    if not parts:
        return None

    filename = parts[0].strip()
    if not filename or len(filename) < 3:
        return None

    # Add extension if missing based on app type
    ext_map = {
        "winword.exe": [".docx", ".doc"],
        "excel.exe": [".xlsx", ".xls", ".csv"],
        "powerpnt.exe": [".pptx", ".ppt"],
    }
    extensions = ext_map.get(exe_name, [".docx", ".xlsx", ".pptx"])

    # Check if filename already has an extension
    has_ext = any(filename.lower().endswith(ext) for ext in extensions)

    # Search directories
    user_home = os.path.expanduser("~")
    search_dirs = [
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "OneDrive"),
        os.path.join(user_home, "OneDrive", "Documents"),
    ]

    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue

        if has_ext:
            full_path = os.path.join(sdir, filename)
            if os.path.isfile(full_path):
                return os.path.abspath(full_path)
        else:
            for ext in extensions:
                full_path = os.path.join(sdir, filename + ext)
                if os.path.isfile(full_path):
                    return os.path.abspath(full_path)

        # Glob search for partial matches
        for ext in extensions:
            pattern = os.path.join(sdir, f"*{filename}*{ext}")
            matches = glob.glob(pattern)
            if matches:
                return os.path.abspath(matches[0])

    return None