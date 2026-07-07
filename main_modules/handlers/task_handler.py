"""
main_modules/handlers/task_handler.py

Handles ###TASK: tags for create, list, complete, delete actions.
Communicates with Seven API on 127.0.0.1:7777.
Writes panel trigger file for LIST action to open task panel.
"""

import os
import requests
from colorama import Fore
from main_modules.handlers.base import BaseHandler


class TaskHandler(BaseHandler):
    tag_name = "TASK"

    def execute(self, response, ctx):
        for params in self.extract_params(response):
            action = params.get("action", "")

            try:
                if action == "create":
                    self._handle_create(params, ctx)
                elif action == "list":
                    self._handle_list(params, ctx)
                elif action == "complete":
                    self._handle_complete(params, ctx)
                elif action == "delete":
                    self._handle_delete(params, ctx)

            except Exception as e:
                print(Fore.RED + f"[TASK HANDLER] Error: {e}")
                import traceback
                traceback.print_exc()
                ctx.mouth.speak("Something went wrong with the task system.")

    def _handle_create(self, params, ctx):
        text     = params.get("text", "").replace("|||", " ").replace("_", " ")
        priority = params.get("priority", "medium")
        due_raw  = params.get("due", "").replace("|||", " ").replace("_", " ")

        # Resolve natural language due date to ISO string
        due_date = None
        if due_raw:
            try:
                from datetime import date, timedelta
                dl = due_raw.lower()
                if "today" in dl or "tonight" in dl:
                    due_date = date.today().isoformat()
                elif "tomorrow" in dl:
                    due_date = (date.today() + timedelta(days=1)).isoformat()
                else:
                    from hands.scheduler import _parse_time
                    parsed = _parse_time(due_raw)
                    if parsed:
                        due_date = parsed.date().isoformat()
            except Exception as _due_err:
                print(Fore.YELLOW + f"[TASKS] Due date parse failed: {_due_err}")

        payload = {"text": text, "priority": priority}
        if due_date:
            payload["due_date"] = due_date

        r = requests.post(
            "http://127.0.0.1:7777/api/tasks",
            json=payload,
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            stats = requests.get(
                "http://127.0.0.1:7777/api/tasks/stats", timeout=3
            ).json()
            pending = stats.get("pending", 0)
            count_str = (
                f"You now have {pending} pending task{'s' if pending != 1 else ''}."
                if pending > 0 else ""
            )

            if ctx.speech_part and "adding" in ctx.speech_part.lower():
                extra = f" {count_str}" if count_str else ""
                if extra:
                    ctx.mouth.speak(extra)
            else:
                confirm = f"Task added. {count_str}"
                ctx.mouth.speak(confirm)

            if ctx.api_set_state:
                ctx.api_set_state("task_results", {
                    "action":  "created",
                    "task":    data.get("task"),
                    "pending": pending
                })
            ctx.update_status("Task added", "#00ff00")
            print(Fore.GREEN + f"[TASKS] Created: {text}")
        else:
            print(Fore.RED + f"[TASKS] Create failed: {r.status_code}")
            ctx.mouth.speak("I could not add that task. Try again.")

    def _handle_list(self, params, ctx):
        filter_val = params.get("filter", "all")
        endpoint = (
            "http://127.0.0.1:7777/api/tasks/today"
            if filter_val == "today"
            else "http://127.0.0.1:7777/api/tasks?status=pending"
        )
        r = requests.get(endpoint, timeout=5)
        if r.status_code != 200:
            return

        tasks = r.json()
        count = len(tasks)

        if count == 0:
            msg = ("No tasks due today." if filter_val == "today"
                   else "You have no pending tasks.")
            ctx.mouth.speak(msg)
        elif count == 1:
            t = tasks[0]
            ctx.mouth.speak(
                f"One task: {t['text']}."
                + (f" Due today." if t.get("due_date") else "")
            )
        elif count <= 3:
            names = ", ".join(t["text"][:30] for t in tasks)
            ctx.mouth.speak(f"{count} tasks: {names}.")
        else:
            top = tasks[0]
            ctx.mouth.speak(
                f"{count} pending tasks. "
                f"Top priority: {top['text'][:40]}. "
                f"Full list is in the chat."
            )

        if ctx.api_set_state:
            ctx.api_set_state("task_results", {
                "action": "list",
                "tasks":  tasks,
                "filter": filter_val
            })
        ctx.update_status(f"Tasks: {count} pending", "#00ccff")

        # Trigger task panel to open
        try:
            import json as _pj
            panel_trigger = os.path.join(
                os.environ.get('APPDATA', ''),
                'SEVEN', 'panel_trigger.json'
            )
            os.makedirs(os.path.dirname(panel_trigger), exist_ok=True)
            with open(panel_trigger, 'w') as pf:
                _pj.dump({"reason": "voice", "tasks": tasks}, pf)
            print(Fore.CYAN + "[TASKS] Panel trigger written")
        except Exception as _pt_err:
            print(Fore.YELLOW + f"[TASKS] Panel trigger failed: {_pt_err}")

    def _handle_complete(self, params, ctx):
        search = params.get("search", "").replace("|||", " ").replace("_", " ")

        try:
            from backend.routes.tasks import db_find_task_by_text
            found = db_find_task_by_text(search)
        except Exception:
            found = None

        if not found:
            ctx.mouth.speak(
                f"Could not find a task matching '{search}'. "
                f"Say 'show my tasks' to see the list."
            )
            return

        r = requests.put(
            f"http://127.0.0.1:7777/api/tasks/{found['id']}",
            json={"completed": True},
            timeout=5
        )
        if r.status_code == 200:
            stats = requests.get(
                "http://127.0.0.1:7777/api/tasks/stats", timeout=3
            ).json()
            pending = stats.get("pending", 0)
            ctx.mouth.speak(
                f"Marked complete. "
                f"{pending} task{'s' if pending != 1 else ''} remaining."
            )
            if ctx.api_set_state:
                ctx.api_set_state("task_results", {
                    "action":  "completed",
                    "task_id": found["id"],
                    "pending": pending
                })
            ctx.update_status("Task completed", "#00ff00")
        else:
            ctx.mouth.speak("Could not mark that complete. Try again.")

    def _handle_delete(self, params, ctx):
        search = params.get("search", "").replace("|||", " ").replace("_", " ")

        try:
            from backend.routes.tasks import db_find_task_by_text
            found = db_find_task_by_text(search)
        except Exception:
            found = None

        if not found:
            ctx.mouth.speak(f"Could not find a task matching '{search}'.")
            return

        r = requests.delete(
            f"http://127.0.0.1:7777/api/tasks/{found['id']}",
            timeout=5
        )
        if r.status_code == 200:
            ctx.mouth.speak(f"Removed: {found['text'][:40]}.")
            if ctx.api_set_state:
                ctx.api_set_state("task_results", {
                    "action":  "deleted",
                    "task_id": found["id"]
                })
            ctx.update_status("Task removed", "#ff6600")
        else:
            ctx.mouth.speak("Could not remove that task.")