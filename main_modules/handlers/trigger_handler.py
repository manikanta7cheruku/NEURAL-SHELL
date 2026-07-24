"""
=============================================================================
main_modules/handlers/trigger_handler.py

Handles ###TRIGGER: and ###WORKSPACE: tags from brain pipeline.

###TRIGGER: action=fire phrase=focus
  → Looks up trigger by voice phrase
  → Executes the trigger action

###WORKSPACE: action=save name=Focus
  → Scans current desktop
  → Saves workspace to DB

###WORKSPACE: action=restore name=Focus
  → Loads workspace from DB
  → Restores all apps in parallel

###WORKSPACE: action=list
  → Lists all saved workspaces
  → Speaks the names
=============================================================================
"""

import re
import json
import threading
from colorama import Fore
from main_modules.handlers.base import BaseHandler


class TriggerHandler(BaseHandler):
    tag_name = "TRIGGER"

    def execute(self, response, ctx):
        for params in self.extract_params(response):
            action = params.get("action", "")
            try:
                if action == "fire":
                    self._fire_by_phrase(params, ctx)
            except Exception as e:
                print(Fore.RED + f"[TRIGGER HANDLER] Error: {e}")
                import traceback; traceback.print_exc()

    def _fire_by_phrase(self, params, ctx):
        phrase = params.get("phrase", "").replace("|||", " ").replace("_", " ")
        if not phrase:
            return

        try:
            from backend.routes.triggers import db_get_by_voice_phrase, db_increment_fire_count
            trigger = db_get_by_voice_phrase(phrase)

            if not trigger:
                ctx.speak(f"No trigger found for '{phrase}'.")
                return

            success, message = execute_trigger_action(trigger)
            db_increment_fire_count(trigger["id"])

            if success:
                ctx.update_status(f"Trigger: {trigger['name']}", "#00ff00")
            else:
                ctx.speak(f"Trigger failed: {message}")

        except Exception as e:
            print(Fore.RED + f"[TRIGGER HANDLER] Fire error: {e}")
            ctx.speak("Something went wrong with the trigger.")


class WorkspaceHandler(BaseHandler):
    tag_name = "WORKSPACE"

    def execute(self, response, ctx):
        for params in self.extract_params(response):
            action = params.get("action", "")
            try:
                if action == "save":
                    self._save_workspace(params, ctx)
                elif action == "restore":
                    self._restore_workspace(params, ctx)
                elif action == "list":
                    self._list_workspaces(ctx)
            except Exception as e:
                print(Fore.RED + f"[WORKSPACE HANDLER] Error: {e}")
                import traceback; traceback.print_exc()

    def _save_workspace(self, params, ctx):
        name = params.get("name", "").replace("|||", " ").replace("_", " ")
        if not name:
            ctx.speak("What should I call this workspace?")
            return

        try:
            from hands.workspace import scan_current
            apps = scan_current()

            if not apps:
                ctx.speak("No apps to save. Open some apps first.")
                return

            # Save via API
            import requests
            r = requests.post(
                "http://127.0.0.1:7777/api/workspaces",
                json={
                    "name": name,
                    "description": f"Saved automatically with {len(apps)} apps",
                    "apps": apps,
                },
                timeout=5
            )

            if r.status_code == 200:
                ctx.speak(f"Workspace '{name}' saved with {len(apps)} apps.")
                ctx.update_status(f"Workspace saved: {name}", "#00ff00")

                if ctx.api_set_state:
                    ctx.api_set_state("workspace_saved", {
                        "name": name,
                        "app_count": len(apps),
                    })
            else:
                ctx.speak("Could not save workspace. Try again.")

        except Exception as e:
            print(Fore.RED + f"[WORKSPACE] Save error: {e}")
            ctx.speak("Something went wrong saving the workspace.")

    def _restore_workspace(self, params, ctx):
        name = params.get("name", "").replace("|||", " ").replace("_", " ")
        if not name:
            ctx.speak("Which workspace should I open?")
            return

        try:
            from backend.routes.workspaces import db_get_workspace_by_name

            workspace = db_get_workspace_by_name(name)
            if not workspace:
                ctx.speak(f"No workspace named '{name}' found.")
                return

            apps = workspace.get("apps", [])
            app_count = len(apps)

            ctx.update_status(f"Restoring: {name}", "#00ccff")

            # Smart restore — only open what's missing
            def _do_restore():
                try:
                    from hands.workspace import smart_restore
                    opened, skipped = smart_restore(apps)

                    # Show notification via overlay daemon
                    try:
                        from seven_overlay.notifications import show_trigger_notification
                        app_list = [a.get("name", "") for a in apps]
                        app_names_str = ",".join(app_list)
                        show_trigger_notification(
                            trigger_name=name,
                            action_type="open_workspace",
                            app_count=len(apps),
                            tab_count=sum(len(a.get("tabs", [])) for a in apps),
                            app_names=app_names_str,
                        )
                    except Exception:
                        pass

                    # Speak result
                    if opened > 0:
                        ctx.speak(f"{name} workspace restored. {opened} apps opened.")
                    else:
                        ctx.speak(f"{name} workspace is already active.")
                except Exception as e:
                    print(f"[WORKSPACE] Restore error: {e}")
                    ctx.speak(f"Could not restore {name} workspace.")

            threading.Thread(target=_do_restore, daemon=True).start()

            # Update use stats
            import requests
            try:
                requests.post(
                    f"http://127.0.0.1:7777/api/workspaces/{workspace['id']}/restore",
                    timeout=3
                )
            except Exception:
                pass

        except Exception as e:
            print(Fore.RED + f"[WORKSPACE] Restore error: {e}")
            ctx.speak("Something went wrong restoring the workspace.")

    def _list_workspaces(self, ctx):
        try:
            import requests
            r = requests.get("http://127.0.0.1:7777/api/workspaces", timeout=5)

            if r.status_code == 200:
                workspaces = r.json()
                if not workspaces:
                    ctx.speak("No workspaces saved yet. Say 'save workspace as Focus' to create one.")
                    return

                names = [w.get("name", "unnamed") for w in workspaces[:5]]
                count = len(workspaces)

                if count == 1:
                    ctx.speak(f"One workspace: {names[0]}.")
                elif count <= 3:
                    ctx.speak(f"{count} workspaces: {', '.join(names)}.")
                else:
                    ctx.speak(
                        f"{count} workspaces. Most recent: {', '.join(names[:3])}. "
                        f"Check the Triggers page for all."
                    )
            else:
                ctx.speak("Could not load workspaces.")

        except Exception as e:
            print(Fore.RED + f"[WORKSPACE] List error: {e}")
            ctx.speak("Something went wrong loading workspaces.")


# ─────────────────────────────────────────────────────────────────────────
# STANDALONE EXECUTION FUNCTION
# Used by trigger_daemon.py and fire endpoint
# ─────────────────────────────────────────────────────────────────────────
def _inject_into_vscode_terminal(cmd):
    """
    Inject a command into VS Code's active integrated terminal.

    Strategy:
      1. Find running VS Code process to get its working directory
      2. Focus VS Code window
      3. Use pyautogui to open terminal if not visible (Ctrl+`) 
      4. Send the command text + Enter via clipboard paste
         (clipboard paste is safer than keystroke simulation for special chars)

    Returns (success, message).
    """
    import time
    import ctypes

    try:
        import psutil
        import pyautogui
        import win32gui
        import win32con

        # Step 1: Find VS Code window
        vscode_hwnd = None

        def _find_vscode(hwnd, _):
            nonlocal vscode_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if title and ('visual studio code' in title.lower() or
                          title.lower().startswith('● ') or
                          '.js' in title or '.py' in title or
                          'vscode' in title.lower()):
                # More reliable: check if exe is code.exe
                try:
                    import win32process
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc = psutil.Process(pid)
                    if 'code' in proc.name().lower():
                        vscode_hwnd = hwnd
                        return False
                except Exception:
                    pass
            return True

        win32gui.EnumWindows(_find_vscode, None)

        # Fallback: find by process name
        if not vscode_hwnd:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if 'code' in proc.info['name'].lower():
                        # Find its window
                        def _by_pid(hwnd, pid):
                            nonlocal vscode_hwnd
                            try:
                                import win32process
                                _, wpid = win32process.GetWindowThreadProcessId(hwnd)
                                if wpid == pid and win32gui.IsWindowVisible(hwnd):
                                    if win32gui.GetWindowTextLength(hwnd) > 0:
                                        vscode_hwnd = hwnd
                                        return False
                            except Exception:
                                pass
                            return True
                        win32gui.EnumWindows(_by_pid, proc.info['pid'])
                        if vscode_hwnd:
                            break
                except Exception:
                    continue

        if not vscode_hwnd:
            return False, "VS Code is not open. Open VS Code first."

        # Step 2: Focus VS Code
        win32gui.ShowWindow(vscode_hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(vscode_hwnd)
        time.sleep(0.4)

        # Step 3: Open terminal panel if needed (Ctrl+`)
        # Send Ctrl+` to toggle terminal — if already open it stays open
        pyautogui.hotkey('ctrl', '`')
        time.sleep(0.5)

        # Step 4: Click terminal area to ensure focus
        # Get window rect and click bottom third (where terminal lives)
        rect = win32gui.GetWindowRect(vscode_hwnd)
        win_x = rect[0]
        win_y = rect[1]
        win_w = rect[2] - rect[0]
        win_h = rect[3] - rect[1]

        # Click in the terminal area (bottom 25% of window, centered)
        click_x = win_x + win_w // 2
        click_y = win_y + int(win_h * 0.82)
        pyautogui.click(click_x, click_y)
        time.sleep(0.3)

        # Step 5: Paste command via clipboard (handles special chars safely)
        import subprocess as _sp
        # Set clipboard
        _sp.run(
            ['clip'],
            input=cmd.encode('utf-8'),
            creationflags=0x08000000,
            check=False
        )
        time.sleep(0.1)

        # Paste and execute
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.15)
        pyautogui.press('enter')

        print(f"[TRIGGER] Injected into VS Code terminal: {cmd}")
        return True, f"Sent to VS Code terminal: {cmd[:50]}"

    except ImportError as ie:
        missing = str(ie).split("'")[1] if "'" in str(ie) else str(ie)
        return False, f"Missing dependency: {missing}"
    except Exception as e:
        print(f"[TRIGGER] VS Code inject error: {e}")
        return False, f"Could not inject into VS Code: {e}"


def execute_trigger_action(trigger):
    """
    Execute a trigger's action.
    Returns (success: bool, message: str).

    Used by:
      - trigger_daemon.py (when hotkey/audio fires)
      - POST /api/triggers/{id}/fire (manual test)
      - TriggerHandler (voice command)
    """
    import os
    import subprocess
    import webbrowser

    action_type = trigger.get("action_type", "")
    action_data = trigger.get("action_data", {})
    name        = trigger.get("name", "unnamed")

    try:
        if action_type == "open_app":
            # Support single app or multiple apps
            apps_list = action_data.get("apps", [])
            single_app = action_data.get("app", "")
            if single_app and not apps_list:
                apps_list = [single_app]

            if not apps_list:
                return False, "No app specified"

            opened = []
            for app_name in apps_list:
                try:
                    from hands.core import open_app
                    import threading
                    threading.Thread(target=open_app, args=(app_name,), daemon=True).start()
                    opened.append(app_name)
                except Exception:
                    try:
                        import AppOpener
                        AppOpener.open(app_name)
                        opened.append(app_name)
                    except Exception:
                        pass

            if opened:
                return True, f"Opened {', '.join(opened)}"
            return False, "Could not open any apps"

        elif action_type == "open_url":
            urls_list = action_data.get("urls", [])
            single_url = action_data.get("url", "")
            if single_url and not urls_list:
                urls_list = [single_url]

            if not urls_list:
                return False, "No URL specified"

            for url in urls_list:
                webbrowser.open(url)

            return True, f"Opened {len(urls_list)} URL{'s' if len(urls_list) > 1 else ''}"

        elif action_type == "open_file":
            paths_list = action_data.get("paths", [])
            single_path = action_data.get("path", "")
            if single_path and not paths_list:
                paths_list = [single_path]

            if not paths_list:
                return False, "No file specified"

            opened = []
            missing = []
            for path in paths_list:
                if os.path.exists(path):
                    os.startfile(path)
                    opened.append(path)
                else:
                    missing.append(path)

            if not opened:
                return False, f"File not found: {missing[0]}"
            return True, f"Opened {len(opened)} file{'s' if len(opened) > 1 else ''}"

        elif action_type == "open_folder":
            paths_list = action_data.get("paths", [])
            single_path = action_data.get("path", "")
            if single_path and not paths_list:
                paths_list = [single_path]

            if not paths_list:
                return False, "No folder specified"

            opened = []
            missing = []
            for path in paths_list:
                if os.path.exists(path):
                    subprocess.Popen(['explorer', path])
                    opened.append(path)
                else:
                    missing.append(path)

            if not opened:
                return False, f"Folder not found: {missing[0]}"
            return True, f"Opened {len(opened)} folder{'s' if len(opened) > 1 else ''}"

        elif action_type == "open_workspace":
            workspace_id   = action_data.get("workspace_id")
            workspace_name = action_data.get("workspace_name")

            from backend.routes.workspaces import (
                db_get_workspace_by_id,
                db_get_workspace_by_name
            )

            workspace = None
            if workspace_id:
                workspace = db_get_workspace_by_id(workspace_id)
            elif workspace_name:
                workspace = db_get_workspace_by_name(workspace_name)

            if not workspace:
                return False, f"Workspace not found"

            apps = workspace.get("apps", [])

            def _do_smart_restore():
                try:
                    from hands.workspace import smart_restore
                    smart_restore(apps)
                except ImportError:
                    from hands.workspace import restore
                    restore(apps)

            import threading
            threading.Thread(target=_do_smart_restore, daemon=True).start()

            return True, f"Restoring {workspace['name']} ({len(apps)} apps)"

        elif action_type == "run_command":
            cmd = action_data.get("command", "")
            if not cmd:
                return False, "No command specified"

            target = action_data.get("target", "terminal")

            if target == "vscode":
                success, message = _inject_into_vscode_terminal(cmd)
                return success, message

            # Default: run silently in background
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                cmd,
                shell=True,
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Executed: {cmd[:50]}"

        elif action_type == "seven_action":
            action = action_data.get("action", "")
            if not action:
                return False, "No action specified"

            # Send to Seven's brain in a background thread
            # Brain handles all intelligence: app opening, system control, etc.
            import threading as _t
            def _send_to_brain():
                try:
                    import requests as _req
                    _req.post(
                        "http://127.0.0.1:7777/api/chat",
                        json={"text": action, "speaker_id": "default"},
                        timeout=60,
                    )
                except Exception as _e:
                    print(f"[TRIGGER] seven_action brain error: {_e}")
            _t.Thread(target=_send_to_brain, daemon=True).start()
            return True, f"Seven processing: {action}"

        else:
            return False, f"Unknown action type: {action_type}"

    except Exception as e:
        return False, str(e)