"""
=============================================================================
brain_modules/recovery_daemon.py

Auto-Recovery and VRAM Sentinel.

Monitors Ollama connectivity, handles detached background service restarts,
prevents restart cascade loops via cooldown timers, and keeps models resident
in VRAM to avoid cold-start penalties.
=============================================================================
"""

import os
import sys
import time
import socket
import threading
import subprocess
import requests
from colorama import Fore
from typing import Tuple, Optional

OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_GEN_URL  = "http://127.0.0.1:11434/api/generate"

_lock = threading.Lock()
_last_restart_time: float = 0.0
_restart_count_window: int = 0
_WINDOW_SECONDS: float = 300.0
_MAX_RESTARTS_PER_WINDOW: int = 3
_MIN_RESTART_INTERVAL: float = 20.0


def is_port_open(host: str = "127.0.0.1", port: int = 11434, timeout: float = 1.0) -> bool:
    """Check if the target port is accepting TCP connections."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def is_ollama_responsive(timeout: float = 1.5) -> bool:
    """Verify HTTP API responsiveness."""
    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def can_attempt_restart() -> Tuple[bool, str]:
    """Rate-limit check to prevent fork bombs or restart loops."""
    global _last_restart_time, _restart_count_window
    now = time.time()

    with _lock:
        if now - _last_restart_time < _MIN_RESTART_INTERVAL:
            return False, f"Cooldown active. Wait {int(_MIN_RESTART_INTERVAL - (now - _last_restart_time))}s."

        if now - _last_restart_time > _WINDOW_SECONDS:
            _restart_count_window = 0

        if _restart_count_window >= _MAX_RESTARTS_PER_WINDOW:
            return False, "Max restart attempts reached in current time window."

        return True, "OK"


def restart_ollama_service() -> bool:
    """
    Launch Ollama in a detached background process surviving parent termination.
    Returns True if service responds within the 8-second grace window.
    """
    global _last_restart_time, _restart_count_window

    allowed, reason = can_attempt_restart()
    if not allowed:
        print(Fore.YELLOW + f"[RECOVERY] Ollama restart suppressed: {reason}")
        return False

    with _lock:
        _last_restart_time = time.time()
        _restart_count_window += 1

    print(Fore.CYAN + "[RECOVERY] Attempting detached Ollama daemon restart...")

    cflags = 0x08000000 if sys.platform == "win32" else 0

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=cflags,
            close_fds=(sys.platform != "win32"),
        )
    except FileNotFoundError:
        print(Fore.RED + "[RECOVERY] Ollama binary not located in PATH.")
        return False
    except Exception as e:
        print(Fore.RED + f"[RECOVERY] Subprocess spawn failed: {e}")
        return False

    # Poll until ready or timeout (max 8 seconds)
    start_poll = time.time()
    while time.time() - start_poll < 8.0:
        time.sleep(0.8)
        if is_ollama_responsive(timeout=1.0):
            print(Fore.GREEN + f"[RECOVERY] Ollama restored successfully in {round(time.time() - start_poll, 2)}s.")
            return True

    print(Fore.RED + "[RECOVERY] Ollama restart timed out waiting for API ready state.")
    return False


def prewarm_model(model_name: str) -> None:
    """Send a zero-token generation request to pin the model into VRAM."""
    if not model_name or not is_ollama_responsive():
        return

    def _worker():
        try:
            requests.post(
                OLLAMA_GEN_URL,
                json={"model": model_name, "prompt": "", "keep_alive": "24h"},
                timeout=10,
            )
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()