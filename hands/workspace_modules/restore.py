"""
hands/workspace_modules/restore.py
Smart workspace restore — only opens what is genuinely missing.
"""
import os
import threading
from colorama import Fore

from hands.workspace_modules.scanner import scan_current
from hands.workspace_modules.url_matching import url_matches, normalize_url
from hands.workspace_modules.chrome_utils import (
    get_open_chrome_profiles,
    get_open_chrome_tabs,
    browser_profile_matches_window,
)
from hands.workspace_modules.app_restorers import restore_one
from hands.workspace_modules.filters import is_seven_process


_restore_in_progress = threading.Lock()


def should_restore(cfg: dict) -> bool:
    """Only skip Seven's own processes."""
    exe  = (cfg.get("exe_path") or "").lower()
    name = (cfg.get("name") or "").strip()

    if not name and not exe:
        return False

    exe_name = os.path.basename(exe) if exe else ""
    if exe_name in ("electron.exe", "python.exe",
                    "pythonw.exe", "seven.exe"):
        seven_markers = (
            "mk-projects\\seven",
            "\\seven\\electron",
            "\\seven\\python",
            "program files\\seven",
            "appdata\\local\\seven",
        )
        if any(marker in exe for marker in seven_markers):
            return False

    return True


def smart_restore(apps_config):
    """
    Open only apps/tabs that are not already running.
    Returns (opened_count, already_open_count).
    """
    if not apps_config:
        return 0, 0

    if not _restore_in_progress.acquire(blocking=True, timeout=30):
        print(Fore.YELLOW + "[WORKSPACE] Restore lock timeout — skipping")
        return 0, 0

    try:
        import concurrent.futures

        from hands.workspace_modules.chrome_utils import get_open_chrome_tabs_per_profile

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as _pool:
            _prof_future = _pool.submit(get_open_chrome_profiles)
            _tabs_future = _pool.submit(get_open_chrome_tabs)
            _per_prof_future = _pool.submit(get_open_chrome_tabs_per_profile)

            try:
                current = scan_current()
            except Exception:
                current = []

            try:
                _extra_profiles = _prof_future.result(timeout=3)
            except Exception:
                _extra_profiles = set()

            try:
                open_chrome_urls, open_chrome_domains = \
                    _tabs_future.result(timeout=3)
            except Exception:
                open_chrome_urls, open_chrome_domains = set(), set()

            try:
                per_profile_urls = _per_prof_future.result(timeout=3)
            except Exception:
                per_profile_urls = {}

        open_exes     = set()
        open_ws_paths = set()
        open_folders  = set()
        open_profiles = set()
        open_uwp      = set()
        open_types    = set()
        browser_titles = []

        for app in current:
            t    = (app.get("type") or "").lower()
            exe  = (app.get("exe_path") or "").lower()
            ws   = (app.get("workspace_path") or "").lower()
            fld  = (app.get("folder_path") or "").lower()
            prof = (app.get("profile_name") or "").lower()
            prot = (app.get("protocol") or "").lower()
            name = (app.get("name") or "").lower()

            if exe:     open_exes.add(exe)
            if ws:      open_ws_paths.add(ws)
            if fld:     open_folders.add(fld)
            if prof:    open_profiles.add(prof)
            if t:       open_types.add(t)

            if t in ("chrome", "edge", "brave", "firefox"):
                win_title = (
                    (app.get("window") or {}).get("title")
                    or app.get("name") or ""
                ).strip()
                if win_title:
                    browser_titles.append(win_title)

            if t == "uwp":
                if prot: open_uwp.add(prot)
                if name: open_uwp.add(name)

        open_profiles.update(_extra_profiles)
        print(Fore.CYAN + f"[WORKSPACE] Open URLs: {len(open_chrome_urls)}, "
              f"Domains: {len(open_chrome_domains)}")

        filtered_apps = [cfg for cfg in apps_config if should_restore(cfg)]

        missing      = []
        already_open = 0

        for cfg in filtered_apps:
          try:
            t    = (cfg.get("type") or "").lower()
            exe  = (cfg.get("exe_path") or "").lower()
            ws   = (cfg.get("workspace_path") or "").lower()
            fld  = (cfg.get("folder_path") or "").lower()
            prof = (cfg.get("profile_name") or "").lower()
            prot = (cfg.get("protocol") or "").lower()
            name = (cfg.get("name") or "").lower()
            tabs = cfg.get("tabs", [])

            if t in ("chrome", "edge", "brave", "firefox"):
                # Check if there are VISIBLE browser windows of this type open
                has_visible_browser_window = any(
                    (app.get("type") or "").lower() == t for app in current
                )

                if not has_visible_browser_window and not tabs:
                    # Browser closed and no tabs to restore — skip
                    already_open += 1
                    continue

                if not has_visible_browser_window and tabs:
                    # Browser completely closed — restore ALL tabs
                    print(Fore.GREEN + f"[WORKSPACE] {t.title()} is closed — "
                          f"restoring all {len(tabs)} tab(s) for profile '{prof}'")
                    new_cfg = dict(cfg)
                    new_cfg["_browser_closed"] = True
                    missing.append(new_cfg)
                    continue

                # Browser is open — do PER-PROFILE tab deduplication
                if tabs:
                    missing_tabs = []
                    skipped_tabs = 0

                    # Get the set of URLs open in THIS specific profile
                    prof_open_urls = set()
                    if per_profile_urls:
                        # Try matching saved profile name against live profiles
                        for live_prof, live_urls in per_profile_urls.items():
                            lp = live_prof.lower()
                            sp = (prof or "").lower()
                            sd = (cfg.get("profile_dir") or "").lower()
                            if (sp and (sp == lp or sp in lp or lp in sp)) or \
                               (sd and (sd == lp or sd in lp or lp in sd)):
                                prof_open_urls = live_urls
                                break

                    for tab in tabs:
                        tab_url = tab.get("url", "")
                        if not tab_url:
                            continue

                        tab_norm = normalize_url(tab_url)

                        # Check 1: Is this URL open in the SAME profile?
                        if tab_norm in prof_open_urls:
                            skipped_tabs += 1
                            continue

                        # Check 2: If per-profile data unavailable, check global
                        if not prof_open_urls and open_chrome_urls:
                            if url_matches(tab_url, open_chrome_urls,
                                           open_chrome_domains):
                                skipped_tabs += 1
                                continue

                        # Tab is genuinely missing from this profile
                        missing_tabs.append(tab)

                    if not missing_tabs:
                        already_open += 1
                        print(Fore.CYAN + f"[WORKSPACE] {name}: "
                              f"All {skipped_tabs} tabs already open in profile")
                    else:
                        new_cfg = dict(cfg)
                        new_cfg["tabs"] = missing_tabs
                        new_cfg["_partial"] = True
                        missing.append(new_cfg)
                        print(Fore.GREEN + f"[WORKSPACE] {name}: "
                              f"{len(missing_tabs)} missing, "
                              f"{skipped_tabs} already open")
                else:
                    if prof and prof in open_profiles:
                        already_open += 1
                    else:
                        missing.append(cfg)

            elif t == "vscode":
                if ws and ws in open_ws_paths:
                    already_open += 1
                elif exe and exe in open_exes:
                    already_open += 1
                else:
                    missing.append(cfg)

            elif t == "explorer":
                # Check 1: exact folder path match
                if fld and fld in open_folders:
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (folder): {name}")
                # Check 2: Explorer title match (handles "Home", "This PC", custom libraries)
                elif any(app.get("type") == "explorer" and (name.lower() in (app.get("name") or "").lower() or (app.get("name") or "").lower() in name.lower()) for app in current):
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (explorer title): {name}")
                # Check 3: If no specific folder was requested and an Explorer window is already visible
                elif not fld and ("explorer" in open_types or any(app.get("type") == "explorer" for app in current)):
                    already_open += 1
                    print(Fore.CYAN + f"[WORKSPACE] Already open (generic explorer): {name}")
                else:
                    missing.append(cfg)
                    print(Fore.YELLOW + f"[WORKSPACE] Missing explorer: {name}")

            elif t == "uwp":
                if (prot and prot in open_uwp) or \
                   (name and name in open_uwp):
                    already_open += 1
                else:
                    missing.append(cfg)

            else:
                is_open = False
                if exe and exe in open_exes:
                    is_open = True
                elif name:
                    for app in current:
                        curr_name = (app.get("name") or "").lower()
                        if name in curr_name or curr_name in name:
                            is_open = True
                            break

                if is_open:
                    already_open += 1
                else:
                    missing.append(cfg)
          except Exception as _cfg_err:
            print(Fore.RED + f"[WORKSPACE] Error processing "
                  f"{cfg.get('name','?')}: {_cfg_err}")
            missing.append(cfg)  # attempt restore anyway

        if missing:
            print(Fore.CYAN + f"[WORKSPACE] Opening {len(missing)} apps "
                  f"({already_open} already running)")
            _do_restore(missing)
        else:
            print(Fore.GREEN + "[WORKSPACE] All apps already open")

        return len(missing), already_open

    finally:
        _restore_in_progress.release()


def restore(apps_config):
    """Launch all apps in parallel threads (no dedup check)."""
    if not apps_config:
        return

    clean_config = [cfg for cfg in apps_config if should_restore(cfg)]

    if not clean_config:
        print(Fore.GREEN + "[WORKSPACE] Nothing to restore after filtering")
        return

    print(Fore.CYAN + f"[WORKSPACE] Restoring {len(clean_config)} apps...")
    _do_restore(clean_config)


def _do_restore(apps_config):
    """Internal: launch apps in parallel threads."""
    import time
    t0      = time.time()
    threads = []

    for cfg in apps_config:
        th = threading.Thread(target=restore_one, args=(cfg,), daemon=True)
        th.start()
        threads.append(th)

    for th in threads:
        th.join(timeout=20)
    elapsed = int((time.time() - t0) * 1000)
    print(Fore.GREEN + f"[WORKSPACE] Done in {elapsed}ms")

def _check_chrome_profile_active(cfg):
    """Quick check if Chrome is running with the saved profile directory."""
    profile_dir = cfg.get("profile_dir", "")
    if not profile_dir:
        return False
    try:
        import psutil
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                if proc.info.get("name", "").lower() == "chrome.exe":
                    cmdline = proc.info.get("cmdline") or []
                    for arg in cmdline:
                        if f"--profile-directory={profile_dir}" in arg:
                            return True
            except Exception:
                continue
    except Exception:
        pass
    return False