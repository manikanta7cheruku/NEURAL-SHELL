"""
main_modules/handlers/__init__.py
Handler registry and dispatcher.

All ###TAG: handlers register here.
main.py calls execute_all(response, ctx) to run all applicable handlers.

ORDER MATTERS:
  WindowHandler runs first (title bar changes may affect other handlers)
  TaskHandler before ScheduleHandler (tasks may reference schedules)
  ScheduleHandler
  SystemHandler
  AppHandler last (opens/closes windows other handlers may reference)
"""

from colorama import Fore

HANDLER_REGISTRY = []


def register_all(ctx):
    """
    Register all handlers with the given context.
    Called once at Seven startup from main.py.
    """
    global HANDLER_REGISTRY

    from main_modules.handlers.window_handler   import WindowHandler
    from main_modules.handlers.task_handler     import TaskHandler
    from main_modules.handlers.schedule_handler import ScheduleHandler
    from main_modules.handlers.system_handler   import SystemHandler
    from main_modules.handlers.app_handler      import AppHandler

    HANDLER_REGISTRY = [
        WindowHandler(),
        TaskHandler(),
        ScheduleHandler(),
        SystemHandler(),
        AppHandler(),
    ]

    print(Fore.CYAN + f"[HANDLERS] Registered {len(HANDLER_REGISTRY)} handlers")


def execute_all(response, ctx):
    """
    Dispatch response to all handlers that can handle it.
    Each handler decides internally if it applies to this response.
    """
    if not isinstance(response, str):
        return

    for handler in HANDLER_REGISTRY:
        try:
            if handler.can_handle(response):
                handler.execute(response, ctx)
        except Exception as e:
            print(Fore.RED + f"[HANDLER {handler.tag_name}] Error: {e}")
            import traceback
            traceback.print_exc()