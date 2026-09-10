"""
trigger_modules/overlay.py
Overlay daemon TCP communication (port 7891).
Handles notification injection and arrangement card display with
production-safe timeouts and non-blocking recovery.
"""
import os
import json
import time
import socket
import subprocess
import threading

from trigger_modules.config import PROJECT_ROOT

_overlay_spawn_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────
# TCP MESSAGE HELPERS
# ─────────────────────────────────────────────────────────────────────────
def _send_overlay(msg: dict, timeout: float = 1.5) -> bool:
    """Send a newline-delimited JSON message to overlay_daemon."""
    try:
        s = socket.create_connection(("127.0.0.1", 7891), timeout=timeout)
        s.settimeout(timeout)
        s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
        s.close()
        if data:
            resp = json.loads(data.decode("utf-8").strip())
            return resp.get("ok", False)
        return False
    except Exception:
        return False


def is_overlay_alive() -> bool:
    """Ping overlay_daemon on port 7891 with a 1.2s timeout."""
    return _send_overlay({"type": "ping"}, timeout=1.2)


# ─────────────────────────────────────────────────────────────────────────
# OVERLAY DAEMON SPAWNER (Production & Dev Safe)
# ─────────────────────────────────────────────────────────────────────────
def ensure_overlay_alive_safe() -> bool:
    """
    Ensure overlay daemon is running on port 7891.
    Thread-safe — only one spawn attempt at a time.
    Uses non-blocking short timeouts to never stall hotkey execution.
    """
    if is_overlay_alive():
        return True

    if not _overlay_spawn_lock.acquire(blocking=False):
        # Another thread is already handling spawn — do not block
        return False

    try:
        if is_overlay_alive():
            return True

        print("[TRIGGER DAEMON] Overlay daemon down — spawning...")

        app_path = os.environ.get('SEVEN_APP_PATH') or PROJECT_ROOT
        resources_dir = os.path.dirname(app_path)
        install_root = os.path.dirname(resources_dir)

        electron_exe = None
        for c in [
            os.path.join(install_root, "SEVEN.exe"),
            os.path.join(install_root, "seven.exe"),
        ]:
            if os.path.exists(c):
                electron_exe = c
                break

        # Fall back to dev node_modules if not running packaged
        if not electron_exe:
            for _rel in [
                os.path.join("node_modules", "electron", "dist", "electron.exe"),
                os.path.join("node_modules", ".bin", "electron.cmd"),
            ]:
                _c = os.path.join(PROJECT_ROOT, _rel)
                if os.path.exists(_c):
                    electron_exe = _c
                    break

        if not electron_exe:
            print("[TRIGGER DAEMON] Electron executable not found.")
            return False

        daemon_js = os.path.join(PROJECT_ROOT, "electron", "overlay_daemon.js")
        if not os.path.exists(daemon_js):
            # Check packaged path
            if app_path:
                daemon_js = os.path.join(app_path, "electron", "overlay_daemon.js")

        if not os.path.exists(daemon_js):
            print(f"[TRIGGER DAEMON] overlay_daemon.js not found: {daemon_js}")
            return False

        # In production, pass unique user-data-dir to avoid single-instance lock collision
        is_production = "SEVEN.exe" in electron_exe or "seven.exe" in electron_exe.lower()
        if is_production:
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            overlay_user_data = os.path.join(appdata, 'SEVEN', 'overlay_user_data')
            os.makedirs(overlay_user_data, exist_ok=True)
            cmd = [
                electron_exe,
                f"--user-data-dir={overlay_user_data}",
                "--",
                daemon_js,
                "--overlay-daemon"
            ]
        else:
            cmd = [electron_exe, daemon_js, "--overlay-daemon"]

        print(f"[TRIGGER DAEMON] Spawning overlay: {electron_exe}")

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008 | 0x00000200,
            close_fds=True,
            start_new_session=True,
            cwd=PROJECT_ROOT,
        )

        # Quick poll for up to 3 seconds (never block for 15s)
        for _ in range(30):
            time.sleep(0.1)
            if is_overlay_alive():
                print("[TRIGGER DAEMON] Overlay daemon ready ✓")
                return True

        print("[TRIGGER DAEMON] Overlay warm-up continuing in background")
        return False

    finally:
        _overlay_spawn_lock.release()


# ─────────────────────────────────────────────────────────────────────────
# NOTIFICATION FIRING
# ─────────────────────────────────────────────────────────────────────────
def fire_notification(name, action_type, app_count, tab_count, app_names):
    """Send a notification message to the overlay daemon asynchronously."""
    subtitle_map = {
        "open_app":       "App launched",
        "open_url":       "URL opened",
        "open_workspace": "Workspace restored",
        "open_file":      "File opened",
        "open_folder":    "Folder opened",
        "run_command":    "Command executed",
        "seven_action":   "Action completed",
    }
    subtitle = subtitle_map.get(action_type, "Trigger fired")

    parts = []
    if app_count > 0:
        parts.append(f"{app_count} app{'s' if app_count != 1 else ''}")
    if tab_count > 0:
        parts.append(f"{tab_count} tab{'s' if tab_count != 1 else ''}")
    detail = "  ·  ".join(parts) if parts else ""
    hold_ms = 3500 if action_type == "open_workspace" else 4500

    def _async_send():
        _send_overlay({
            "type": "notif",
            "data": {
                "title":    name,
                "subtitle": subtitle,
                "detail":   detail,
                "holdMs":   hold_ms,
            },
        }, timeout=1.5)

    threading.Thread(target=_async_send, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────
# ARRANGEMENT CARD FIRING
# ─────────────────────────────────────────────────────────────────────────
def fire_arrangement_card(workspace_apps, get_windows_fn):
    """Send arrangement card data to the overlay daemon asynchronously."""
    if not workspace_apps:
        return

    def _async_arrange():
        if not is_overlay_alive():
            ensure_overlay_alive_safe()
            time.sleep(0.5)

        triggered_wins, other_wins = get_windows_fn(workspace_apps)
        if triggered_wins:
            _send_overlay({
                "type": "arrange",
                "data": {
                    "windows":    triggered_wins,
                    "allWindows": other_wins,
                },
            }, timeout=2.0)
            print(f"[TRIGGER DAEMON] Arrangement card displayed: {len(triggered_wins)} windows")
        else:
            print("[TRIGGER DAEMON] No matching windows found for arrangement card")

    threading.Thread(target=_async_arrange, daemon=True).start()