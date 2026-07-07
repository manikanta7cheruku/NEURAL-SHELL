"""
main_modules/handlers/window_handler.py

Handles ###WINDOW: tags.
Actions: focus, minimize, maximize, snap, layout, close, transparent, pin, etc.
"""

from colorama import Fore
from main_modules.handlers.base import BaseHandler


class WindowHandler(BaseHandler):
    tag_name = "WINDOW"

    def execute(self, response, ctx):
        for params in self.extract_params(response):
            try:
                success, msg = ctx.hands_windows.manage_window(params)

                if success:
                    ctx.update_status(f"Window: {msg}", "#00ff00")

                    # Speak the list result if no other speech happened
                    if params.get("action") == "list" and msg and not ctx.speech_part:
                        if ctx.speak_with_interrupt:
                            ctx.speak_with_interrupt(msg)
                        else:
                            ctx.speak(msg)
                else:
                    if not ctx.speech_part:
                        ctx.speak(msg)
                    ctx.update_status(f"Window failed: {msg}", "#ff0000")

            except Exception as e:
                print(Fore.RED + f"[WINDOW HANDLER] Error: {e}")
                import traceback
                traceback.print_exc()