"""
seven_utils/safe_call.py
Utility for calling functions that might fail without silent swallowing.

Usage:
    from seven_utils.safe_call import safe_call

    # Instead of:
    try:
        do_something()
    except Exception:
        pass

    # Use:
    safe_call(do_something, context="description of what this does")

    # Or with args:
    safe_call(do_something, args=(arg1, arg2), context="description")
"""

import logging
import traceback

_log = logging.getLogger('seven.safe_call')


def safe_call(fn, args=(), kwargs=None, context="", reraise=False, default=None):
    """
    Call a function and log any exception instead of swallowing it silently.

    Args:
        fn:       Function to call
        args:     Positional arguments
        kwargs:   Keyword arguments
        context:  Description for the log message
        reraise:  If True, re-raise the exception after logging
        default:  Return value if the call fails

    Returns:
        Function return value, or default on failure
    """
    if kwargs is None:
        kwargs = {}
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        label = context or fn.__name__ if hasattr(fn, '__name__') else str(fn)
        _log.warning(f"[safe_call] {label} failed: {type(e).__name__}: {e}")
        _log.debug(f"[safe_call] {label} traceback:\n{traceback.format_exc()}")
        if reraise:
            raise
        return default