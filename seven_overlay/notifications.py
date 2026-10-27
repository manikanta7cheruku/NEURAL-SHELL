"""
seven_overlay/notifications.py

Ultra-fast notification client.
Sends TCP message to overlay_daemon (already running).
Fallback: spawn one-off Electron if daemon not running.
"""

import os
import json
import socket
import subprocess
import threading
import time
from colorama import Fore


IPC_HOST = "127.0.0.1"
IPC_PORT = 7891

# Track daemon health
_daemon_healthy = False
_daemon_last_check = 0
_spawn_lock = threading.Lock()  # module-level — initialized once, never None


def _root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _electron():
    root = _root()
    candidates = [
        os.path.join(root, "node_modules", "electron", "dist", "electron.exe"),
        os.path.join(root, "node_modules", ".bin", "electron.cmd"),
        os.path.join(root, "frontend", "node_modules",
                     "electron", "dist", "electron.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


# ── TCP client ────────────────────────────────────────────────────────────

def _send_ipc(msg: dict, timeout: float = 0.5) -> bool:
    """
    Send message to overlay_daemon over TCP.
    Returns True if daemon responded ok.
    """
    global _daemon_healthy
    try:
        sock = socket.create_connection((IPC_HOST, IPC_PORT), timeout=timeout)
        sock.settimeout(timeout)
        payload = (json.dumps(msg) + "\n").encode("utf-8")
        sock.sendall(payload)

        # Read response
        data = b""
        while b"\n" not in data:
            chunk = sock.recv(1024)
            if not chunk:
                break
            data += chunk
        sock.close()

        if data:
            resp = json.loads(data.decode("utf-8").strip())
            _daemon_healthy = resp.get("ok", False)
            return _daemon_healthy
        return False

    except Exception:
        _daemon_healthy = False
        return False


# Module-level lock — initialized once, never None
_spawn_lock = threading.Lock()


def _ensure_daemon_running():
    """
    Ensure overlay daemon is running on port 7891.
    Thread-safe — module-level lock prevents concurrent spawns.
    Called from notification threads — must never block long.
    """
    global _daemon_healthy, _daemon_last_check

    # Fast path — skip if recently confirmed alive
    now = time.time()
    if _daemon_healthy and (now - _daemon_last_check) < 5:
        return True

    _daemon_last_check = now

    # Already alive — return immediately
    if _send_ipc({"type": "ping"}, timeout=0.3):
        _daemon_healthy = True
        return True

    # Dead — acquire lock before spawning
    if not _spawn_lock.acquire(blocking=True, timeout=8):
        return False

    try:
        # Double-check after lock — another thread may have spawned it
        if _send_ipc({"type": "ping"}, timeout=0.3):
            _daemon_healthy = True
            return True

        electron = _electron()
        if not electron:
            print(Fore.YELLOW + "[OVERLAY] Electron not found")
            return False

        daemon_js = os.path.join(_root(), "electron", "overlay_daemon.js")
        if not os.path.exists(daemon_js):
            print(Fore.YELLOW + "[OVERLAY] overlay_daemon.js not found")
            return False

        print(Fore.CYAN + "[OVERLAY] Spawning overlay daemon...")
        subprocess.Popen(
            [electron, daemon_js],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008 | 0x00000200,
        )

        # Wait up to 5 seconds
        for _ in range(50):
            time.sleep(0.1)
            if _send_ipc({"type": "ping"}, timeout=0.2):
                print(Fore.GREEN + "[OVERLAY] Daemon ready")
                _daemon_healthy = True
                return True

        print(Fore.YELLOW + "[OVERLAY] Spawn timed out")
        return False

    finally:
        _spawn_lock.release()


# ── Public API ────────────────────────────────────────────────────────────

def show_notification(
    title: str,
    subtitle: str = "",
    detail: str = "",
    hold_ms: int = 3500,
    state: str = "info",
    replace: bool = False,
):
    """
    Show the card at the top centre of the screen. Non-blocking.
    state: "working" (spinner, stays until replaced), "done" (check and chime), "error", "info".
    replace=True updates the card already showing instead of sliding a new one in.
    """
    threading.Thread(
        target=_do_show_notif,
        args=(title, subtitle, detail, hold_ms, state, replace),
        daemon=True,
    ).start()


def _do_show_notif(title, subtitle, detail, hold_ms, state="info", replace=False):
    """Internal: send notif to daemon."""
    if os.environ.get("SEVEN_TEST") == "1":
        return
    if not _ensure_daemon_running():
        print(Fore.YELLOW + "[OVERLAY] Daemon unavailable")
        return

    msg = {
        "type": "notif",
        "data": {
            "title":    title,
            "subtitle": subtitle,
            "detail":   detail,
            "holdMs":   hold_ms,
            "state":    state,
            "replace":  replace,
        },
    }
    _send_ipc(msg)


class progress:
    """A card that says what Seven is doing, then what happened:

        with progress("Scanning your workspace", "Windows, tabs and documents") as card:
            ...
            card.done("Saved Study", "9 apps", "37 tabs")
    Leaving the block with an exception shows the error instead.
    """

    def __init__(self, title: str, subtitle: str = ""):
        self.finished = False
        show_notification(title, subtitle, state="working", hold_ms=20000)

    def done(self, title: str, subtitle: str = "", detail: str = ""):
        self.finished = True
        time.sleep(0.15)                      # keep the update behind the first message on the socket
        show_notification(title, subtitle, detail, hold_ms=3800, state="done", replace=True)

    def fail(self, title: str, subtitle: str = ""):
        self.finished = True
        time.sleep(0.15)
        show_notification(title, subtitle, hold_ms=4500, state="error", replace=True)

    def __enter__(self):
        return self

    def __exit__(self, kind, exc, tb):
        if kind and not self.finished:
            self.fail("That didn't work", str(exc)[:80])
        return False


def show_trigger_notification(
    trigger_name: str,
    action_type: str = "",
    app_count: int = 0,
    tab_count: int = 0,
    app_names: str = "",
    workspace_apps: list = None,
    arrange: bool = True,
):
    """
    Full two-stage trigger notification.
    Stage 1: notification (3.5s)
    Stage 2: arrangement card (workspace only) — appears after stage 1 dismisses, once 2+ of its windows are open.
    workspace_apps (the saved app dicts) finds windows by exe path; without it, app_names finds them by title.
    """
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
    detail = "  ·  ".join(parts)

    is_workspace = (action_type == "open_workspace")
    hold_ms = 3800 if is_workspace else 3200
    is_workspace = is_workspace and arrange

    threading.Thread(
        target=_do_two_stage,
        args=(trigger_name, subtitle, detail, hold_ms, is_workspace, app_names, workspace_apps),
        daemon=True,
    ).start()


def _find_arrange_windows(app_names, workspace_apps):
    """(windows, other_windows) as the arrangement card needs them: dicts with hwnd, title, exe."""
    try:
        from trigger_modules.window_finder import get_windows_by_workspace_apps, get_windows_for_arrange
        if workspace_apps:
            return get_windows_by_workspace_apps(workspace_apps)
        return get_windows_for_arrange([a.strip() for a in app_names.split(",") if a.strip()])
    except Exception as e:
        print(f"[OVERLAY] Window lookup for arrangement failed: {e}")
        return [], []


def _do_two_stage(title, subtitle, detail, hold_ms, show_arrangement, app_names, workspace_apps=None):
    """Internal: fire notification, then arrangement after delay."""
    if not _ensure_daemon_running():
        return

    # Stage 1: notification
    _send_ipc({
        "type": "notif",
        "data": {
            "title":    title,
            "subtitle": subtitle,
            "detail":   detail,
            "holdMs":   hold_ms,
            "state":    "done",
        },
    })

    if not show_arrangement:
        return

    # Stage 2: the arrangement card, after stage 1 has gone and once the restored windows exist. The card arranges
    # windows by handle, so it needs the real windows; names alone gave it nothing to arrange.
    deadline = time.time() + 10 + hold_ms / 1000.0
    time.sleep((hold_ms + 300) / 1000.0)
    windows, others = [], []
    while time.time() < deadline:
        windows, others = _find_arrange_windows(app_names, workspace_apps)
        if len(windows) >= 2:
            break
        time.sleep(1.0)
    if len(windows) < 2:
        print("[OVERLAY] Fewer than 2 workspace windows open, no arrangement card")
        return
    _send_ipc({"type": "arrange", "data": {"windows": windows, "allWindows": others}})