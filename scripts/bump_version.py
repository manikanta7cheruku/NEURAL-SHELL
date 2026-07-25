"""
scripts/bump_version.py
Single version source of truth for Seven.

Usage:
    python scripts/bump_version.py              - show current version
    python scripts/bump_version.py 1.2.8        - bump to specific version
    python scripts/bump_version.py --patch      - bump patch: 1.2.7 -> 1.2.8
    python scripts/bump_version.py --minor      - bump minor: 1.2.7 -> 1.3.0
    python scripts/bump_version.py --major      - bump major: 1.2.7 -> 2.0.0

What it updates:
    version.txt                 (source of truth)
    package.json                (Electron main)
    frontend/package.json       (React frontend)

electron-builder.yml reads version from package.json automatically.
Python code reads version.txt at runtime.
"""

import sys
import os
import json
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VERSION_TXT     = os.path.join(ROOT, "version.txt")
PACKAGE_JSON    = os.path.join(ROOT, "package.json")
FRONTEND_JSON   = os.path.join(ROOT, "frontend", "package.json")


def read_version():
    with open(VERSION_TXT, "r") as f:
        return f.read().strip()


def parse_version(v):
    parts = v.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {v}. Expected X.Y.Z")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump(current, part):
    major, minor, patch = parse_version(current)
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unknown part: {part}")


def update_version_txt(version):
    with open(VERSION_TXT, "w") as f:
        f.write(version)
    print(f"  updated version.txt -> {version}")


def update_package_json(path, version):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = version
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        f.write("\n")
    print(f"  updated {os.path.relpath(path, ROOT)} -> {version}")


def main():
    current = read_version()

    if len(sys.argv) == 1:
        print(f"Current version: {current}")
        print(f"\nAll version files:")
        print(f"  version.txt:          {current}")

        with open(PACKAGE_JSON) as f:
            pj = json.load(f)
        print(f"  package.json:         {pj.get('version', 'NOT SET')}")

        with open(FRONTEND_JSON) as f:
            fj = json.load(f)
        print(f"  frontend/package.json: {fj.get('version', 'NOT SET')}")

        all_match = (
            current == pj.get("version") == fj.get("version")
        )
        print(f"\nAll in sync: {'YES' if all_match else 'NO - FIX WITH: python scripts/bump_version.py ' + current}")
        return

    arg = sys.argv[1]

    if arg in ("--patch", "--minor", "--major"):
        new_version = bump(current, arg.lstrip("-"))
    else:
        try:
            parse_version(arg)
            new_version = arg
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    print(f"\nBumping version: {current} -> {new_version}\n")

    update_version_txt(new_version)
    update_package_json(PACKAGE_JSON, new_version)
    update_package_json(FRONTEND_JSON, new_version)

    print(f"\nDone. All files updated to {new_version}")
    print(f"\nNext steps:")
    print(f"  git add version.txt package.json frontend/package.json")
    print(f'  git commit -m "chore(release): bump version to {new_version}"')
    print(f"  git push")
    print(f"  npm run dist")


if __name__ == "__main__":
    main()