"""
trigger_modules/app_launcher.py
Robust application launcher with hard-coded Windows path resolution.
Falls back through: hands.core → AppOpener → os.startfile.
"""
import os
import subprocess


def open_app_robust(app_name: str) -> bool:
    """
    Launch an app by name.
    Handles apps installed outside PATH via hardcoded Windows paths.
    """
    name_clean       = app_name.lower().strip()
    local_appdata    = os.environ.get('LOCALAPPDATA', '')
    program_files    = os.environ.get('PROGRAMFILES',      'C:\\Program Files')
    program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')

    # 1. Visual Studio Code
    if name_clean in ["vscode", "vs code", "visual studio code", "code"]:
        for path in [
            os.path.join(local_appdata, "Programs", "Microsoft VS Code", "Code.exe"),
            os.path.join(program_files, "Microsoft VS Code", "Code.exe"),
            os.path.join(program_files_x86, "Microsoft VS Code", "Code.exe"),
        ]:
            if os.path.exists(path):
                subprocess.Popen([path], start_new_session=True)
                print(f"[TRIGGER DAEMON] Opened VS Code: {path}")
                return True

    # 2. Google Chrome
    if name_clean in ["chrome", "google chrome"]:
        for path in [
            os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
        ]:
            if os.path.exists(path):
                subprocess.Popen([path], start_new_session=True)
                print(f"[TRIGGER DAEMON] Opened Chrome: {path}")
                return True

    # 3. Microsoft Edge
    if name_clean in ["edge", "microsoft edge"]:
        for path in [
            os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(program_files,     "Microsoft", "Edge", "Application", "msedge.exe"),
        ]:
            if os.path.exists(path):
                subprocess.Popen([path], start_new_session=True)
                print(f"[TRIGGER DAEMON] Opened Edge: {path}")
                return True

    # Fallback: hands.core.open_app
    try:
        from hands.core import open_app
        open_app(app_name)
        print(f"[TRIGGER DAEMON] Opened via hands.core: {app_name}")
        return True
    except Exception:
        pass

    # Fallback: AppOpener
    try:
        import AppOpener
        AppOpener.open(app_name)
        print(f"[TRIGGER DAEMON] Opened via AppOpener: {app_name}")
        return True
    except Exception:
        pass

    # Fallback: os.startfile
    try:
        os.startfile(app_name)
        print(f"[TRIGGER DAEMON] Opened via os.startfile: {app_name}")
        return True
    except Exception:
        pass

    return False