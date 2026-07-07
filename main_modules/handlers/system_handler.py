"""
main_modules/handlers/system_handler.py

Handles ###SYS: tags emitted by brain.
Actions: volume, brightness, wifi, bluetooth, media, dark_mode,
         night_light, dnd, airplane, battery.

Skips execution if pre-executor already ran the tag before speaking.
"""

from colorama import Fore
from main_modules.handlers.base import BaseHandler


class SystemHandler(BaseHandler):
    tag_name = "SYS"

    def execute(self, response, ctx):
        # Skip if pre-executor already handled it
        if ctx.pre_executed_sys:
            return

        for params in self.extract_params(response):
            try:
                success, msg = ctx.system_mod.manage_system(params)

                if success:
                    ctx.update_status(f"System: {msg}", "#00ff00")

                    # Speak the result for query-type actions
                    action = params.get("action", "")
                    if action in ["battery", "volume_get", "brightness_get",
                                  "wifi_status", "bluetooth_status"] and msg:
                        if ctx.speak_with_interrupt:
                            ctx.speak_with_interrupt(msg)
                        else:
                            ctx.speak(msg)
                else:
                    ctx.speak(msg)
                    ctx.update_status(f"System failed: {msg}", "#ff0000")

            except Exception as e:
                print(Fore.RED + f"[SYS HANDLER] Error: {e}")
                import traceback
                traceback.print_exc()