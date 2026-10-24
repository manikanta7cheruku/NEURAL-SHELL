"""
knowledge/indexer.py

Older entry points kept working on top of the document library (knowledge/store.py).
"""

import os

from knowledge import store
from knowledge.extract import SUPPORTED as SUPPORTED_EXTENSIONS, ExtractError

__all__ = ["SUPPORTED_EXTENSIONS", "index_file", "remove_file", "index_directory", "get_index_manifest"]


def index_file(filepath):
    """Read one file into the library and wait for it. Returns (success, passages, message)."""
    try:
        doc = store.wait(store.add(filepath)["id"], timeout=600)
    except ExtractError as exc:
        return False, 0, str(exc)
    if not doc or doc["status"] != "ready":
        return False, 0, (doc or {}).get("error") or "Reading did not finish."
    return True, doc["chunks"], f"Read {doc['name']}: {doc['unit']}"


def remove_file(filename):
    doc = next((d for d in store.documents() if d["name"] == filename or d["id"] == filename), None)
    if not doc:
        return False, f"Not in your library: {filename}"
    store.remove(doc["id"])
    return True, f"Removed {doc['name']}"


def index_directory(dirpath):
    files = chunks = 0
    messages = []
    for name in sorted(os.listdir(dirpath)):
        if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
            ok, n, msg = index_file(os.path.join(dirpath, name))
            messages.append(msg)
            files, chunks = files + ok, chunks + n
    return files, chunks, messages


def get_index_manifest():
    return {d["name"]: {"ext": d["ext"], "size_kb": d.get("size_kb", 0), "chunks": d.get("chunks", 0)}
            for d in store.documents()}
