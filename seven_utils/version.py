"""
seven_utils/version.py
The app version, read from version.txt at the app root (the file the updater and
installer use). Every API that reports a version should call get_version() instead
of hardcoding a number or reading the user's config.json, which keeps the version
from when setup ran.

Usage:
    from seven_utils.version import get_version
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_version() -> str:
    try:
        # utf-8-sig drops the byte-order mark Windows editors add to version.txt
        with open(os.path.join(_ROOT, "version.txt"), encoding="utf-8-sig") as f:
            version = f.read().strip()
        if version:
            return version
    except OSError:
        pass
    try:
        with open(os.path.join(_ROOT, "package.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "unknown")
    except (OSError, ValueError):
        return "unknown"
