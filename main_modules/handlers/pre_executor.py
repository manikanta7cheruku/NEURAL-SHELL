"""
main_modules/handlers/pre_executor.py

Runs SYS, OPEN, CLOSE and WINDOW tags BEFORE Seven speaks.
This way the app is already launching (or the window already in front) while the user hears the confirmation:
"show Chrome" brings Chrome forward at once instead of after Seven finishes saying "Chrome".
Sets flags on ctx so main handlers skip re-running these tags.
"""

import re
import threading
from colorama import Fore


def pre_execute(response, ctx):
    """
    Pre-execute SYS, OPEN, CLOSE tags before speech.
    Updates ctx flags: pre_executed_sys, pre_executed_open, pre_executed_close, pre_executed_window.
    """
    if not isinstance(response, str):
        ctx.pre_executed_window = False
        return

    _pre_execute_window(response, ctx)
    _pre_execute_sys(response, ctx)
    _pre_execute_open(response, ctx)
    _pre_execute_close(response, ctx)


def _pre_execute_window(response, ctx):
    """Window actions (focus, minimize, snap...) are quick and silent: do them now. "list" speaks, so it waits."""
    ctx.pre_executed_window = False
    if "###WINDOW:" not in response:
        return
    from main_modules.handlers.window_handler import WindowHandler
    handler = WindowHandler()
    params = [p for p in handler.extract_params(response) if p.get("action") != "list"]
    if not params or len(params) != len(handler.extract_params(response)):
        return
    ctx.pre_executed_window = True
    threading.Thread(target=handler.run, args=(response, ctx), daemon=True, name="PreExecWindow").start()


def _pre_execute_sys(response, ctx):
    ctx.pre_executed_sys = False
    if "###SYS:" not in response:
        return

    sys_matches = re.findall(r"###SYS:\s*(.*?)(?=###|$)", response)
    for match in sys_matches:
        params = {}
        for pair in match.strip().split():
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v
        if params:
            try:
                ctx.system_mod.manage_system(params)
                ctx.pre_executed_sys = True
            except Exception as e:
                print(Fore.RED + f"[PRE-EXEC] SYS error: {e}")


def _pre_execute_open(response, ctx):
    ctx.pre_executed_open = False
    if "###OPEN:" not in response:
        return

    opens = re.findall(r"###OPEN:\s*(.*?)(?=###|$)", response)
    for app in opens:
        app = app.strip().replace('"', '').replace("'", "")
        if app:
            threading.Thread(
                target=ctx.core.open_app,
                args=(app,),
                daemon=True
            ).start()
            ctx.pre_executed_open = True


def _pre_execute_close(response, ctx):
    ctx.pre_executed_close = False
    if "###CLOSE:" not in response:
        return

    closes = re.findall(r"###CLOSE:\s*(.*?)(?=###|$)", response)
    for app in closes:
        app = app.strip().replace('"', '').replace("'", "")
        if app:
            threading.Thread(
                target=ctx.core.close_app,
                args=(app,),
                daemon=True
            ).start()
            ctx.pre_executed_close = True