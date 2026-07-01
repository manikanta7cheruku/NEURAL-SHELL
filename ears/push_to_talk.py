"""
ears/push_to_talk.py
Seven — Push to Talk keyboard gate.

Monitors Shift key state in background thread.
main.py reads _ptt_active to decide if audio should be processed.

WHY SHIFT:
    Shift is held comfortably while speaking.
    Does not conflict with normal typing.
    Both left and right Shift work.
    Future: user can configure any key via Settings.
"""

import threading
from colorama import Fore

_ptt_active = False   # True when Shift is held
_ptt_lock   = threading.Lock()
_listener   = None
_enabled    = False   # Set by main.py from config


def is_ptt_active() -> bool:
    """Returns True if Shift is currently held (or PTT is disabled)."""
    if not _enabled:
        return True   # PTT disabled = always active
    with _ptt_lock:
        return _ptt_active


def set_enabled(enabled: bool):
    """Called by main.py when config changes."""
    global _enabled
    _enabled = enabled
    print(Fore.CYAN + f"[PTT] Push to talk {'enabled' if enabled else 'disabled'}")


def start():
    """Start keyboard listener in background daemon thread."""
    global _listener
    try:
        from pynput import keyboard

        def _on_press(key):
            global _ptt_active
            if key in (keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.shift_l):
                with _ptt_lock:
                    _ptt_active = True

        def _on_release(key):
            global _ptt_active
            if key in (keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.shift_l):
                with _ptt_lock:
                    _ptt_active = False

        _listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        _listener.daemon = True
        _listener.start()
        print(Fore.GREEN + "[PTT] Keyboard listener started (Shift = push to talk)")

    except ImportError:
        print(Fore.YELLOW + "[PTT] pynput not installed — push to talk unavailable")
    except Exception as e:
        print(Fore.YELLOW + f"[PTT] Keyboard listener failed: {e}")


def stop():
    """Stop keyboard listener."""
    global _listener
    if _listener:
        try:
            _listener.stop()
        except Exception:
            pass
        _listener = None