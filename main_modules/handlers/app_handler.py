"""
main_modules/handlers/app_handler.py

Handles ###OPEN:, ###CLOSE:, ###SEARCH: tags.
Skips OPEN if pre-executor already launched (parallel execution).
Skips CLOSE if pre-executor already killed.
Always handles SEARCH.
"""

import re
import threading
from colorama import Fore
from main_modules.handlers.base import BaseHandler


class AppHandler(BaseHandler):
    tag_name = "OPEN"  # Not used — we override can_handle to catch all 3 tags

    def can_handle(self, response):
        if not isinstance(response, str):
            return False
        return ("###OPEN:" in response
                or "###CLOSE:" in response
                or "###SEARCH:" in response)

    def execute(self, response, ctx):
        try:
            import telemetry
            _telemetry = telemetry
        except ImportError:
            _telemetry = None

        # Build the regex based on what was pre-executed
        if ctx.pre_executed_open and ctx.pre_executed_close:
            commands = re.findall(r"###(SEARCH):\s*(.*?)(?=###|$)", response)
        elif ctx.pre_executed_open:
            commands = re.findall(r"###(CLOSE|SEARCH):\s*(.*?)(?=###|$)", response)
        elif ctx.pre_executed_close:
            commands = re.findall(r"###(OPEN|SEARCH):\s*(.*?)(?=###|$)", response)
        else:
            commands = re.findall(r"###(OPEN|CLOSE|SEARCH):\s*(.*?)(?=###|$)", response)

        for cmd_type, arg in commands:
            clean_arg = arg.replace('"', '').replace("'", "").replace(".", "").strip()
            if not clean_arg:
                continue

            # Normalize separators
            _normalized = clean_arg.replace(" and ", ",").replace(" & ", ",")
            sub_apps = [a.strip() for a in _normalized.split(",") if a.strip()]
            if not sub_apps:
                sub_apps = [clean_arg]

            if cmd_type == "OPEN":
                self._handle_open(sub_apps, ctx, _telemetry)
            elif cmd_type == "CLOSE":
                self._handle_close(sub_apps, ctx, _telemetry)
            elif cmd_type == "SEARCH":
                self._handle_search(sub_apps, ctx)

    def _handle_open(self, apps, ctx, telemetry_mod):
        if len(apps) > 1:
            def _open_one(name):
                if not name:
                    return
                ctx.core.open_app(name)
                if telemetry_mod:
                    telemetry_mod.log_activity()
            _threads = []
            for _app in apps:
                _t = threading.Thread(target=_open_one, args=(_app.strip(),), daemon=True)
                _t.start()
                _threads.append(_t)
            for _t in _threads:
                _t.join(timeout=5)
            ctx.update_status(f"Opened {len(apps)} apps", "#00ff00")
        else:
            app_name = apps[0]
            ctx.update_status(f"Opening: {app_name}", "#00ff00")
            if telemetry_mod:
                telemetry_mod.log_activity()

    def _handle_close(self, apps, ctx, telemetry_mod):
        _skip_words = {"me", "it", "this", "that", "the", "a", "an"}
        for app_name in apps:
            app_name = app_name.strip()
            if not app_name:
                continue
            if app_name.lower() in _skip_words:
                continue

            ctx.update_status(f"Closing: {app_name}", "#ff0000")

            def _close_and_report(name):
                success = ctx.core.close_app(name)
                if not success:
                    try:
                        ctx.mouth.speak(f"{name} is not running.")
                    except Exception:
                        pass

            threading.Thread(
                target=_close_and_report,
                args=(app_name,),
                daemon=True
            ).start()
            if telemetry_mod:
                telemetry_mod.log_activity()

    def _handle_search(self, apps, ctx):
        for app_name in apps:
            app_name = app_name.strip()
            if app_name:
                ctx.update_status(f"Searching: {app_name}", "#0000ff")
                ctx.core.search_web(app_name)