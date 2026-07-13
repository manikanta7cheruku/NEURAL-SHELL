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


def _ensure_daemon_running():
    """
    Check if overlay daemon is running. If not, spawn it.
    Called at first notification attempt.
    """
    global _daemon_healthy, _daemon_last_check

    # Skip check if we pinged recently
    now = time.time()
    if _daemon_healthy and (now - _daemon_last_check) < 5:
        return True

    _daemon_last_check = now

    # Try ping first
    if _send_ipc({"type": "ping"}, timeout=0.3):
        return True

    # Not running — spawn it
    electron = _electron()
    if not electron:
        print(Fore.YELLOW + "[OVERLAY] Electron not found — daemon can't start")
        return False

    daemon_js = os.path.join(_root(), "electron", "overlay_daemon.js")
    if not os.path.exists(daemon_js):
        print(Fore.YELLOW + f"[OVERLAY] Daemon script missing: {daemon_js}")
        return False

    print(Fore.CYAN + "[OVERLAY] Spawning overlay daemon...")
    try:
        subprocess.Popen(
            [electron, daemon_js],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=0x08000000 | 0x00000008 | 0x00000200,
            # CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        )
    except Exception as e:
        print(Fore.YELLOW + f"[OVERLAY] Daemon spawn failed: {e}")
        return False

    # Wait for daemon to be ready (poll for up to 3 seconds)
    for _ in range(30):
        time.sleep(0.1)
        if _send_ipc({"type": "ping"}, timeout=0.2):
            print(Fore.GREEN + "[OVERLAY] Daemon is ready")
            return True

    print(Fore.YELLOW + "[OVERLAY] Daemon didn't respond in time")
    return False


# ── Public API ────────────────────────────────────────────────────────────

def show_notification(
    title: str,
    subtitle: str = "",
    detail: str = "",
    hold_ms: int = 3500,
):
    """
    Show notification card (Stage 1 only).
    Non-blocking — sends TCP message and returns immediately.
    """
    threading.Thread(
        target=_do_show_notif,
        args=(title, subtitle, detail, hold_ms),
        daemon=True,
    ).start()


def _do_show_notif(title, subtitle, detail, hold_ms):
    """Internal: send notif to daemon."""
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
        },
    }
    _send_ipc(msg)


def show_trigger_notification(
    trigger_name: str,
    action_type: str = "",
    app_count: int = 0,
    tab_count: int = 0,
    app_names: str = "",
):
    """
    Full two-stage trigger notification.
    Stage 1: notification (3.5s)
    Stage 2: arrangement card (workspace only) — appears after stage 1 dismisses
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

    threading.Thread(
        target=_do_two_stage,
        args=(trigger_name, subtitle, detail, hold_ms, is_workspace, app_names),
        daemon=True,
    ).start()


def _do_two_stage(title, subtitle, detail, hold_ms, show_arrangement, app_names):
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
        },
    })

    if not show_arrangement:
        return

    # Wait for stage 1 to finish (hold + slide-up animation)
    time.sleep((hold_ms + 500) / 1000.0)

    # Stage 2: arrangement card
    app_list = [a.strip() for a in app_names.split(",") if a.strip()]
    _send_ipc({
        "type": "arrange",
        "data": {"appNames": app_list},
    })