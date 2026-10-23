"""
scripts/check_version.py

Fails when the version numbers that ship with SEVEN disagree.
version.txt is the source of truth (read by seven_utils.version, the updater and
the installer); the package.json files and the config.json template must match it.

    python scripts/check_version.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _json_version(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8-sig") as f:
        return json.load(f).get("version")


def main():
    with open(os.path.join(ROOT, "version.txt"), encoding="utf-8-sig") as f:
        expected = f.read().strip()
    found = {rel: _json_version(rel) for rel in ("package.json", "frontend/package.json", "config.json")}
    wrong = {rel: v for rel, v in found.items() if v != expected}
    if wrong:
        for rel, v in wrong.items():
            print(f"{rel}: version {v!r}, expected {expected!r} (from version.txt)")
        return 1
    print(f"All versions match {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
