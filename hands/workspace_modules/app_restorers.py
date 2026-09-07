"""
hands/workspace_modules/app_restorers.py
Individual app-type restore functions.
Each handles one category: browser, editor, terminal, etc.
"""
import os
import subprocess
import time
from colorama import Fore

from hands.workspace_modules.helpers import (
    find_chrome_exe, find_chrome_profile_dir
)


def restore_one(cfg):
    """Dispatch to the correct restorer based on app type."""
    t    = (cfg.get("type") or "").lower()
    name = cfg.get("name", "?")
    try:
        if t in ("chrome", "edge", "brave", "firefox"):
            _restore_browser(cfg)
        elif t == "vscode":
            _restore_vscode(cfg)
        elif t == "explorer":
            _restore_explorer(cfg)
        elif t in ("notepad", "notepad++", "sublime"):
            _restore_editor(cfg)
        elif t in ("excel", "word", "powerpoint"):
            _restore_office(cfg)
        elif t == "uwp":
            _restore_uwp(cfg)
        elif t in ("powershell", "cmd", "terminal"):
            _restore_terminal(cfg)
        else:
            _restore_generic(cfg)
        # Reopen saved documents (Office files, Premiere projects, etc.)
        open_files = cfg.get("open_files", [])
        if open_files:
            import time as _t
            _t.sleep(1.5)  # Wait for app to finish launching
            try:
                from hands.workspace_modules.document_capture import restore_open_files
                _opened = restore_open_files(open_files)
                if _opened > 0:
                    print(Fore.GREEN + f"  [+] {name} (+ {_opened} files)")
            except Exception as _fe:
                print(Fore.YELLOW + f"  [~] {name} file restore: {_fe}")

        print(Fore.GREEN + f"  [+] {name}")
    except Exception as e:
        print(Fore.RED + f"  [-] {name}: {e}")


def _restore_browser(cfg):
    """
    Restore browser tabs with deduplication.

    Chrome automatically restores "last session" tabs on launch.
    Seven ALSO saves tabs. Result: duplicates.

    Fix (Option A+C):
      1. Check if Chrome is already running for this profile
      2. If yes → session restore already happened → diff tabs
      3. If no → launch Chrome → wait 3s for session restore → diff → open missing
      4. Only open tabs that are genuinely missing
    """
    tabs         = cfg.get("tabs", [])
    urls         = [t["url"] for t in tabs
                    if t.get("url", "").startswith("http")]
    profile_name = cfg.get("profile_name", "")
    chrome_exe   = find_chrome_exe()

    if not urls:
        return

    if not chrome_exe:
        for url in urls:
            subprocess.Popen(f'start chrome "{url}"', shell=True)
            time.sleep(0.3)
        return

    import os as _os
    from hands.workspace_modules.url_matching import normalize_url

    chrome_base = _os.path.join(
        _os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data"
    )
    profile_dir = find_chrome_profile_dir(chrome_base, profile_name)

    # Check if Chrome is already running
    chrome_already_running = False
    try:
        import psutil as _ps
        for _p in _ps.process_iter(['name']):
            try:
                if _p.info['name'] and 'chrome' in _p.info['name'].lower():
                    chrome_already_running = True
                    break
            except Exception:
                pass
    except Exception:
        pass

    # Launch Chrome if not running
    if not chrome_already_running:
        if profile_dir:
            subprocess.Popen(
                [chrome_exe, f"--profile-directory={profile_dir}", urls[0]]
            )
        else:
            subprocess.Popen([chrome_exe, urls[0]])

        # Wait for Chrome to finish session restore (reopens last tabs)
        time.sleep(3.5)

    # Now diff: query what's actually open vs what we want
    missing_urls = list(urls)  # start with all, remove already-open

    try:
        from backend.routes.chrome import get_tabs_by_profile
        open_tabs = get_tabs_by_profile()

        if open_tabs:
            # Build set of currently open URLs (normalized)
            open_url_set = set()
            for _prof, _tabs in open_tabs.items():
                # If profile specified, only check that profile
                if profile_name and _prof.lower() != profile_name.lower():
                    continue
                for _t in _tabs:
                    _u = _t.get("url", "")
                    if _u:
                        open_url_set.add(normalize_url(_u))

            # Filter to only truly missing URLs
            missing_urls = [
                u for u in urls
                if normalize_url(u) not in open_url_set
            ]

            skipped = len(urls) - len(missing_urls)
            if skipped > 0:
                print(Fore.CYAN + f"[WORKSPACE] Chrome dedup: "
                      f"{skipped} tabs already open (session restore), "
                      f"{len(missing_urls)} missing")

    except Exception as _dedup_err:
        print(Fore.YELLOW + f"[WORKSPACE] Chrome dedup check failed: "
              f"{_dedup_err} — opening all tabs")
        missing_urls = list(urls)

    if not missing_urls:
        print(Fore.GREEN + f"[WORKSPACE] Chrome '{profile_name}': "
              f"all tabs already open")
        return

    # Open only missing tabs
    for url in missing_urls:
        if profile_dir:
            subprocess.Popen(
                [chrome_exe, f"--profile-directory={profile_dir}", url]
            )
        else:
            subprocess.Popen([chrome_exe, url])
        time.sleep(0.15)  # minimal delay to avoid Chrome merge


def _restore_vscode(cfg):
    ws  = cfg.get("workspace_path", "")
    exe = cfg.get("exe_path", "")

    if ws and os.path.exists(ws):
        try:
            subprocess.Popen(["code", ws])
            return
        except Exception:
            pass

    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe])
            return
        except Exception:
            pass

    try:
        subprocess.Popen("code", shell=True)
    except Exception:
        pass


def _restore_explorer(cfg):
    folder = cfg.get("folder_path", "")
    name   = cfg.get("name", "")

    if folder and os.path.exists(folder):
        subprocess.Popen(["explorer", folder])
        return

    if name:
        clean = name
        for prefix in ("File Explorer: ", "File Explorer — ",
                       "File Explorer - "):
            if name.startswith(prefix):
                clean = name[len(prefix):]
                break
        if " - File Explorer" in clean:
            clean = clean.replace(" - File Explorer", "").strip()
        if os.path.exists(clean):
            subprocess.Popen(["explorer", clean])
            return

    subprocess.Popen(["explorer"])


def _restore_editor(cfg):
    fp  = cfg.get("file_path", "")
    exe = cfg.get("exe_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    elif exe and os.path.exists(exe):
        subprocess.Popen([exe])
    else:
        _restore_generic(cfg)


def _restore_office(cfg):
    fp = cfg.get("file_path", "")
    if fp and os.path.exists(fp):
        os.startfile(fp)
    else:
        _restore_generic(cfg)


def _restore_uwp(cfg):
    proto = cfg.get("protocol", "")
    if proto:
        try:
            os.startfile(proto)
            return
        except Exception:
            pass
    _restore_generic(cfg)


def _restore_terminal(cfg):
    cwd      = cfg.get("working_dir", "")
    app_type = (cfg.get("type") or "").lower()
    exe      = "powershell" if app_type in ("powershell", "terminal") \
               else "cmd"
    flags    = subprocess.CREATE_NEW_CONSOLE
    if cwd and os.path.exists(cwd):
        subprocess.Popen([exe], cwd=cwd, creationflags=flags)
    else:
        subprocess.Popen([exe], creationflags=flags)


def _restore_generic(cfg):
    exe  = cfg.get("exe_path", "")
    name = cfg.get("name", "")

    if exe and os.path.exists(exe):
        try:
            subprocess.Popen([exe])
            return
        except Exception:
            pass

    clean = name.split(" - ")[-1].strip() if " - " in name else name
    if not clean:
        return

    try:
        from hands.core import open_app
        open_app(clean)
        return
    except Exception:
        pass

    try:
        import AppOpener
        AppOpener.open(clean)
    except Exception:
        pass