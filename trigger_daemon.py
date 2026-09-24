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

# Ensure project root and SEVEN_APP_PATH are at index 0 in sys.path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_app_path = os.environ.get("SEVEN_APP_PATH", "")

for _p in [_app_path, _this_dir]:
    if _p and os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# Import config first — triggers logging, console hiding, UTF-8 setup
from trigger_modules.config import setup_logging, is_seven_running  # noqa
from trigger_modules.lock import acquire_lock, release_lock
from trigger_modules.database import load_triggers
from trigger_modules.overlay import ensure_overlay_alive_safe, is_overlay_alive
from trigger_modules.hotkey_listener import HotkeyListener
from trigger_modules.audio_listener import AudioListener
from trigger_modules.voice_listener import VoiceListener
from trigger_modules.reload_poller import ReloadPoller

_tab_listener_proc = None


def _offline_tab_listener_supervisor():
    """
    Background supervisor thread:
    Ensures offline_tab_listener.py is active on port 7777 ONLY when Seven's
    main backend is genuinely closed — never while it's mid-startup.

    BUG FIX (found after main.py started crash-looping with "Port 7777 is
    still in use"): the original version polled port 7777 every 2s and
    spawned offline_tab_listener.py the instant it saw the port unoccupied.
    Since trigger_daemon.py runs independently and survives Seven closing
    by design, this supervisor was ALWAYS alive in the background — so
    every main.py restart (including a normal one, and especially the
    5s-interval crash-retry loop) had a window where port 7777 was
    briefly free, which this supervisor won the race for almost every
    time, permanently blocking main.py's own bind attempt. Fixed with:
    (a) requiring several consecutive "closed" readings, spaced out, before
    treating the port as genuinely free — a brief restart blip no longer
    looks like "Seven is closed" — and (b) tearing down the fallback
    listener immediately the moment the real backend reclaims the port,
    instead of leaving it running indefinitely as a silent contender.
    """
    global _tab_listener_proc
    import socket
    import subprocess

    CONSECUTIVE_CLOSED_REQUIRED = 4   # 4 x 2s = 8s of confirmed silence
    POLL_INTERVAL = 2.0

    consecutive_closed = 0

    while True:
        try:
            port_open = False
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.1)
                res = s.connect_ex(("127.0.0.1", 7777))
                s.close()
                port_open = (res == 0)
            except Exception:
                port_open = False

            if port_open:
                consecutive_closed = 0
                # Real backend (or anything) has the port now. If our own
                # fallback listener is still running, it's redundant and
                # will fight the next legitimate restart — tear it down.
                if _tab_listener_proc is not None and _tab_listener_proc.poll() is None:
                    try:
                        _tab_listener_proc.terminate()
                        _tab_listener_proc.wait(timeout=3)
                    except Exception:
                        try:
                            _tab_listener_proc.kill()
                        except Exception:
                            pass
                    _tab_listener_proc = None
                    print("[TRIGGER DAEMON] Port 7777 reclaimed by main backend — offline tab listener stopped")
            else:
                consecutive_closed += 1
                already_running = (
                    _tab_listener_proc is not None
                    and _tab_listener_proc.poll() is None
                )
                if not already_running and consecutive_closed >= CONSECUTIVE_CLOSED_REQUIRED:
                    base_dir = os.environ.get(
                        "SEVEN_APP_PATH",
                        os.path.dirname(os.path.abspath(__file__))
                    )
                    script_path = os.path.join(
                        base_dir, "hands", "workspace_modules", "offline_tab_listener.py"
                    )
                    if os.path.isfile(script_path):
                        py_exe = sys.executable
                        if "python.exe" in py_exe.lower():
                            pw_exe = py_exe.lower().replace("python.exe", "pythonw.exe")
                            if os.path.isfile(pw_exe):
                                py_exe = pw_exe

                        _tab_listener_proc = subprocess.Popen(
                            [py_exe, script_path],
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        print(f"[TRIGGER DAEMON] Port 7777 confirmed closed for "
                              f"{CONSECUTIVE_CLOSED_REQUIRED * POLL_INTERVAL:.0f}s — "
                              f"starting offline tab listener")
        except Exception:
            pass

        time.sleep(POLL_INTERVAL)


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

    # Supervise offline tab listener for 24/7 Chrome sync
    threading.Thread(
        target=_offline_tab_listener_supervisor, daemon=True
    ).start()

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