"""
=============================================================================
trigger_daemon.py

Independent background process for trigger activation.
Runs even when Seven UI is fully closed.

RESPONSIBILITIES:
  1. Global hotkey listener (keyboard hooks)
  2. Voice trigger listener ("Seven [word]" detection via Whisper)
  3. Audio trigger listener (snap/clap detection via YAMNet)
  4. Trigger execution (launches apps, restores workspaces)
  5. Reload triggers when DB changes (via signal file)

LIFECYCLE:
  Spawned by main.py at startup as detached process
  Registered in Windows Task Scheduler for auto-start at login
  Survives Seven quit (detached, independent)
  Single instance enforced via mutex

PROCESS ARCHITECTURE:
  Main thread: hotkey listener (blocking keyboard hook)
  Thread 2: voice listener (Whisper STT)
  Thread 3: audio listener (YAMNet classifier)
  Thread 4: DB reload poller

COMMUNICATION:
  Reads: seven_data/triggers.db (SQLite WAL)
  Reads: seven_data/trigger_reload.signal (daemon reloads triggers)
  Checks: port 7777 to know if Seven is running
=============================================================================
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import threading
from datetime import datetime

# Force hidden console on Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0
        )
    except Exception:
        pass

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

APPDATA      = os.environ.get('APPDATA', os.path.expanduser('~'))
SEVEN_DATA   = os.path.join(APPDATA, 'SEVEN', 'seven_data')
TRIGGERS_DB  = os.path.join(SEVEN_DATA, 'triggers.db')
RELOAD_SIGNAL = os.path.join(SEVEN_DATA, 'trigger_reload.signal')
LOCK_FILE    = os.path.join(APPDATA, 'SEVEN', 'trigger_daemon.lock')

# Also check local seven_data
LOCAL_SEVEN_DATA = os.path.join(PROJECT_ROOT, 'seven_data')
LOCAL_DB = os.path.join(LOCAL_SEVEN_DATA, 'triggers.db')
if os.path.exists(LOCAL_DB) and not os.path.exists(TRIGGERS_DB):
    TRIGGERS_DB = LOCAL_DB
    SEVEN_DATA = LOCAL_SEVEN_DATA
    RELOAD_SIGNAL = os.path.join(LOCAL_SEVEN_DATA, 'trigger_reload.signal')


# ─────────────────────────────────────────────────────────────────────────
# SINGLE INSTANCE LOCK
# ─────────────────────────────────────────────────────────────────────────

def acquire_lock():
    """Prevent multiple daemon instances using Windows mutex."""
    try:
        import ctypes
        _mutex_name = "Global\\SevenTriggerDaemon_SingleInstance"
        _kernel32 = ctypes.windll.kernel32
        _mutex = _kernel32.CreateMutexW(None, True, _mutex_name)
        _last_err = _kernel32.GetLastError()

        if _last_err == 183:  # ERROR_ALREADY_EXISTS
            print("[TRIGGER DAEMON] Already running. Exiting.")
            if _mutex:
                _kernel32.CloseHandle(_mutex)
            return False

        if not _mutex:
            return True

        acquire_lock._mutex_handle = _mutex
        print(f"[TRIGGER DAEMON] Mutex acquired. PID: {os.getpid()}")

        try:
            os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
            with open(LOCK_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

        return True

    except Exception as _e:
        print(f"[TRIGGER DAEMON] Mutex failed: {_e}")
        return True

acquire_lock._mutex_handle = None


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# DATABASE ACCESS
# ─────────────────────────────────────────────────────────────────────────

def load_triggers():
    """Load all enabled triggers from DB."""
    if not os.path.exists(TRIGGERS_DB):
        return []
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT * FROM triggers WHERE enabled = 1"
        ).fetchall()
        conn.close()

        triggers = []
        for row in rows:
            d = dict(row)
            d["enabled"] = bool(d.get("enabled", 1))
            d["silent"]  = bool(d.get("silent", 0))
            try:
                d["action_data"] = json.loads(d.get("action_data") or "{}")
            except Exception:
                d["action_data"] = {}
            triggers.append(d)

        return triggers
    except Exception as e:
        print(f"[TRIGGER DAEMON] DB load error: {e}")
        return []


def update_fire_stats(trigger_id):
    """Increment fire count for a trigger."""
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE triggers SET fire_count = fire_count + 1, last_fired = ? WHERE id = ?",
            (datetime.now().isoformat(), trigger_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TRIGGER DAEMON] Stats update error: {e}")


# ─────────────────────────────────────────────────────────────────────────
# SEVEN STATUS CHECK
# ─────────────────────────────────────────────────────────────────────────

def is_seven_running():
    """Check if Seven main backend is running on port 7777."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:7777/api/status", timeout=1)
        return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────
# TRIGGER EXECUTION
# ─────────────────────────────────────────────────────────────────────────

def execute_trigger(trigger):
    """
    Execute a trigger action.
    Runs the appropriate handler based on action_type.
    """
    action_type = trigger.get("action_type", "")
    action_data = trigger.get("action_data", {})
    name        = trigger.get("name", "unnamed")

    print(f"[TRIGGER DAEMON] Firing: {name} (type={action_type})")

    try:
        if action_type == "open_app":
            _exec_open_app(action_data)

        elif action_type == "open_url":
            _exec_open_url(action_data)

        elif action_type == "open_file":
            _exec_open_file(action_data)

        elif action_type == "open_folder":
            _exec_open_folder(action_data)

        elif action_type == "open_workspace":
            _exec_open_workspace(action_data)

        elif action_type == "run_command":
            _exec_run_command(action_data)

        elif action_type == "seven_action":
            _exec_seven_action(action_data)

        else:
            print(f"[TRIGGER DAEMON] Unknown action type: {action_type}")
            return

        # Show notification with sound (unless silent)
        if not trigger.get("silent", False):
            try:
                from hands.notifications import notify_trigger_fired
                notify_trigger_fired(name, action_type, sound="default")
            except ImportError:
                _show_notification(name, action_type)

        # Update stats
        update_fire_stats(trigger.get("id"))

    except Exception as e:
        print(f"[TRIGGER DAEMON] Execution error: {e}")
        import traceback; traceback.print_exc()


def _exec_open_app(data):
    """Launch an application."""
    app_name = data.get("app", "")
    if not app_name:
        return

    try:
        # Try Seven's own app launcher first (if running)
        if is_seven_running():
            import requests
            requests.post(
                "http://127.0.0.1:7777/api/chat",
                json={"text": f"open {app_name}", "speaker_id": "default"},
                timeout=5
            )
            return
    except Exception:
        pass

    # Direct launch fallback
    try:
        from hands.core import open_app
        open_app(app_name)
    except ImportError:
        # Fallback: try AppOpener or subprocess
        try:
            import AppOpener
            AppOpener.open(app_name)
        except Exception:
            os.startfile(app_name)


def _exec_open_url(data):
    """Open URL in default browser."""
    url = data.get("url", "")
    if url:
        import webbrowser
        webbrowser.open(url)


def _exec_open_file(data):
    """Open a file with default application."""
    path = data.get("path", "")
    if path and os.path.exists(path):
        os.startfile(path)


def _exec_open_folder(data):
    """Open folder in Explorer."""
    path = data.get("path", "")
    if path and os.path.exists(path):
        subprocess.Popen(['explorer', path])


def _exec_open_workspace(data):
    """Restore a workspace by ID or name."""
    workspace_id   = data.get("workspace_id")
    workspace_name = data.get("workspace_name")

    workspace = None

    # Try via API first
    if is_seven_running():
        try:
            import requests
            if workspace_id:
                r = requests.post(
                    f"http://127.0.0.1:7777/api/workspaces/{workspace_id}/restore",
                    timeout=10
                )
                if r.status_code == 200:
                    return
        except Exception:
            pass

    # Direct DB lookup + execute
    try:
        conn = sqlite3.connect(TRIGGERS_DB, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

        if workspace_id:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
            ).fetchone()
        elif workspace_name:
            row = conn.execute(
                "SELECT * FROM workspaces WHERE LOWER(name) = ?",
                (workspace_name.lower(),)
            ).fetchone()
        else:
            conn.close()
            return

        conn.close()

        if not row:
            print(f"[TRIGGER DAEMON] Workspace not found: id={workspace_id} name={workspace_name}")
            return

        workspace = dict(row)
        try:
            apps = json.loads(workspace.get("apps") or "[]")
        except Exception:
            apps = []

        # Launch all apps in parallel
        threads = []
        for app_config in apps:
            t = threading.Thread(
                target=_launch_workspace_app,
                args=(app_config,),
                daemon=True
            )
            t.start()
            threads.append(t)

        # Wait for all to launch (max 15 seconds)
        for t in threads:
            t.join(timeout=15)

        print(f"[TRIGGER DAEMON] Workspace restored: {workspace.get('name')} ({len(apps)} apps)")

    except Exception as e:
        print(f"[TRIGGER DAEMON] Workspace restore error: {e}")


def _launch_workspace_app(app_config):
    """Launch a single app from workspace config."""
    app_type = app_config.get("type", "app")

    try:
        if app_type == "chrome":
            tabs = app_config.get("tabs", [])
            urls = [t.get("url", "") for t in tabs if t.get("url")]
            if urls:
                # Open Chrome with all tabs
                chrome_cmd = f'start chrome {" ".join(urls)}'
                subprocess.Popen(chrome_cmd, shell=True)
            else:
                subprocess.Popen(['start', 'chrome'], shell=True)

        elif app_type == "vscode":
            workspace_path = app_config.get("workspace_path", "")
            if workspace_path and os.path.exists(workspace_path):
                subprocess.Popen(['code', workspace_path])
            else:
                subprocess.Popen(['code'])

        elif app_type == "explorer":
            folder = app_config.get("folder_path", "")
            if folder and os.path.exists(folder):
                subprocess.Popen(['explorer', folder])

        elif app_type == "app":
            name = app_config.get("name", "")
            exe  = app_config.get("exe_path")
            if exe and os.path.exists(exe):
                subprocess.Popen([exe])
            elif name:
                try:
                    from hands.core import open_app
                    open_app(name)
                except ImportError:
                    try:
                        import AppOpener
                        AppOpener.open(name)
                    except Exception:
                        pass

        elif app_type == "file" or app_type == "pdf":
            path = app_config.get("file_path", "")
            if path and os.path.exists(path):
                os.startfile(path)

    except Exception as e:
        print(f"[TRIGGER DAEMON] App launch error: {e}")


def _exec_run_command(data):
    """Execute a shell command."""
    cmd = data.get("command", "")
    if cmd:
        subprocess.Popen(cmd, shell=True)


def _exec_seven_action(data):
    """Execute internal Seven action via API."""
    action = data.get("action", "")
    if not action:
        return

    if is_seven_running():
        try:
            import requests
            requests.post(
                "http://127.0.0.1:7777/api/chat",
                json={"text": action, "speaker_id": "default"},
                timeout=5
            )
        except Exception:
            pass


def _show_notification(trigger_name, action_type):
    """Show Windows toast notification for trigger fire."""
    try:
        from winotify import Notification, audio
        toast = Notification(
            app_id="Seven AI",
            title="Trigger Fired",
            msg=f"{trigger_name}",
            duration="short"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────
# HOTKEY LISTENER
# ─────────────────────────────────────────────────────────────────────────

class HotkeyListener:
    """
    Global hotkey listener using pynput.
    Monitors keyboard for configured key combos.
    """

    def __init__(self):
        self._triggers     = []     # list of trigger dicts
        self._hotkey_map   = {}     # "ctrl+shift+f" → trigger dict
        self._pressed_keys = set()  # currently held keys
        self._listener     = None
        self._running      = False

    def reload(self, triggers):
        """Reload trigger list (called when DB changes)."""
        self._triggers = triggers
        self._hotkey_map = {}
        for t in triggers:
            hk = t.get("hotkey")
            if hk:
                self._hotkey_map[hk.lower()] = t
        print(f"[HOTKEY] Loaded {len(self._hotkey_map)} hotkey triggers")

    def start(self):
        """Start listening for hotkeys in background thread."""
        if self._running:
            return
        self._running = True

        try:
            from pynput import keyboard

            def on_press(key):
                try:
                    key_str = self._key_to_string(key)
                    if key_str:
                        self._pressed_keys.add(key_str)
                        self._check_combo()
                except Exception:
                    pass

            def on_release(key):
                try:
                    key_str = self._key_to_string(key)
                    if key_str:
                        self._pressed_keys.discard(key_str)
                except Exception:
                    pass

            self._listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
                suppress=False  # don't block keys from other apps
            )
            self._listener.daemon = True
            self._listener.start()
            print("[HOTKEY] Listener started")

        except ImportError:
            print("[HOTKEY] pynput not installed — hotkeys disabled")
        except Exception as e:
            print(f"[HOTKEY] Listener failed: {e}")

    def stop(self):
        self._running = False
        if self._listener:
            self._listener.stop()

    def _key_to_string(self, key):
        """Convert pynput key to normalized string."""
        from pynput import keyboard as kb

        if isinstance(key, kb.Key):
            key_map = {
                kb.Key.ctrl_l:  "ctrl", kb.Key.ctrl_r:  "ctrl",
                kb.Key.shift_l: "shift", kb.Key.shift_r: "shift",
                kb.Key.alt_l:   "alt", kb.Key.alt_r:   "alt",
                kb.Key.cmd:     "win",
                kb.Key.space:   "space",
                kb.Key.enter:   "enter",
                kb.Key.tab:     "tab",
                kb.Key.esc:     "esc",
                kb.Key.backspace: "backspace",
                kb.Key.delete:  "delete",
                kb.Key.home:    "home",
                kb.Key.end:     "end",
                kb.Key.page_up: "pageup",
                kb.Key.page_down: "pagedown",
                kb.Key.up:      "up",
                kb.Key.down:    "down",
                kb.Key.left:    "left",
                kb.Key.right:   "right",
            }
            # F1-F12
            for i in range(1, 13):
                key_map[getattr(kb.Key, f"f{i}", None)] = f"f{i}"

            return key_map.get(key)

        if hasattr(key, 'char') and key.char:
            return key.char.lower()

        if hasattr(key, 'vk') and key.vk:
            # Numeric keys 0-9
            if 48 <= key.vk <= 57:
                return str(key.vk - 48)
            # Numpad 0-9
            if 96 <= key.vk <= 105:
                return f"num{key.vk - 96}"

        return None

    def _check_combo(self):
        """Check if currently pressed keys match any configured hotkey."""
        if not self._pressed_keys or not self._hotkey_map:
            return

        # Build current combo string (sorted for consistency)
        current = "+".join(sorted(self._pressed_keys))

        # Check against all registered hotkeys
        for hotkey_str, trigger in self._hotkey_map.items():
            # Normalize hotkey for comparison
            hotkey_parts = sorted(hotkey_str.split("+"))
            hotkey_normalized = "+".join(hotkey_parts)

            if current == hotkey_normalized:
                print(f"[HOTKEY] Match: {hotkey_str} → {trigger['name']}")

                # Execute in separate thread to not block keyboard
                threading.Thread(
                    target=execute_trigger,
                    args=(trigger,),
                    daemon=True
                ).start()

                # Clear pressed keys to prevent repeat firing
                self._pressed_keys.clear()
                return


# ─────────────────────────────────────────────────────────────────────────
# AUDIO LISTENER (headset users only)
# ─────────────────────────────────────────────────────────────────────────

class AudioListener:
    """
    Listens for snap/clap patterns using DSP or YAMNet.
    Only active if compatible mic detected.
    """

    def __init__(self):
        self._detector  = None
        self._triggers  = []
        self._audio_map = {}  # "1_tap" → trigger, "2_tap" → trigger
        self._running   = False

    def reload(self, triggers):
        """Reload audio pattern triggers."""
        self._triggers = triggers
        self._audio_map = {}
        for t in triggers:
            pattern = t.get("audio_pattern")
            if pattern:
                self._audio_map[pattern] = t
        print(f"[AUDIO] Loaded {len(self._audio_map)} audio triggers")

    def start(self):
        """Start audio detection if any audio triggers exist and mic is compatible."""
        if not self._audio_map:
            print("[AUDIO] No audio triggers configured — skipping")
            return

        self._running = True

        try:
            from ears.audio_triggers import TriggerDetector

            self._detector = TriggerDetector(sensitivity="medium")
            self._detector.on_pattern = self._on_pattern
            self._detector.start()
            print("[AUDIO] Listener started (DSP mode)")

        except Exception as e:
            print(f"[AUDIO] Listener failed: {e}")

    def stop(self):
        self._running = False
        if self._detector:
            self._detector.stop()

    def suppress(self, ms=3000):
        """Suppress detection during voice/speech."""
        if self._detector:
            self._detector.suppress(ms)

    def _on_pattern(self, count):
        """Called when tap pattern detected."""
        pattern_key = f"{count}_tap"
        trigger = self._audio_map.get(pattern_key)

        if trigger:
            print(f"[AUDIO] Pattern {pattern_key} → {trigger['name']}")
            threading.Thread(
                target=execute_trigger,
                args=(trigger,),
                daemon=True
            ).start()
        else:
            print(f"[AUDIO] Pattern {pattern_key} — no trigger assigned")


# ─────────────────────────────────────────────────────────────────────────
# DB RELOAD POLLER
# ─────────────────────────────────────────────────────────────────────────

class ReloadPoller:
    """Watches for trigger_reload.signal file to refresh triggers."""

    def __init__(self, on_reload):
        self._on_reload = on_reload
        self._running   = False
        self._thread    = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
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


# ─────────────────────────────────────────────────────────────────────────
# MAIN DAEMON LOOP
# ─────────────────────────────────────────────────────────────────────────

def main():
    if not acquire_lock():
        return

    print("[TRIGGER DAEMON] Starting...")
    print(f"[TRIGGER DAEMON] DB: {TRIGGERS_DB}")
    print(f"[TRIGGER DAEMON] PID: {os.getpid()}")

    # Load initial triggers
    triggers = load_triggers()
    print(f"[TRIGGER DAEMON] Loaded {len(triggers)} active triggers")

    # Initialize listeners
    hotkey_listener = HotkeyListener()
    audio_listener  = AudioListener()

    def reload_all():
        """Reload all triggers from DB and distribute to listeners."""
        nonlocal triggers
        triggers = load_triggers()
        hotkey_listener.reload(triggers)
        audio_listener.reload(triggers)
        print(f"[TRIGGER DAEMON] Reloaded: {len(triggers)} triggers")

    reload_poller = ReloadPoller(on_reload=reload_all)

    # Initial load into listeners
    hotkey_listener.reload(triggers)
    audio_listener.reload(triggers)

    # Start all listeners
    hotkey_listener.start()
    audio_listener.start()
    reload_poller.start()

    print("[TRIGGER DAEMON] All listeners active. Waiting for triggers...")

    # Keep alive
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        print("[TRIGGER DAEMON] Stopping...")
        hotkey_listener.stop()
        audio_listener.stop()
        reload_poller.stop()
        release_lock()
        print("[TRIGGER DAEMON] Stopped.")


if __name__ == "__main__":
    try:
        main()
    finally:
        release_lock()