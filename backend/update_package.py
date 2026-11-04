"""
backend/update_package.py
Updates that carry only what changed.

A release is described by a manifest: every file of the installed app with its SHA-256. A patch is a zip holding just the
files that differ between two releases (and a list of the ones that went away). Building one is the release script's
job (scripts/build_update_package.py); checking one before it touches an install is the app's:

    build_manifest(root, version)               hash every file under the build folder
    diff(old, new)                              (changed or added paths, removed paths)
    build_patch(root, old, new, out_zip)        the patch zip and the numbers to publish with it
    extract_and_verify(zip, dest, sha256)       unpack it and prove every file is the one that was published

Paths are relative to the install folder (the folder that holds SEVEN.exe), written with "/".
"""
import gzip
import hashlib
import json
import os
import shutil
import zipfile

SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = (".pyc", ".pyo")
PATCH_FILE = "patch.json"
BASE_SKIP = ("resources/app/python/",)
PAYLOAD = "files/"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk(root: str):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(SKIP_SUFFIXES):
                continue
            full = os.path.join(base, name)
            yield os.path.relpath(full, root).replace(os.sep, "/"), full


def build_manifest(root: str, version: str) -> dict:
    files = {rel: [sha256_file(full), os.path.getsize(full)] for rel, full in _walk(root)}
    return {"version": version, "files": files}


def save_manifest(manifest: dict, path: str) -> None:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"), sort_keys=True)


def load_manifest(path: str) -> dict:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def diff(old: dict, new: dict):
    """(paths to send: new or changed, paths to delete: in the old build and not in the new one)."""
    o, n = old["files"], new["files"]
    changed = sorted(p for p, meta in n.items() if p not in o or o[p][0] != meta[0])
    removed = sorted(p for p in o if p not in n)
    return changed, removed


def build_patch(root: str, old: dict, new: dict, out_zip: str) -> dict:
    """Write the patch zip for old -> new and return what to publish with it."""
    changed, removed = diff(old, new)
    # What the old build looked like, so the PC can prove it has exactly that build before anything is touched: a patch applied
    # on top of a different build of the same version number (rebuilt since) would mix two builds. The Python runtime is left
    # out of the check (it is large and a patch that changes it carries its own files, each checked against "old").
    unchanged = {p: m[0] for p, m in old["files"].items() if p not in changed and p not in removed and not p.startswith(BASE_SKIP)}
    meta = {"from": old["version"], "to": new["version"], "delete": removed,
            "files": {p: new["files"][p] for p in changed},
            "old": {p: old["files"][p][0] for p in list(changed) + removed if p in old["files"]},
            "base": unchanged}
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(PATCH_FILE, json.dumps(meta, separators=(",", ":")))
        for p in changed:
            z.write(os.path.join(root, *p.split("/")), PAYLOAD + p)
    return {"from": old["version"], "to": new["version"], "files": len(changed), "removed": len(removed),
            "size": os.path.getsize(out_zip), "sha256": sha256_file(out_zip)}


def extract_and_verify(zip_path: str, dest: str, sha256: str = "") -> dict:
    """Unpack a patch into `dest` and check every file against the patch's own list. Returns the patch description.
    Raises ValueError (with a sentence a person can read) when anything does not match: the install is never touched."""
    if sha256 and sha256_file(zip_path).lower() != sha256.strip().lower():
        raise ValueError("The update package does not match its published checksum.")
    if os.path.isdir(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as z:
            meta = json.loads(z.read(PATCH_FILE))
            for name in z.namelist():
                if name == PATCH_FILE:
                    continue
                target = os.path.realpath(os.path.join(dest, *name.split("/")))
                if not target.startswith(os.path.realpath(dest) + os.sep):
                    raise ValueError("The update package contains an unsafe path.")
                if not name.startswith(PAYLOAD):
                    raise ValueError("The update package is not in the expected layout.")
            z.extractall(dest)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f"The update package is damaged ({type(exc).__name__}).")
    for rel, (digest, size) in meta["files"].items():
        path = os.path.join(dest, "files", *rel.split("/"))
        if not os.path.isfile(path) or os.path.getsize(path) != size or sha256_file(path) != digest:
            raise ValueError(f"The update package is damaged: {rel} does not match.")
    return meta
