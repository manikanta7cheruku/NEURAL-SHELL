"""
main_modules/handlers/__init__.py
Handler registry and dispatcher.

All ###TAG: handlers register here.
main.py calls execute_all(response, ctx) to run all applicable handlers.
"""

from colorama import Fore

# Registry populated by register_all() after handlers are imported
HANDLER_REGISTRY = []


def register_all(ctx):
    """
    Register all handlers with the given context.
    Called once at Seven startup from main.py.
    """
    global HANDLER_REGISTRY

    # Handlers will be added here as we extract them one by one
    # For now, empty registry — nothing to dispatch yet
    HANDLER_REGISTRY = []

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