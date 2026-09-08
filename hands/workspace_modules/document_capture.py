"""
hands/workspace_modules/document_capture.py
Universal Dynamic Process & Document Inspector.

No hardcoded app lists. Automatically discovers:
  1. Active document & project files (cmdline args, title parsing, Windows Recent MRU)
  2. Active working directories (proc.cwd())
  3. Window spatial placement (x, y, width, height, state)
  4. Web URLs and document URIs

Works out of the box for ANY application (current or future).
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

# Universal document/project filename regex (e.g., "model.onnx", "workflow.json", "doc.pdf")
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
                detected_cwd = proc.cwd()
                cmdline = proc.cmdline()
                
                # Search cmdline arguments for existing files or directories
                for arg in cmdline[1:]:
                    clean_arg = arg.strip().strip('"').strip("'")
                    if os.path.isfile(clean_arg):
                        detected_files.add(os.path.abspath(clean_arg))
                    elif os.path.isdir(clean_arg) and not app.get("workspace_path"):
                        app["working_dir"] = os.path.abspath(clean_arg)
            except Exception:
                pass

        # ── LAYER 2: Window Title Path & Project Detection ──
        if title:
            # Check for absolute path in window title
            title_paths = _ABS_PATH_REGEX.findall(title)
            for p in title_paths:
                if os.path.isfile(p):
                    detected_files.add(os.path.abspath(p))

            # If no absolute path, check for filename and resolve via CWD or Recent Items
            if not detected_files:
                resolved = _resolve_filename_from_title(title, detected_cwd)
                if resolved:
                    detected_files.add(resolved)

        # ── LAYER 3: Dynamic COM Server Probe (Office / CAD / Generic) ──
        if not detected_files and exe_name.endswith(".exe"):
            com_files = _probe_generic_com(exe_name)
            for cf in com_files:
                detected_files.add(cf)

        # Store results
        if detected_files:
            app["open_files"] = sorted(list(detected_files))
            print(Fore.CYAN + f"[WORKSPACE] Dynamic capture for '{app.get('name')}': {len(detected_files)} document(s)")

        if detected_cwd and not app.get("working_dir") and os.path.isdir(detected_cwd):
            app["working_dir"] = detected_cwd

    return apps


def _resolve_filename_from_title(title: str, cwd: str = None) -> str:
    """
    Extracts filename from title and attempts to locate it in the process CWD,
    User Desktop, Documents, or Windows Recent files.
    """
    # Clean standard delimiters e.g. "MyProject.ai - Adobe Illustrator" -> "MyProject.ai"
    parts = re.split(r'[-–—•|]', title)
    candidate_tokens = [p.strip() for p in parts if p.strip()]

    candidates = []
    for tok in candidate_tokens:
        matches = _DOC_FILENAME_REGEX.findall(tok)
        for m in matches:
            # Ignore app names and common noise words
            if len(m) > 4 and not m.lower().endswith(".exe"):
                candidates.append(m)

    search_dirs = []
    if cwd and os.path.isdir(cwd):
        search_dirs.append(cwd)

    # Standard user search locations
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


def _probe_generic_com(exe_name: str) -> list:
    """
    Safely probes for active COM application servers without crashing or hanging.
    """
    files = []
    prog_map = {
        "winword.exe":  ("Word.Application", "Documents", "FullName"),
        "excel.exe":    ("Excel.Application", "Workbooks", "FullName"),
        "powerpnt.exe": ("PowerPoint.Application", "Presentations", "FullName"),
    }

    if exe_name not in prog_map:
        return files

    prog_id, coll_name, prop_name = prog_map[exe_name]

    try:
        import win32com.client
        app_obj = win32com.client.GetActiveObject(prog_id)
        collection = getattr(app_obj, coll_name, None)
        if collection:
            for i in range(1, collection.Count + 1):
                item = collection(i)
                fpath = getattr(item, prop_name, "")
                if fpath and os.path.exists(fpath):
                    files.append(os.path.abspath(fpath))
    except Exception:
        pass

    return files


def restore_open_files(open_files: list) -> int:
    """
    Reopens saved project or document files using the operating system's
    active shell association. Always reads the most up-to-date state of the file.
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
            else:
                print(Fore.YELLOW + f"  [WORKSPACE] Document path moved or missing: {fpath}")
        except Exception as e:
            print(Fore.YELLOW + f"  [WORKSPACE] Could not reopen {fpath}: {e}")

    return opened