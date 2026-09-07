"""
=============================================================================
trigger_daemon.py — Thin entry point.

Independent background process for trigger activation.
Runs even when Seven UI is fully closed.

All logic lives in trigger_modules/ (same pattern as main.py → main_modules/).

RESPONSIBILITIES (delegated to modules):
  trigger_modules.hotkey_listener  → Global keyboard hooks
  trigger_modules.voice_listener   → "Seven [word]" detection via Whisper
  trigger_modules.audio_listener   → Snap/clap detection via YAMNet
  trigger_modules.executor         → Trigger action execution
  trigger_modules.overlay          → TCP 7891 overlay communication
  trigger_modules.database         → SQLite trigger DB access
  trigger_modules.lock             → Single-instance mutex
  trigger_modules.reload_poller    → DB change watcher
=============================================================================
"""
import sys
import os
import time
import threading

# Ensure project root is in path BEFORE importing modules
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Import config first — triggers logging, console hiding, UTF-8 setup
from trigger_modules.config import setup_logging, is_seven_running  # noqa
from trigger_modules.lock import acquire_lock, release_lock
from trigger_modules.database import load_triggers
from trigger_modules.overlay import ensure_overlay_alive_safe, is_overlay_alive
from trigger_modules.hotkey_listener import HotkeyListener
from trigger_modules.audio_listener import AudioListener
from trigger_modules.voice_listener import VoiceListener
from trigger_modules.reload_poller import ReloadPoller


def main():
    if not acquire_lock():
        return

    print("[TRIGGER DAEMON] Starting...")

    # Load initial triggers
    triggers = load_triggers()
    print(f"[TRIGGER DAEMON] Loaded {len(triggers)} active triggers")

    # Initialize listeners
    hotkey_listener = HotkeyListener()
    audio_listener  = AudioListener()
    voice_listener  = VoiceListener()

    # Single reload function — wires all three listeners
    def reload_all():
        nonlocal triggers
        triggers = load_triggers()
        hotkey_listener.reload(triggers)
        audio_listener.reload(triggers)
        voice_listener.reload()
        print(f"[TRIGGER DAEMON] Reloaded: {len(triggers)} triggers")

    reload_poller = ReloadPoller(on_reload=reload_all)

    # Load triggers into listeners
    hotkey_listener.reload(triggers)
    audio_listener.reload(triggers)

    # Pre-warm overlay daemon
    threading.Thread(
        target=ensure_overlay_alive_safe, daemon=True
    ).start()

    # Pre-load heavy modules so first trigger fires instantly
    def _preload():
        try:
            import hands.workspace
            import hands.system
            import hands.core
            print("[TRIGGER DAEMON] Modules pre-loaded")
        except Exception:
            pass

    threading.Thread(target=_preload, daemon=True).start()

    # Start all listeners
    hotkey_listener.start()
    audio_listener.start()
    voice_listener.start()
    reload_poller.start()

    print("[TRIGGER DAEMON] All listeners active. Waiting for triggers...")

    # Health check loop
    _hotkey_fail_streak = 0
    _last_health_log    = time.time()

    try:
        while True:
            time.sleep(30)

            # Overlay health check
            if not is_overlay_alive():
                print("[TRIGGER DAEMON] Overlay daemon down — respawning...")
                threading.Thread(
                    target=ensure_overlay_alive_safe,
                    daemon=True
                ).start()

            # Hotkey listener health check
            _listener_obj   = hotkey_listener._listener
            _listener_alive = (
                _listener_obj is not None and
                getattr(_listener_obj, 'running', False) == True
            )

            if not _listener_alive:
                _hotkey_fail_streak += 1
                print(
                    f"[TRIGGER DAEMON] Hotkey check: not running "
                    f"(streak={_hotkey_fail_streak}/3)"
                )
                if _hotkey_fail_streak >= 3:
                    print(
                        "[TRIGGER DAEMON] Hotkey listener confirmed dead "
                        "— restarting"
                    )
                    try:
                        hotkey_listener.stop()
                        time.sleep(1.0)
                        hotkey_listener.start()
                        hotkey_listener.reload(triggers)
                        _hotkey_fail_streak = 0
                        print("[TRIGGER DAEMON] Hotkey listener restarted")
                    except Exception as _re:
                        print(
                            f"[TRIGGER DAEMON] Listener restart failed: {_re}"
                        )
                        print(
                            "[TRIGGER DAEMON] Exiting for Task Scheduler "
                            "restart"
                        )
                        sys.exit(1)
            else:
                _hotkey_fail_streak = 0

            # Voice listener health check
            if not voice_listener.is_alive() and voice_listener._phrase_map:
                print(
                    "[TRIGGER DAEMON] Voice listener stopped — restarting"
                )
                voice_listener = VoiceListener()
                voice_listener.start()

            # Heartbeat every 30 minutes
            if time.time() - _last_health_log > 1800:
                print(
                    f"[TRIGGER DAEMON] Heartbeat — "
                    f"hotkeys: {len(hotkey_listener._hotkey_map)}, "
                    f"overlay: {'up' if is_overlay_alive() else 'down'}, "
                    f"voice_phrases: {len(voice_listener._phrase_map)}"
                )
                _last_health_log = time.time()

    except KeyboardInterrupt:
        print("[TRIGGER DAEMON] Stopping...")
        hotkey_listener.stop()
        audio_listener.stop()
        voice_listener.stop()
        reload_poller.stop()
        release_lock()
        print("[TRIGGER DAEMON] Stopped.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[TRIGGER DAEMON] Interrupted by user")
    except Exception as _crash:
        import traceback
        print(f"[TRIGGER DAEMON] FATAL CRASH: {_crash}")
        traceback.print_exc()
        try:
            release_lock()
        except Exception:
            pass
        sys.exit(1)
    finally:
        release_lock()