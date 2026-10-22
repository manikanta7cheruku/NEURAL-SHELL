"""
brain_modules/app_map.py

Seven's knowledge of its OWN interface, generated from the frontend source so
it cannot drift: routes come from App.jsx, page titles and purposes from
PageHeader, controls and their descriptions from the text in each page and
its section components. Pages may add precision with an exported JSON block:

    export const SEVEN_DOC = {"purpose": "...", "keywords": ["..."]};

build() runs in dev builds and via scripts/build_app_manifest.py (an npm
prebuild step). In a development checkout refresh_if_stale() rebuilds the map
automatically when the frontend changed; a packaged app ships the built file.
"""

import hashlib
import json
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app_map.json")
_ROUTE_RE = re.compile(r'<Route\s+path="(?P<path>[^"]+)"\s+element=\{<(?P<comp>\w+)')
_IMPORT_RE = re.compile(r"import\s+(?P<name>\w+)\s+from\s+'(?P<path>\./pages/[^']+)'")
_TEXT_RE = re.compile(r">\s*([^<>{}\n=][^<>{}]{1,170}?)\s*<")
_HEADER_RE = re.compile(r'<PageHeader\s+title="([^"]+)"(?:\s+sub="([^"]*)")?')
_DOC_RE = re.compile(r"export const SEVEN_DOC\s*=\s*(\{.*?\});", re.DOTALL)
_STOP = {"the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "it", "my", "i", "you", "your", "do", "how",
         "what", "where", "can", "does", "for", "with", "this", "that", "me", "seven", "change", "set", "page",
         "section", "see", "find", "use", "turn"}
_lock = threading.Lock()
_cache: Dict[str, Any] = {"mtime": None, "data": None}


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _resolve(src_dir: str, rel: str) -> Optional[str]:
    base = os.path.normpath(os.path.join(src_dir, rel))
    for cand in (base + ".jsx", base + ".js", os.path.join(base, "index.jsx")):
        if os.path.isfile(cand):
            return cand
    return None


def _texts(src: str) -> List[Tuple[str, str]]:
    """Ordered (kind, text) with kind = label | description."""
    out = []
    for t in _TEXT_RE.findall(src):
        t = re.sub(r"\s+", " ", t).strip()
        if not re.search(r"[A-Za-z]{3}", t) or "=>" in t or t.startswith(("//", "/*")):
            continue
        out.append(("description" if len(t) >= 28 else "label", t))
    return out


def _controls(files: List[str]) -> List[Dict[str, str]]:
    controls, seen = [], set()
    for path in files:
        last = None
        for kind, text in _texts(_read(path)):
            if kind == "label":
                if text.lower() in seen or len(text) > 45:
                    last = None
                    continue
                seen.add(text.lower())
                last = {"label": text, "description": "", "file": os.path.basename(path)}
                controls.append(last)
            elif last is not None and not last["description"]:
                last["description"] = text
    return controls


def _page_files(path: str) -> List[str]:
    files = [path]
    if os.path.basename(path).startswith("index."):
        folder = os.path.dirname(path)
        files += sorted(os.path.join(folder, f) for f in os.listdir(folder)
                        if f.endswith(".jsx") and os.path.join(folder, f) != path)
    return files


def source_hash(src_dir: str) -> str:
    h = hashlib.sha256()
    for root, _d, files in os.walk(src_dir):
        for f in sorted(files):
            if f.endswith((".jsx", ".js")):
                p = os.path.join(root, f)
                st = os.stat(p)
                h.update(f"{os.path.relpath(p, src_dir)}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def build(src_dir: str) -> Dict[str, Any]:
    """Generate the app map from frontend/src."""
    app = _read(os.path.join(src_dir, "App.jsx"))
    imports = {m.group("name"): m.group("path") for m in _IMPORT_RE.finditer(app)}
    pages = []
    for m in _ROUTE_RE.finditer(app):
        route, comp = m.group("path"), m.group("comp")
        file = _resolve(src_dir, imports.get(comp, "")) if comp in imports else None
        if not file:
            continue
        files = _page_files(file)
        text = _read(file)
        header = _HEADER_RE.search(text)
        doc: Dict[str, Any] = {}
        dm = _DOC_RE.search(text)
        if dm:
            try:
                doc = json.loads(dm.group(1))
            except ValueError:
                doc = {}
        controls = _controls(files)
        title = (header.group(1) if header else None) or (controls[0]["label"] if controls else comp)
        purpose = doc.get("purpose") or (header.group(2) if header and header.group(2) else "")
        pages.append({
            "id": route.strip("/") or "home", "route": route, "component": comp, "title": title,
            "purpose": purpose, "controls": controls[:80], "keywords": doc.get("keywords", []),
            "sections": [os.path.splitext(os.path.basename(f))[0] for f in files[1:]],
        })
    return {"app_map_version": 1, "source_hash": source_hash(src_dir), "pages": pages}


def write(data: Dict[str, Any], path: str = DATA_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    with _lock:
        _cache["mtime"] = None


def load(path: str = DATA_PATH) -> Dict[str, Any]:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {"pages": []}
    with _lock:
        if _cache["mtime"] == mtime and _cache["data"] is not None:
            return _cache["data"]
    try:
        data = json.loads(_read(path))
    except ValueError:
        data = {"pages": []}
    with _lock:
        _cache["mtime"], _cache["data"] = mtime, data
    return data


def find_frontend_src() -> Optional[str]:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.environ.get("SEVEN_FRONTEND_SRC"), os.path.join(base, "frontend", "src"),
                 os.path.join(os.environ.get("SEVEN_APP_PATH", ""), "frontend", "src")):
        if cand and os.path.isfile(os.path.join(cand, "App.jsx")):
            return cand
    return None


def refresh_if_stale(path: str = DATA_PATH) -> bool:
    """Rebuild the map when the frontend source changed (development checkouts)."""
    src = find_frontend_src()
    if not src:
        return False
    current = load(path).get("source_hash")
    if current == source_hash(src):
        return False
    write(build(src), path)
    return True


def _toks(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) > 1}


def search(question: str, limit: int = 3, path: str = DATA_PATH) -> List[Dict[str, Any]]:
    """Best matching pages/controls for a how-to question."""
    q = _toks(question)
    if not q:
        return []
    hits = []
    for page in load(path).get("pages", []):
        page_words = _toks(" ".join([page["title"], page.get("purpose", ""), page["id"],
                                     " ".join(page.get("keywords", []))]))
        base = len(q & page_words) + 2 * len(q & _toks(page["title"] + " " + page["id"]))
        best_ctrl, best = None, 0
        for c in page.get("controls", []):
            s = len(q & _toks(c["label"] + " " + c.get("description", ""))) * 2 - (0 if c["label"].lower() in
                                                                                      question.lower() else 0)
            if s > best:
                best_ctrl, best = c, s
        score = base + best
        if score:
            hits.append({"score": score, "page": page, "control": best_ctrl})
    hits.sort(key=lambda h: -h["score"])
    return hits[:limit]


def describe(hit: Dict[str, Any]) -> str:
    page, ctrl = hit["page"], hit["control"]
    where = f"{page['title']} (the {page['id']} page in the sidebar)"
    if ctrl:
        extra = f" {ctrl['description']}" if ctrl.get("description") else ""
        return f"That's in {where}, under \"{ctrl['label']}\".{extra}"
    purpose = f" {page['purpose']}." if page.get("purpose") else ""
    return f"Open {where}.{purpose}"
