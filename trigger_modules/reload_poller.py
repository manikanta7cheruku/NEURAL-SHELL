"""
trigger_modules/reload_poller.py
Watches for trigger_reload.signal file to refresh triggers.
Backend writes this file whenever a trigger is created/updated/deleted.
"""
import os
import time
import threading

from trigger_modules.config import RELOAD_SIGNAL


class ReloadPoller:
    def __init__(self, on_reload):
        self._on_reload = on_reload
        self._running   = False
        self._thread    = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        print("[RELOAD] DB change poller started")

    def stop(self):
        self._running = False

    def _poll(self):
        while self._running:
            try:
                if os.path.exists(RELOAD_SIGNAL):
                    os.remove(RELOAD_SIGNAL)
                    print("[RELOAD] Signal detected — reloading triggers")
                    self._on_reload()
            except Exception:
                pass
            time.sleep(2)