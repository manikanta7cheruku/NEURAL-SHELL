"""
trigger_modules/executor.py
Trigger action execution — all action types.

Handles: open_app, open_url, open_file, open_folder,
         open_workspace, run_command, seven_action.

Called by hotkey_listener, audio_listener, voice_listener,
and the HTTP fire endpoint.
"""
import os
import re
import json
import time
import sqlite3
import subprocess
import threading
import webbrowser
from datetime import datetime

from trigger_modules.config import TRIGGERS_DB, is_seven_running
from trigger_modules.overlay import (
    ensure_overlay_alive_safe,
    fire_notification,
    fire_arrangement_card,
    _send_overlay,
)
from trigger_modules.window_finder import get_windows_by_workspace_apps
from trigger_modules.app_launcher import open_app_robust
from trigger_modules.database import update_fire_stats

# Per-trigger cooldown — prevents double-fire when user mashes hotkey
# or fires same trigger via voice + hotkey within 5 seconds
_trigger_cooldowns = {}
_TRIGGER_COOLDOWN_SEC = 5.0


# ─────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────
def execute_trigger(trigger):
    """
    Execute a trigger action.
    Shows notification INSTANTLY, then runs action in background.
    For workspace triggers: shows arrangement card after apps open.
    """
    action_type = trigger.get("action_type", "")
    action_data = trigger.get("action_data", {})
    name        = trigger.get("name", "unnamed")
    trigger_id  = trigger.get("id", 0)

    # Cooldown check — prevent double-fire within 5 seconds
    now = time.time()
    last_fire = _trigger_cooldowns.get(trigger_id, 0)
    if now - last_fire < _TRIGGER_COOLDOWN_SEC:
        print(f"[TRIGGER DAEMON] Cooldown active for '{name}' "
              f"({_TRIGGER_COOLDOWN_SEC - (now - last_fire):.1f}s remaining)")
        return
    _trigger_cooldowns[trigger_id] = now

    print(f"[TRIGGER DAEMON] Firing: {name} (type={action_type})")

    app_count  = 0
    tab_count  = 0
    app_names  = ""
    workspace_apps = []

    if action_type == "open_workspace":
        ws_id   = action_data.get("workspace_id")
        ws_name = action_data.get("workspace_name")
        try:
            conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            if ws_id:
                ws_row = conn.execute(
                    "SELECT apps FROM workspaces WHERE id = ?", (ws_id,)
                ).fetchone()
            elif ws_name:
                ws_row = conn.execute(
                    "SELECT apps FROM workspaces WHERE LOWER(name) = ?",
                    (ws_name.lower(),)
                ).fetchone()
            else:
                ws_row = None
            conn.close()

            if ws_row:
                workspace_apps = json.loads(ws_row["apps"] or "[]")
                app_count  = len(workspace_apps)
                names_list = []
                for a in workspace_apps:
                    n = a.get("name", "")
                    if " - " in n:
                        n = n.split(" - ")[-1].strip()
                    names_list.append(n)
                    tab_count += len(a.get("tabs", []))
                app_names = ",".join(names_list)
        except Exception as we:
            print(f"[TRIGGER DAEMON] Workspace lookup: {we}")

    elif action_type == "open_app":
        apps_list  = action_data.get("apps", [])
        single     = action_data.get("app", "")
        if single and not apps_list:
            apps_list = [single]
        app_count  = len(apps_list)
        app_names  = ",".join(apps_list)
        workspace_apps = [{"name": a, "exe_path": ""} for a in apps_list]

    threading.Thread(
        target=_execute_trigger_complete,
        args=(trigger, name, action_type, action_data,
              app_count, tab_count, app_names, workspace_apps),
        daemon=True,
    ).start()


# ─────────────────────────────────────────────────────────────────────────
# COMPLETE EXECUTION PIPELINE
# ─────────────────────────────────────────────────────────────────────────
def _execute_trigger_complete(trigger, name, action_type, action_data,
                               app_count, tab_count, app_names,
                               workspace_apps=None):
    """
    Complete trigger execution.
    Fires notification asynchronously and executes the action immediately.
    """
    workspace_apps = workspace_apps or []

    # Fire visual notification asynchronously (never blocks action execution)
    if not trigger.get("silent", False):
        fire_notification(name, action_type, app_count, tab_count, app_names)

    # Step 2: Execute action immediately
    result = None
    try:
        if action_type == "open_app":
            _exec_open_app(action_data)
        elif action_type == "open_url":
            _exec_open_url(action_data)
        elif action_type == "open_file":
            _exec_open_file(action_data)
        elif action_type == "open_folder":
            _exec_open_folder(action_data)
        elif action_type == "open_workspace":
            result = _exec_open_workspace(action_data)
        elif action_type == "run_command":
            _run_data = dict(action_data)
            _run_data["_fired_key"] = trigger.get("_fired_key", "")
            _run_data["_had_modifiers"] = trigger.get("_had_modifiers", True)
            _exec_run_command(_run_data)
        elif action_type == "seven_action":
            _exec_seven_action(action_data)
        else:
            print(f"[TRIGGER DAEMON] Unknown action: {action_type}")
            return
    except Exception as e:
        print(f"[TRIGGER DAEMON] Action error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 4: Feedback + arrangement card
    if action_type == "open_workspace" and result and not trigger.get("silent", False):
        opened  = result.get("opened", 0)
        skipped = result.get("skipped", 0)

        if opened == 0 and skipped > 0:
            _send_overlay({
                "type": "notif",
                "data": {
                    "title":    name,
                    "subtitle": "Already active",
                    "detail":   f"All {skipped} app{'s' if skipped != 1 else ''} already open",
                    "holdMs":   2500,
                },
            })
            # Wait for windows to be visible, then show arrangement
            time.sleep(1.2)
            fire_arrangement_card(workspace_apps, get_windows_by_workspace_apps)

        elif opened > 0 and skipped > 0:
            _send_overlay({
                "type": "notif",
                "data": {
                    "title":    name,
                    "subtitle": "Workspace restored",
                    "detail":   f"{opened} opened · {skipped} already running",
                    "holdMs":   2200,
                },
            })
            # Give newly-opened apps 3 seconds to appear on screen
            # (Notepad, Word, Chrome all take 1-2s to render window)
            time.sleep(3.0)
            fire_arrangement_card(workspace_apps, get_windows_by_workspace_apps)

        elif opened > 0:
            # Longer wait — all apps were newly launched
            time.sleep(3.5)
            fire_arrangement_card(workspace_apps, get_windows_by_workspace_apps)

    elif action_type == "open_app" and not trigger.get("silent", False):
        if len(workspace_apps) >= 2:
            time.sleep(2.5)
            fire_arrangement_card(workspace_apps, get_windows_by_workspace_apps)

    # Step 5: Update fire stats
    update_fire_stats(trigger.get("id"))


# ─────────────────────────────────────────────────────────────────────────
# INDIVIDUAL ACTION EXECUTORS
# ─────────────────────────────────────────────────────────────────────────
def _exec_open_app(data):
    """Launch application(s). Supports single or multiple apps."""
    apps_list  = data.get("apps", [])
    single_app = data.get("app", "")
    if single_app and not apps_list:
        apps_list = [single_app]

    if not apps_list:
        print("[TRIGGER DAEMON] No app specified")
        return

    for app_name in apps_list:
        if not app_name:
            continue
        open_app_robust(app_name)


def _exec_open_url(data):
    """Open URL(s) in default browser."""
    urls   = data.get("urls", [])
    single = data.get("url", "")
    if single and not urls:
        urls = [single]
    for url in urls:
        if url:
            webbrowser.open(url)
            print(f"[TRIGGER DAEMON] Opened URL: {url}")


def _exec_open_file(data):
    """Open file(s) with default application."""
    paths  = data.get("paths", [])
    single = data.get("path", "")
    if single and not paths:
        paths = [single]
    for path in paths:
        if path and os.path.exists(path):
            os.startfile(path)
            print(f"[TRIGGER DAEMON] Opened file: {path}")


def _exec_open_folder(data):
    """Open folder(s) in Explorer."""
    paths  = data.get("paths", [])
    single = data.get("path", "")
    if single and not paths:
        paths = [single]
    for path in paths:
        if path and os.path.exists(path):
            subprocess.Popen(['explorer', path])
            print(f"[TRIGGER DAEMON] Opened folder: {path}")


def _exec_open_workspace(data):
    """
    Restore a workspace by ID or name using smart_restore.
    Returns {"opened": N, "skipped": N} for caller to show feedback.
    """
    workspace_id   = data.get("workspace_id")
    workspace_name = data.get("workspace_name")

    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        if workspace_id:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
        elif workspace_name:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE LOWER(name) = ?",
                (workspace_name.lower(),)
            ).fetchone()
        else:
            conn.close()
            print("[TRIGGER DAEMON] No workspace ID or name provided")
            return {"opened": 0, "skipped": 0}

        conn.close()

        if not row:
            print(f"[TRIGGER DAEMON] Workspace not found: "
                  f"id={workspace_id} name={workspace_name}")
            return {"opened": 0, "skipped": 0}

        workspace = dict(row)
        try:
            apps = json.loads(workspace.get("apps") or "[]")
        except Exception:
            apps = []

        if not apps:
            print("[TRIGGER DAEMON] Workspace has no apps")
            return {"opened": 0, "skipped": 0}

        from hands.workspace import smart_restore
        opened, skipped = smart_restore(apps)
        print(f"[TRIGGER DAEMON] Smart restore: "
              f"{opened} opened, {skipped} already running")

        if is_seven_running() and workspace_id:
            try:
                import requests
                requests.post(
                    f"http://127.0.0.1:7777/api/workspaces/{workspace_id}/restore"
                    f"?stats_only=true",
                    timeout=2,
                )
            except Exception:
                pass

        print(f"[TRIGGER DAEMON] Workspace done: "
              f"{workspace.get('name')} ({len(apps)} apps)")

        return {"opened": opened, "skipped": skipped}

    except Exception as e:
        print(f"[TRIGGER DAEMON] Workspace restore error: {e}")
        import traceback
        traceback.print_exc()
        return {"opened": 0, "skipped": 0}


def _exec_run_command(data):
    """
    Inject a shell command into the focused text input using Native Win32 SendInput.

    UNIVERSAL STRATEGY:
      - Backspace ANY stray key that leaked from the hotkey combo.
      - Inject characters instantly and smoothly using KEYEVENTF_UNICODE packets.
      - Win32 SendInput completely bypasses input buffers, meaning it works 
        inside PowerShell, VS Code terminal, Chrome, and WhatsApp instantly.
    """
    cmd    = data.get("command", "")
    target = data.get("target", "terminal")

    if not cmd:
        return

    # Background mode — silent subprocess, no typing
    if target == "background":
        import sys as _sys
        _cflags = 0x08000000 if _sys.platform == 'win32' else 0
        subprocess.Popen(
            cmd, shell=True, creationflags=_cflags,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[TRIGGER DAEMON] Run (background): {cmd[:60]}")
        return

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        
        # SendInput structures
        PUL = ctypes.POINTER(ctypes.c_ulong)
        class KeyBdInput(ctypes.Structure):
            _fields_ = [
                ("wVk",         wintypes.WORD),
                ("wScan",       wintypes.WORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", PUL),
            ]
        class HardwareInput(ctypes.Structure):
            _fields_ = [
                ("uMsg",    wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD),
            ]
        class MouseInput(ctypes.Structure):
            _fields_ = [
                ("dx",          wintypes.LONG),
                ("dy",          wintypes.LONG),
                ("mouseData",   wintypes.DWORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", PUL),
            ]
        class InputUnion(ctypes.Union):
            _fields_ = [
                ("ki", KeyBdInput),
                ("mi", MouseInput),
                ("hi", HardwareInput),
            ]
        class Input(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("ii",   InputUnion),
            ]

        INPUT_KEYBOARD       = 1
        KEYEVENTF_KEYUP      = 0x0002
        KEYEVENTF_UNICODE    = 0x0004
        KEYEVENTF_SCANCODE   = 0x0008

        # ── STEP 1: Release ALL physically-held modifier keys ──
        for _vk in [0x11, 0x10, 0x12, 0x5B, 0x5C]:  # Ctrl, Shift, Alt, LWin, RWin
            user32.keybd_event(_vk, 0, KEYEVENTF_KEYUP, 0)

        # ── STEP 2: Release the trigger key itself ──
        _fired_key = data.get("_fired_key", "")
        _vk_fired = None
        if _fired_key:
            _vk_map = {
                '/': 0xBF, '\\': 0xDC, '.': 0xBE, ',': 0xBC,
                ';': 0xBA, "'": 0xDE, '[': 0xDB, ']': 0xDD,
                '`': 0xC0, '-': 0xBD, '=': 0xBB, ' ': 0x20,
            }
            _vk_fired = _vk_map.get(_fired_key)
            if _vk_fired is None and len(_fired_key) == 1:
                if _fired_key.isalpha():
                    _vk_fired = ord(_fired_key.upper())
                elif _fired_key.isdigit():
                    _vk_fired = ord(_fired_key)
            if _vk_fired:
                user32.keybd_event(_vk_fired, 0, KEYEVENTF_KEYUP, 0)

        # ── STEP 3: Wait for OS to fully process key release ──
        time.sleep(0.35)

        # ── STEP 4: Detect focused app ──
        try:
            import win32gui, win32process, psutil
            _hwnd = user32.GetForegroundWindow()
            _title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(_hwnd, _title, 512)
            _title_str = (_title.value or "").lower()
            _, _pid = win32process.GetWindowThreadProcessId(_hwnd)
            _proc = psutil.Process(_pid).name().lower()
        except Exception:
            _proc = ""
            _title_str = ""

        # Terminal-class apps
        _terminal_apps = {
            "powershell.exe", "pwsh.exe", "cmd.exe",
            "windowsterminal.exe", "wt.exe", "conhost.exe",
            "bash.exe", "wsl.exe", "mintty.exe",
        }
        _browser_apps = {
            "chrome.exe", "msedge.exe", "firefox.exe",
            "brave.exe", "opera.exe",
        }

        is_terminal = _proc in _terminal_apps
        is_browser  = _proc in _browser_apps

        # ── STEP 5: Backspace stray char if it typed itself ──
        _navigation_keys = {
            'home', 'end', 'pageup', 'pagedown', 'up', 'down',
            'left', 'right', 'insert', 'delete', 'tab', 'esc',
            'enter', 'backspace', 'capslock', 'numlock'
        }
        _is_function_key = _fired_key and _fired_key.startswith('f') and \
                           _fired_key[1:].isdigit()
        _is_navigation  = _fired_key in _navigation_keys
        _is_printable   = bool(_fired_key) and not _is_function_key and \
                          not _is_navigation and len(_fired_key) == 1

        if _is_printable:
            user32.keybd_event(0x08, 0, 0, 0)  # Backspace down
            time.sleep(0.02)
            user32.keybd_event(0x08, 0, KEYEVENTF_KEYUP, 0)  # up
            time.sleep(0.12)

        # ── STEP 6: For browsers, force focus commit ──
        if is_browser:
            user32.keybd_event(0x23, 0, 0, 0)   # End down
            time.sleep(0.03)
            user32.keybd_event(0x23, 0, KEYEVENTF_KEYUP, 0)  # End up
            time.sleep(0.15)

        # ── STEP 7: Smooth, high-fidelity native Win32 Unicode injection ──
        def _type_unicode(string):
            extra = ctypes.c_ulong(0)
            for char in string:
                code = ord(char)
                # Key Down
                ki_down = KeyBdInput(0, code, KEYEVENTF_UNICODE, 0, ctypes.pointer(extra))
                inp_down = Input(INPUT_KEYBOARD, InputUnion(ki=ki_down))
                user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
                time.sleep(0.005) # 5ms delay per char: natural typewriter, zero lag
                # Key Up
                ki_up = KeyBdInput(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
                inp_up = Input(INPUT_KEYBOARD, InputUnion(ki=ki_up))
                user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))
                time.sleep(0.005)

        _type_unicode(cmd)

        # ── STEP 8: Enter for terminal apps only ──
        time.sleep(0.15)
        if is_terminal:
            _VK_ENTER = 0x0D
            _SC_ENTER = 0x1C
            # Send Enter via scancode injection to ensure PowerShell registers it
            ki_down = KeyBdInput(_VK_ENTER, _SC_ENTER, KEYEVENTF_SCANCODE, 0, ctypes.pointer(ctypes.c_ulong(0)))
            inp_down = Input(INPUT_KEYBOARD, InputUnion(ki=ki_down))
            user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
            time.sleep(0.02)
            ki_up = KeyBdInput(_VK_ENTER, _SC_ENTER, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(ctypes.c_ulong(0)))
            inp_up = Input(INPUT_KEYBOARD, InputUnion(ki=ki_up))
            user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))
            print(f"[TRIGGER DAEMON] Injected + Enter in {_proc}: {cmd[:60]}")
        else:
            print(f"[TRIGGER DAEMON] Injected in {_proc} (no Enter): {cmd[:60]}")

    except Exception as e:
        print(f"[TRIGGER DAEMON] Run command error: {e}")
        import traceback
        traceback.print_exc()


def _exec_seven_action(data):
    """
    Execute internal Seven action.
    Parses the full action string and dispatches ALL commands found in it.
    Handles: app opens, brightness, volume, mute — all in one string.
    Falls back to chat API for anything not recognized.
    """
    action = data.get("action", "")
    if not action:
        return

    action_lower = action.lower().strip()

    # Split on common separators
    _parts = re.split(r'\s*(?:,|and|also|&|\+)\s*', action_lower)
    _parts = [p.strip() for p in _parts if p.strip()]

    _handled   = []
    _unhandled = []

    try:
        from hands.system import manage_system

        for part in _parts:

            # ── MUTE / UNMUTE ──
            if re.search(r'\bunmute\b', part):
                manage_system({"action": "volume_unmute"})
                _handled.append("unmute")
                continue

            if re.search(r'\bmute\b', part):
                manage_system({"action": "volume_mute"})
                _handled.append("mute")
                continue

            # ── VOLUME ──
            if re.search(r'\bvolume\b', part):
                nums = re.findall(r'\d+', part)
                if nums:
                    manage_system({"action": "volume_set", "value": nums[0]})
                    _handled.append(f"volume {nums[0]}%")
                elif re.search(r'\b(max|full|maximum)\b', part):
                    manage_system({"action": "volume_set", "value": "100"})
                    _handled.append("volume max")
                elif re.search(r'\b(min|low|minimum)\b', part):
                    manage_system({"action": "volume_set", "value": "10"})
                    _handled.append("volume min")
                continue

            # ── BRIGHTNESS ──
            if re.search(r'\b(brightness|bright|dim|screen)\b', part):
                nums = re.findall(r'\d+', part)
                if nums:
                    val = nums[0]
                elif re.search(r'\b(max|full|maximum|high)\b', part):
                    val = "100"
                elif re.search(r'\b(min|low|minimum|dim)\b', part):
                    val = "10"
                else:
                    val = "80"
                manage_system({"action": "brightness_set", "value": val})
                _handled.append(f"brightness {val}%")
                continue

            # ── OPEN APP ──
            open_match = re.match(
                r'^(?:open|launch|start|run)\s+(.+)$', part
            )
            app_name = open_match.group(1).strip() if open_match else None

            # URL detection
            _is_url = bool(
                re.match(r'^https?://', part) or
                re.match(r'^[\w\-]+\.(com|org|net|io|dev|app|co|in|gov|edu)', part)
            )
            if _is_url:
                try:
                    url = part if part.startswith('http') else f'https://{part}'
                    webbrowser.open(url)
                    _handled.append(f"open {url}")
                except Exception:
                    _unhandled.append(part)
                continue

            # Known system keywords — do not treat as app name
            _sys_keywords = {
                'brightness', 'volume', 'mute', 'unmute', 'media',
                'play', 'pause', 'next', 'previous', 'stop', 'dim',
                'show', 'tasks', 'schedule', 'screen',
            }
            _is_sys = any(kw in part for kw in _sys_keywords)

            if open_match or (not _is_sys and app_name is None):
                if app_name is None:
                    app_name = part.strip()
                try:
                    threading.Thread(
                        target=open_app_robust,
                        args=(app_name,),
                        daemon=True,
                    ).start()
                    _handled.append(f"open {app_name}")
                except Exception as _ae:
                    print(f"[TRIGGER DAEMON] App open failed for "
                          f"'{app_name}': {_ae}")
                    _unhandled.append(part)
                continue

            # ── MEDIA ──
            if re.search(r'\b(play|pause|next|previous|prev|stop)\b', part):
                if re.search(r'\bnext\b', part):
                    manage_system({"action": "media_next"})
                    _handled.append("media next")
                elif re.search(r'\b(previous|prev)\b', part):
                    manage_system({"action": "media_prev"})
                    _handled.append("media prev")
                elif re.search(r'\bstop\b', part):
                    manage_system({"action": "media_stop"})
                    _handled.append("media stop")
                else:
                    manage_system({"action": "media_play_pause"})
                    _handled.append("media play/pause")
                continue

            # ── SHOW TASKS PANEL ──
            if re.search(r'\b(show|open)\s+(my\s+)?tasks?\b', part):
                try:
                    import requests as _req
                    _req.post("http://127.0.0.1:7779/panel/open", timeout=3)
                    _handled.append("tasks panel")
                except Exception:
                    pass
                continue

            # ── SHOW SCHEDULE ──
            if re.search(r'\b(show|open)\s+(my\s+)?schedule\b', part):
                try:
                    _appdata = os.environ.get('APPDATA', '')
                    _nav = os.path.join(_appdata, 'SEVEN', 'nav_trigger.json')
                    with open(_nav, 'w') as _f:
                        json.dump({"route": "/schedules"}, _f)
                    _handled.append("schedule page")
                except Exception:
                    pass
                continue

            # ── UNRECOGNIZED ──
            _unhandled.append(part)

    except Exception as e:
        print(f"[TRIGGER DAEMON] Seven action parse error: {e}")
        import traceback
        traceback.print_exc()
        _unhandled = _parts

    print(f"[TRIGGER DAEMON] Seven action handled: {_handled}")

    # Send unrecognized parts to chat API as one message
    if _unhandled and is_seven_running():
        fallback_text = " and ".join(_unhandled)
        try:
            import requests
            requests.post(
                "http://127.0.0.1:7777/api/chat",
                json={"text": fallback_text, "speaker_id": "default"},
                timeout=60,
            )
            print(f"[TRIGGER DAEMON] Seven action API fallback: "
                  f"{fallback_text}")
        except Exception as e:
            print(f"[TRIGGER DAEMON] API fallback failed: {e}")
    elif _unhandled:
        print(f"[TRIGGER DAEMON] Seven not running, unhandled: "
              f"{_unhandled}")