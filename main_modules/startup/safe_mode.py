"""
main_modules/startup/safe_mode.py

Safe mode: Seven opens without its speech, brain and voice when loading them keeps failing.

It used to be permanent. One failed load (a speech model that could not download while offline, a library that needed
a restart after installing) wrote a flag that nothing ever deleted, so every later start skipped the AI modules: Seven sat
on "Getting ready", could not hear, and the test mic said "not listening", with no error anywhere. Now:

    one failure       is only noted; the next start tries to load everything again
    three in a row    safe mode, with the reason shown and a Retry button (retry() clears it and restarts Seven)
    a new version     forgets old failures: an update may be exactly the fix
    a good start      clears the record

The flag is a small JSON file next to config.json; an old flag (a bare timestamp) counts as one failure.
"""
import json
import os
import time

MAX_FAILS = 3


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    return {"fails": 1, "reason": "", "version": ""}        # the old flag: a bare timestamp


def state(path: str, version: str = "") -> dict:
    """{fails, reason, at, version} of the recorded failures; empty when there are none (or a new version replaced them)."""
    data = _read(path)
    if data and data.get("version") and version and data["version"] != version:
        return {}
    return data


def should_enter(path: str, version: str = "") -> bool:
    return int(state(path, version).get("fails", 0) or 0) >= MAX_FAILS


def record_failure(path: str, reason: str, version: str = "") -> int:
    """Note one more failed load. Returns how many in a row."""
    fails = int(state(path, version).get("fails", 0) or 0) + 1
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"fails": fails, "reason": (reason or "")[:300], "at": time.time(), "version": version}, f)
    except OSError:
        pass
    return fails


def clear(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def retry(path: str, restart=None) -> None:
    """Leave safe mode: forget the failures and start Seven again (Electron restarts the backend when it exits)."""
    clear(path)
    if restart is not None:
        restart()
