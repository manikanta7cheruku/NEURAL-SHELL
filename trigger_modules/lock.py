"""
trigger_modules/lock.py
Single-instance mutex enforcement for the trigger daemon.
Prevents duplicate daemons from launching (child processes,
Task Scheduler restarts, manual runs).
"""
import os
from trigger_modules.config import LOCK_FILE


def acquire_lock():
    """
    Two-stage mutex check:
      1. OpenMutexW — detects inherited handles (child process bypass)
      2. CreateMutexW + ERROR_ALREADY_EXISTS — race condition fallback

    Also marks the mutex non-inheritable so child processes spawned
    by this daemon (AppOpener indexer etc.) cannot bypass the check.
    """
    try:
        import ctypes
        _mutex_name = "Global\\SevenTriggerDaemon_SingleInstance"
        _kernel32   = ctypes.windll.kernel32

        # Stage 1: Try to OPEN existing mutex before creating
        _existing = _kernel32.OpenMutexW(0x1F0001, False, _mutex_name)
        if _existing:
            _kernel32.CloseHandle(_existing)

            # Mutex exists — but is the owning process still alive?
            _owner_alive = False
            try:
                if os.path.exists(LOCK_FILE):
                    with open(LOCK_FILE, 'r') as _lf:
                        _owner_pid = int(_lf.read().strip())
                    if _owner_pid != os.getpid():
                        import psutil
                        _owner_alive = psutil.pid_exists(_owner_pid)
                        if _owner_alive:
                            try:
                                _proc = psutil.Process(_owner_pid)
                                _cmd  = ' '.join(_proc.cmdline())
                                _owner_alive = 'trigger_daemon' in _cmd
                            except Exception:
                                _owner_alive = False
            except Exception:
                _owner_alive = False

            if _owner_alive:
                print(f"[TRIGGER DAEMON] Already running (OpenMutex). "
                      f"PID {os.getpid()} exiting.")
                return False
            else:
                print(f"[TRIGGER DAEMON] Stale mutex found — previous "
                      f"instance is dead. Starting fresh.")

        # Stage 2: Create and own the mutex
        _mutex    = _kernel32.CreateMutexW(None, True, _mutex_name)
        _last_err = _kernel32.GetLastError()

        if _last_err == 183:  # ERROR_ALREADY_EXISTS
            print("[TRIGGER DAEMON] Already running (CreateMutex). Exiting.")
            if _mutex:
                _kernel32.CloseHandle(_mutex)
            return False

        if not _mutex:
            print("[TRIGGER DAEMON] Mutex creation failed — starting anyway")
            return True

        # Mark mutex non-inheritable
        _kernel32.SetHandleInformation(_mutex, 1, 0)

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