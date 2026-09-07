"""
hands/workspace_modules/document_capture.py
Captures open document paths from Office and creative applications.

Uses COM automation for Microsoft Office (Word, Excel, PowerPoint).
Uses window title parsing for creative apps (Premiere Pro, Photoshop, etc.).

On restore, files are reopened via os.startfile() which reads the
current file contents from disk — so if the user saved changes after
the workspace was scanned, the updated file opens automatically.
"""
import os
import re
from colorama import Fore


def capture_open_documents(apps: list) -> list:
    """
    Enrich app configs with open file paths.
    Modifies apps in-place and returns them.
    """
    for app in apps:
        app_type = (app.get("type") or "").lower()
        exe_path = (app.get("exe_path") or "").lower()
        exe_name = os.path.basename(exe_path).lower() if exe_path else ""
        title    = app.get("name", "")

        open_files = []

        # ── Microsoft Office (COM automation) ────────────────────────
        if exe_name in ("winword.exe", "excel.exe", "powerpnt.exe"):
            open_files = _capture_office_documents(exe_name)

        # ── Adobe Creative Suite (window title parsing) ──────────────
        elif exe_name in ("adobe premiere pro.exe", "premiere pro.exe"):
            open_files = _parse_title_for_file(title, [".prproj"])

        elif exe_name in ("photoshop.exe", "adobe photoshop.exe"):
            open_files = _parse_title_for_file(title, [".psd", ".psb", ".tiff", ".png", ".jpg"])

        elif exe_name in ("illustrator.exe", "adobe illustrator.exe"):
            open_files = _parse_title_for_file(title, [".ai", ".eps", ".svg"])

        elif exe_name in ("afterfx.exe", "after effects.exe"):
            open_files = _parse_title_for_file(title, [".aep"])

        elif exe_name in ("indesign.exe", "adobe indesign.exe"):
            open_files = _parse_title_for_file(title, [".indd", ".idml"])

        # ── Notepad++ (window title parsing) ─────────────────────────
        elif exe_name in ("notepad++.exe",):
            open_files = _parse_title_for_file(title, [".txt", ".py", ".js", ".html", ".css", ".json", ".md", ".xml", ".cpp", ".c", ".java", ".rs"])

        # ── VS Code (already handled by enrichment.py) ───────────────
        # Skip — workspace_path already captured

        # ── Generic: try to extract file path from window title ──────
        elif not open_files:
            open_files = _generic_title_file_extract(title)

        if open_files:
            app["open_files"] = open_files

    return apps


def _capture_office_documents(exe_name: str) -> list:
    """
    Use COM automation to read open document paths from Office apps.
    Returns list of absolute file paths.
    """
    files = []
    try:
        import win32com.client

        if exe_name == "winword.exe":
            try:
                word = win32com.client.GetActiveObject("Word.Application")
                for i in range(1, word.Documents.Count + 1):
                    doc = word.Documents(i)
                    path = doc.FullName
                    if path and os.path.exists(path):
                        files.append(path)
            except Exception:
                pass

        elif exe_name == "excel.exe":
            try:
                excel = win32com.client.GetActiveObject("Excel.Application")
                for i in range(1, excel.Workbooks.Count + 1):
                    wb = excel.Workbooks(i)
                    path = wb.FullName
                    if path and os.path.exists(path):
                        files.append(path)
            except Exception:
                pass

        elif exe_name == "powerpnt.exe":
            try:
                ppt = win32com.client.GetActiveObject("PowerPoint.Application")
                for i in range(1, ppt.Presentations.Count + 1):
                    pres = ppt.Presentations(i)
                    path = pres.FullName
                    if path and os.path.exists(path):
                        files.append(path)
            except Exception:
                pass

        if files:
            print(Fore.CYAN + f"[WORKSPACE] Office COM: "
                  f"{len(files)} documents from {exe_name}")

    except ImportError:
        print(Fore.YELLOW + "[WORKSPACE] pywin32 not available — "
              "Office documents not captured")
    except Exception as e:
        print(Fore.YELLOW + f"[WORKSPACE] Office COM error: {e}")

    return files


def _parse_title_for_file(title: str, extensions: list) -> list:
    """
    Extract file path from window title using known extensions.
    Most creative apps put the filename in the title:
      "MyProject.prproj - Adobe Premiere Pro"
      "Untitled-1 @ 100% (RGB/8#) - Photoshop"
    """
    if not title:
        return []

    files = []
    for ext in extensions:
        # Pattern: "filename.ext" or "filename.ext - App Name"
        pattern = re.compile(
            r'([A-Za-z]:\\[^\s\*\?\"<>|]+' + re.escape(ext) + r')',
            re.IGNORECASE
        )
        matches = pattern.findall(title)
        for m in matches:
            if os.path.exists(m):
                files.append(m)

    # Also try just the filename part (before " - ")
    if not files and " - " in title:
        name_part = title.split(" - ")[0].strip()
        for ext in extensions:
            if name_part.lower().endswith(ext.lower()):
                # We have a filename but no full path
                # Store as filename-only — restore will search common locations
                files.append(name_part)

    return files


def _generic_title_file_extract(title: str) -> list:
    """
    Last resort: try to find any file path in the window title.
    Matches patterns like "C:\Users\...\file.ext".
    """
    if not title:
        return []

    pattern = re.compile(
        r'([A-Za-z]:\\[^\s\*\?\"<>|]+\.[a-zA-Z0-9]{1,6})'
    )
    matches = pattern.findall(title)
    return [m for m in matches if os.path.exists(m)]


def restore_open_files(open_files: list) -> int:
    """
    Reopen saved document files.
    Uses os.startfile() which opens with the default associated app
    and reads CURRENT file contents from disk (not stale snapshot).

    Returns count of files successfully opened.
    """
    if not open_files:
        return 0

    opened = 0
    for fpath in open_files:
        try:
            if os.path.exists(fpath):
                os.startfile(fpath)
                opened += 1
                print(Fore.GREEN + f"  [WORKSPACE] Reopened: {fpath}")
            else:
                print(Fore.YELLOW + f"  [WORKSPACE] File not found: {fpath}")
        except Exception as e:
            print(Fore.YELLOW + f"  [WORKSPACE] Could not reopen {fpath}: {e}")

    return opened