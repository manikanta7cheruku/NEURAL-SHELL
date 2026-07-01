"""
ears/push_to_talk.py
Seven — Push to Talk keyboard gate.

Monitors Shift key state in background daemon thread.
main.py reads is_ptt_active() to decide if audio should be processed.

Design: pynput keyboard listener runs continuously.
        When Shift is held: _ptt_active = True
        When Shift released: _ptt_active = False
        main.py checks is_ptt_active() after every listen() call.
        If PTT enabled and Shift not held: audio discarded immediately.
        No Whisper, no brain, no RMS — pure gate, sub-millisecond check.
"""

import threading
from colorama import Fore

_ptt_active = False
_ptt_lock   = threading.Lock()
_listener   = None
_enabled    = False


def is_ptt_active() -> bool:
    """
    Returns True if audio should be processed.
    - PTT disabled: always True (pass all audio)
    - PTT enabled + Shift held: True
    - PTT enabled + Shift not held: False
    """
    if not _enabled:
        return True
    with _ptt_lock:
        return _ptt_active


def set_enabled(enabled: bool):
    global _enabled
    _enabled = enabled
    print(Fore.CYAN + f"[PTT] Push to talk {'enabled — hold Shift to speak' if enabled else 'disabled'}")


def start():
    """Start keyboard listener. Called once at Seven startup."""
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
        print(Fore.GREEN + "[PTT] Keyboard listener started")

    except ImportError:
        print(Fore.YELLOW + "[PTT] pynput not installed — push to talk unavailable")
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