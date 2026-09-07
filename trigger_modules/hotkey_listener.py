"""
trigger_modules/hotkey_listener.py
Global hotkey listener using pynput low-level keyboard hook.

Windows low-level keyboard hooks require the installing thread to
pump messages continuously. A keepalive thread handles this.
"""
import time
import threading

from trigger_modules.normalization import normalize_hotkey
from trigger_modules.executor import execute_trigger


class HotkeyListener:
    def __init__(self):
        self._triggers        = []
        self._hotkey_map      = {}
        self._pressed_keys    = set()
        self._listener        = None
        self._running         = False
        self._last_fire       = 0
        self._mod_reset_timer = None

    def reload(self, triggers):
        self._triggers   = triggers
        self._hotkey_map = {}
        for t in triggers:
            hk = t.get("hotkey")
            if hk:
                normalized = normalize_hotkey(hk)
                self._hotkey_map[normalized] = t
                print(f"[HOTKEY] Mapped: '{hk}' -> '{normalized}' "
                      f"-> '{t.get('name')}'")
        print(f"[HOTKEY] {len(self._hotkey_map)} hotkeys active")

    def start(self):
        if self._running:
            return
        self._running = True

        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    name = self._key_name(key)
                    if not name:
                        return
                    self._pressed_keys.add(name)
                    self._check_combo()
                    self._schedule_reset()
                except Exception:
                    pass

            def on_release(key):
                try:
                    name = self._key_name(key)
                    if name:
                        self._pressed_keys.discard(name)
                except Exception:
                    pass

            self._listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
                suppress=False,
            )
            self._listener.daemon = True
            self._listener.start()
            print("[HOTKEY] Listener started via pynput engine")

            # Windows low-level keyboard hooks require the installing
            # thread to pump messages continuously. If the thread blocks
            # for more than 5 seconds, Windows silently removes the hook.
            threading.Thread(
                target=self._message_pump_keepalive,
                daemon=True,
                name="HotkeyMessagePump"
            ).start()

        except ImportError:
            print("[HOTKEY] pynput not installed — hotkeys disabled")
        except Exception as e:
            print(f"[HOTKEY] Start failed: {e}")

    def _message_pump_keepalive(self):
        """
        Pump Windows messages to keep low-level keyboard hook alive.
        """
        try:
            import ctypes
            _user32 = ctypes.windll.user32
            _MSG    = ctypes.wintypes.MSG

            while self._running:
                msg = _MSG()
                while _user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, 0x0001  # PM_REMOVE
                ):
                    _user32.TranslateMessage(ctypes.byref(msg))
                    _user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.1)

        except Exception as e:
            print(f"[HOTKEY] Message pump error: {e}")

    def stop(self):
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _key_name(self, key):
        """Convert any pynput key to a normalized string name."""
        from pynput import keyboard as kb

        # Named special keys
        if isinstance(key, kb.Key):
            _map = {
                kb.Key.ctrl_l: "ctrl", kb.Key.ctrl_r: "ctrl",
                kb.Key.shift_l: "shift", kb.Key.shift_r: "shift",
                kb.Key.alt_l: "alt", kb.Key.alt_r: "alt",
                kb.Key.alt_gr: "alt",
                kb.Key.cmd: "win", kb.Key.cmd_l: "win", kb.Key.cmd_r: "win",
                kb.Key.space: "space", kb.Key.enter: "enter",
                kb.Key.tab: "tab", kb.Key.esc: "esc",
                kb.Key.backspace: "backspace", kb.Key.delete: "delete",
                kb.Key.home: "home", kb.Key.end: "end",
                kb.Key.page_up: "pageup", kb.Key.page_down: "pagedown",
                kb.Key.up: "up", kb.Key.down: "down",
                kb.Key.left: "left", kb.Key.right: "right",
                kb.Key.insert: "insert", kb.Key.menu: "menu",
                kb.Key.caps_lock: "capslock", kb.Key.num_lock: "numlock",
            }
            for i in range(1, 25):
                fk = getattr(kb.Key, f"f{i}", None)
                if fk:
                    _map[fk] = f"f{i}"
            return _map.get(key)

        # Virtual key code — most reliable when modifiers are held
        vk = getattr(key, 'vk', None)
        if vk is not None:
            if 65 <= vk <= 90:
                return chr(vk).lower()
            if 48 <= vk <= 57:
                return str(vk - 48)
            if 96 <= vk <= 105:
                return f"num{vk - 96}"
            _sym = {
                186: ";", 187: "=", 188: ",", 189: "-", 190: ".",
                191: "/", 192: "`", 219: "[", 220: "\\",
                221: "]", 222: "'",
            }
            if vk in _sym:
                return _sym[vk]

        # Character fallback — handles Shift+1 = '!' etc.
        ch = getattr(key, 'char', None)
        if ch and isinstance(ch, str) and len(ch) == 1 and ch.isprintable():
            return ch.lower()

        return None

    def _check_combo(self):
        """Check if currently pressed keys match any registered hotkey."""
        now = time.time()
        if now - self._last_fire < 0.3:
            return

        MODIFIERS = {"ctrl", "shift", "alt", "win"}
        mods = sorted(k for k in self._pressed_keys if k in MODIFIERS)
        keys = sorted(k for k in self._pressed_keys if k not in MODIFIERS)

        raw_combo = "+".join(mods + keys)
        if not raw_combo:
            return

        combo = normalize_hotkey(raw_combo)
        trigger = self._hotkey_map.get(combo)

        if trigger:
            self._last_fire = now
            self._pressed_keys.clear()
            print(f"[HOTKEY] FIRED: {combo} -> {trigger['name']}")

            # Extract the non-modifier key from the combo
            _mods_set = {"ctrl", "shift", "alt", "win"}
            _combo_parts = combo.split("+")
            _trigger_key = next(
                (p for p in _combo_parts if p not in _mods_set), ""
            )

            _trigger_with_key = dict(trigger)
            _trigger_with_key["_fired_key"] = _trigger_key

            threading.Thread(
                target=execute_trigger,
                args=(_trigger_with_key,),
                daemon=True,
            ).start()

    def _schedule_reset(self):
        """Clear pressed keys after 3s inactivity — prevents stuck state."""
        if self._mod_reset_timer:
            self._mod_reset_timer.cancel()
        self._mod_reset_timer = threading.Timer(3.0, self._reset_keys)
        self._mod_reset_timer.daemon = True
        self._mod_reset_timer.start()

    def _reset_keys(self):
        if self._pressed_keys:
            self._pressed_keys.clear()