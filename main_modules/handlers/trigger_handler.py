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

            ctx.speak(f"Opening {name} workspace. {app_count} apps coming up.")
            ctx.update_status(f"Restoring: {name}", "#00ccff")

            # Restore in background thread for speed
            from hands.workspace import restore
            threading.Thread(
                target=restore,
                args=(apps,),
                daemon=True
            ).start()

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

            for path in paths_list:
                if os.path.exists(path):
                    os.startfile(path)

            return True, f"Opened {len(paths_list)} file{'s' if len(paths_list) > 1 else ''}"

        elif action_type == "open_folder":
            paths_list = action_data.get("paths", [])
            single_path = action_data.get("path", "")
            if single_path and not paths_list:
                paths_list = [single_path]

            if not paths_list:
                return False, "No folder specified"

            for path in paths_list:
                if os.path.exists(path):
                    subprocess.Popen(['explorer', path])

            return True, f"Opened {len(paths_list)} folder{'s' if len(paths_list) > 1 else ''}"

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
            from hands.workspace import restore
            import threading
            threading.Thread(target=restore, args=(apps,), daemon=True).start()

            return True, f"Restoring {workspace['name']} ({len(apps)} apps)"

        elif action_type == "run_command":
            cmd = action_data.get("command", "")
            if not cmd:
                return False, "No command specified"
            subprocess.Popen(cmd, shell=True)
            return True, f"Executed: {cmd[:50]}"

        elif action_type == "seven_action":
            action = action_data.get("action", "")
            if not action:
                return False, "No action specified"

            try:
                import requests
                requests.post(
                    "http://127.0.0.1:7777/api/chat",
                    json={"text": action, "speaker_id": "default"},
                    timeout=5
                )
            except Exception:
                return False, "Seven not running"

            return True, f"Seven action: {action}"

        else:
            return False, f"Unknown action type: {action_type}"

    except Exception as e:
        return False, str(e)