"""
ears/push_to_talk.py
The push-to-talk key: Seven hears you only while you hold Shift.

A keyboard listener (pynput) watches Shift. The mic stream asks is_held() every 32 ms frame: holding Shift starts an
utterance and letting go ends it (ears/stream.py), so there is no waiting for a pause.

Shift is also how capitals are typed, so a Shift held together with any other key is typing, not talking: that hold
doesn't count until Shift is released and pressed again on its own.
"""

import threading

from colorama import Fore

_lock = threading.Lock()
_listener = None
_shift_down = False
_typing = False            # another key was pressed during this Shift hold


def is_held() -> bool:
    """True while Shift is held on its own."""
    with _lock:
        return _shift_down and not _typing


def _pressed(is_shift: bool):
    global _shift_down, _typing
    with _lock:
        if is_shift:
            if not _shift_down:
                _typing = False
            _shift_down = True
        elif _shift_down:
            _typing = True


def _released(is_shift: bool):
    global _shift_down, _typing
    if is_shift:
        with _lock:
            _shift_down = False
            _typing = False


def start():
    """Start the keyboard listener. Called once at startup; does nothing if it is already running."""
    global _listener
    if _listener is not None:
        return
    try:
        from pynput import keyboard
        shifts = (keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.shift_l)

        _listener = keyboard.Listener(on_press=lambda key: _pressed(key in shifts),
                                      on_release=lambda key: _released(key in shifts))
        _listener.daemon = True
        _listener.start()
        print(Fore.GREEN + "[PTT] Keyboard listener started")
    except ImportError:
        print(Fore.YELLOW + "[PTT] pynput not installed: push to talk unavailable")
    except Exception as e:
        print(Fore.YELLOW + f"[PTT] Failed to start: {e}")


def stop():
    global _listener
    if _listener:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None
