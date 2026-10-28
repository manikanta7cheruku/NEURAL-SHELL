"""
seven_utils/event_loop.py
The event loop Seven's local API runs on.

On Windows, Python's default (proactor) loop closes a server's listening socket for good after ONE failed accept
("[WinError 64] The specified network name is no longer available", logged as "Accept failed on a socket"). That
happens when a client drops a connection the instant it opens it, as the app, Vite and Electron all do while polling a
backend that is still starting, and the app then shows "Backend Unreachable" while Seven keeps running. The selector
loop shrugs that off.

Kept in its own tiny module so tests can check it without importing the whole API (and its dependencies).
"""
import asyncio
import os


def new_event_loop() -> asyncio.AbstractEventLoop:
    """A selector loop on Windows, the platform default elsewhere."""
    return asyncio.SelectorEventLoop() if os.name == "nt" else asyncio.new_event_loop()
