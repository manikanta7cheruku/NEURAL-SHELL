"""
knowledge/store.py

Seven's document library: the files a user adds on the Knowledge page or attaches in a chat.

WHY NOT CHROMADB HERE:
    A student's library is a few thousand passages at most. Plain NumPy search over that is instant, never crashes
    the process, and lets keyword and meaning search run over exactly the same passages.

HOW A DOCUMENT IS READ:
    extract.py splits it into pages, slides or sheets. Each is cut into overlapping passages of about 1,000
    characters that remember their page, so answers can cite "p. 12". Passages are embedded in batches by the
    same model memory uses. Reading runs on one background thread; the upload returns at once with status
    "reading" and the page shows progress.

HOW A QUESTION IS ANSWERED:
    Keyword search (BM25) and meaning search (cosine) each rank the passages; the two rankings are fused, so an
    exact term like "Kirchhoff" and a paraphrase like "the rule about currents at a junction" both land. Questions
    about the whole document (summaries, outlines, key points) get passages spread evenly across it instead.

LAYOUT (<data>/seven_data/knowledge/library):
    index.json            every document: name, type, pages, passages, words, status, headings
    conversations.json    which documents are attached to which chat
    <id>.json / <id>.npy  passages and their vectors
    files/<id><ext>       the original file
"""

import hashlib
import json
import math
import os
import queue
import re
import shutil
import threading
import time
import uuid
from collections import Counter
from typing import Dict, List, Optional

import numpy as np

from knowledge import extract

READER_VERSION = 2        # raise when extraction or chunking improves; older documents are read again
CHUNK_CHARS = 1000
OVERLAP_CHARS = 180
_BATCH = 64
_DIM = 384

_STOP = frozenset("""a an and are as at be been but by can could did do does for from had has have how i if in into is it
its me my of on or our so than that the their them then there these they this to was we were what when where which who
why will with would you your about tell explain give show list please document file pdf notes page""".split())

_WHOLE_DOC = re.compile(
    r"\b(summari[sz]e|summary|overview|outline|key (?:points|ideas|takeaways|concepts)|main (?:points|ideas|topics)|"
    r"table of contents|what is (?:this|the|it) (?:document|file|pdf|paper|book|chapter) about|what(?:'s| is) in (?:it|this|the)|"
    r"make (?:me )?notes|revision notes|study notes|cheat ?sheet|tl;?dr|gist|walk me through|"
    r"what (?:does|do) (?:it|this|the (?:document|file|pdf|paper|notes)) (?:say|cover|contain))\b", re.I)

_lock = threading.RLock()
_jobs: "queue.Queue[str]" = queue.Queue()
_worker: Optional[threading.Thread] = None
_cache: Dict[str, dict] = {}          # id -> {"chunks": [...], "vectors": ndarray, "tf": [Counter], "lens": [int]}


# ── Paths ─────────────────────────────────────────────────────────────────

def _root() -> str:
    base = os.environ.get("SEVEN_KNOWLEDGE_DIR")
    if not base:
        try:
            from seven_paths import paths
            base = paths.knowledge_dir
        except Exception:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seven_data", "knowledge")
    root = os.path.join(base, "library")
    os.makedirs(os.path.join(root, "files"), exist_ok=True)
    return root


def _read_json(name: str, default):
    try:
        with open(os.path.join(_root(), name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(name: str, value) -> None:
    path = os.path.join(_root(), name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _index() -> List[dict]:
    return _read_json("index.json", [])


def _save_index(docs: List[dict]) -> None:
    _write_json("index.json", docs)


def _update(doc_id: str, **fields) -> Optional[dict]:
    with _lock:
        docs = _index()
        for d in docs:
            if d["id"] == doc_id:
                d.update(fields)
                _save_index(docs)
                return d
    return None


# ── Embedding ─────────────────────────────────────────────────────────────

def _hash_vectors(texts: List[str]) -> np.ndarray:
    """Fallback when the real model is unavailable (tests, broken install): hashed word counts.
    Weak at paraphrase, but keyword search still finds the passages."""
    out = np.zeros((len(texts), _DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        for w in _tokens(t):
            out[i, int(hashlib.md5(w.encode()).hexdigest()[:6], 16) % _DIM] += 1.0
    return out


_embed_fn = None
_embed_name = ""


def _embedder():
    global _embed_fn, _embed_name
    if _embed_fn is None:
        fn, name = _hash_vectors, "hash"
        if os.environ.get("SEVEN_TEST") != "1":
            try:
                from memory.core import get_embedder
                ef = get_embedder()
                if "dummy" not in str(getattr(ef, "name", lambda: "")()):
                    fn, name = (lambda texts: np.asarray(ef(list(texts)), dtype=np.float32)), "minilm"
            except Exception:
                pass
        _embed_fn, _embed_name = fn, name
    return _embed_fn, _embed_name


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def _embed(texts: List[str], progress=None) -> np.ndarray:
    fn, _ = _embedder()
    parts = []
    for start in range(0, len(texts), _BATCH):
        parts.append(fn(texts[start:start + _BATCH]))
        if progress:
            progress(min(len(texts), start + _BATCH) / max(1, len(texts)))
    return _normalize(np.vstack(parts)) if parts else np.zeros((0, _DIM), dtype=np.float32)


# ── Text helpers ──────────────────────────────────────────────────────────

def _tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+(?:[.'][a-z0-9]+)*", text.lower())
    out = []
    for w in words:
        if w in _STOP or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def chunk_units(units: List[dict]) -> List[dict]:
    """Overlapping passages that keep their page label and the nearest heading above them."""
    chunks, heading = [], ""
    for unit in units:
        paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=# )", unit["text"]) if p.strip()]
        current = ""
        for para in paras:
            first = para.splitlines()[0].strip()
            title = first[2:].strip() if first.startswith("# ") else first if extract._looks_like_heading(first) else ""
            if title:
                if current.strip():                    # a new section starts a new passage
                    chunks.append({"text": current.strip(), "page": unit["page"], "label": unit["label"],
                                   "section": heading})
                    current = ""
                heading = title
            pieces = [para] if len(para) <= CHUNK_CHARS else re.split(r"(?<=[.!?])\s+", para)
            for piece in pieces:
                if current and len(current) + len(piece) + 2 > CHUNK_CHARS:
                    chunks.append({"text": current.strip(), "page": unit["page"], "label": unit["label"],
                                   "section": heading})
                    current = current[-OVERLAP_CHARS:].split(" ", 1)[-1] + " "
                current += piece + ("\n\n" if piece is para else " ")
        if current.strip():
            chunks.append({"text": current.strip(), "page": unit["page"], "label": unit["label"], "section": heading})
    return chunks


# ── Reading documents ─────────────────────────────────────────────────────

def _ensure_worker() -> None:
    global _worker
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, name="seven-knowledge-reader", daemon=True)
            _worker.start()


def _work() -> None:
    while True:
        doc_id = _jobs.get()
        try:
            _read(doc_id)
        except Exception as exc:                       # never let one bad file stop the reader
            _update(doc_id, status="failed", error=f"Something went wrong while reading ({exc.__class__.__name__}).")
        finally:
            _jobs.task_done()


def _read(doc_id: str) -> None:
    doc = get(doc_id)
    if not doc:
        return
    started = time.time()
    _update(doc_id, status="reading", progress=5, error="")
    try:
        units = extract.extract(doc["path"])
    except extract.ExtractError as exc:
        _update(doc_id, status="failed", error=str(exc), progress=0)
        return
    chunks = chunk_units(units)
    _update(doc_id, progress=20)
    vectors = _embed([c["text"] for c in chunks],
                     progress=lambda f: _update(doc_id, progress=20 + int(f * 75)))
    root = _root()
    with open(os.path.join(root, f"{doc_id}.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    np.save(os.path.join(root, f"{doc_id}.npy"), vectors.astype(np.float32))
    _cache.pop(doc_id, None)
    words = sum(len(u["text"].split()) for u in units)
    pages = max((u["page"] or 0) for u in units) or len(units)
    _update(doc_id, status="ready", progress=100, chunks=len(chunks), words=words, pages=pages,
            unit=_unit_name(doc["ext"], pages, words), headings=extract.headings(units),
            embedder=_embedder()[1], reader=READER_VERSION, read_ms=int((time.time() - started) * 1000))


def _unit_name(ext: str, n: int, words: int) -> str:
    noun = {".pdf": "page", ".pptx": "slide", ".xlsx": "sheet"}.get(ext)
    return f"{n} {noun}{'' if n == 1 else 's'}" if noun else f"{words:,} words"


def add(src_path: str, name: Optional[str] = None, conversation_id: Optional[str] = None) -> dict:
    """Copy a file into the library and queue it for reading. Returns its entry (status "reading")."""
    name = name or os.path.basename(src_path)
    ext = os.path.splitext(name)[1].lower()
    if ext not in extract.SUPPORTED:
        raise extract.ExtractError(f"{ext or 'This file type'} isn't supported. "
                                   "Use PDF, Word, PowerPoint, Excel, TXT or MD.")
    digest = _file_hash(src_path)
    with _lock:
        docs = _index()
        same = next((d for d in docs if d.get("hash") == digest and d["status"] != "failed"), None)
        if same:
            if conversation_id:
                attach(conversation_id, [same["id"]])
            return same
        doc_id = uuid.uuid4().hex[:12]
        dest = os.path.join(_root(), "files", f"{doc_id}{ext}")
        shutil.copyfile(src_path, dest)
        doc = {"id": doc_id, "name": name, "ext": ext, "path": dest, "hash": digest,
               "size_kb": round(os.path.getsize(dest) / 1024, 1), "added": time.time(),
               "status": "reading", "progress": 0, "error": "", "chunks": 0, "words": 0, "pages": 0,
               "headings": []}
        docs.insert(0, doc)
        _save_index(docs)
    if conversation_id:
        attach(conversation_id, [doc_id])
    _jobs.put(doc_id)
    _ensure_worker()
    return doc


def _file_hash(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def wait(doc_id: str, timeout: float = 60.0) -> Optional[dict]:
    """Block until a document is read (used by tests and the voice path)."""
    end = time.time() + timeout
    while time.time() < end:
        doc = get(doc_id)
        if not doc or doc["status"] in ("ready", "failed"):
            return doc
        time.sleep(0.05)
    return get(doc_id)


def retry(doc_id: str) -> Optional[dict]:
    doc = _update(doc_id, status="reading", progress=0, error="")
    if doc:
        _jobs.put(doc_id)
        _ensure_worker()
    return doc


def remove(doc_id: str) -> bool:
    with _lock:
        docs = _index()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if not doc:
            return False
        _save_index([d for d in docs if d["id"] != doc_id])
        links = _read_json("conversations.json", {})
        _write_json("conversations.json", {c: [i for i in ids if i != doc_id] for c, ids in links.items()})
    _cache.pop(doc_id, None)
    for path in (doc.get("path"), os.path.join(_root(), f"{doc_id}.json"), os.path.join(_root(), f"{doc_id}.npy")):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    return True


def open_original(doc_id: str) -> bool:
    """Open the stored copy of a document in its usual app."""
    doc = get(doc_id)
    if not doc or not os.path.isfile(doc.get("path", "")):
        return False
    if os.environ.get("SEVEN_TEST") == "1":
        return True
    try:
        os.startfile(doc["path"])
        return True
    except OSError:
        return False


def clear() -> None:
    for doc in documents():
        remove(doc["id"])


def documents() -> List[dict]:
    return _index()


def get(doc_id: str) -> Optional[dict]:
    return next((d for d in _index() if d["id"] == doc_id), None)


def ready_ids() -> List[str]:
    return [d["id"] for d in _index() if d["status"] == "ready"]


def has_documents() -> bool:
    return bool(ready_ids())


def stats() -> dict:
    docs = _index()
    size = sum(d.get("size_kb", 0) for d in docs)
    return {"documents": len(docs), "ready": sum(d["status"] == "ready" for d in docs),
            "pages": sum(d.get("pages", 0) for d in docs if d["status"] == "ready"),
            "words": sum(d.get("words", 0) for d in docs if d["status"] == "ready"),
            "passages": sum(d.get("chunks", 0) for d in docs if d["status"] == "ready"),
            "size_mb": round(size / 1024, 2)}


# ── Chats and documents ───────────────────────────────────────────────────

def attach(conversation_id: str, doc_ids: List[str]) -> None:
    if not conversation_id:
        return
    with _lock:
        links = _read_json("conversations.json", {})
        current = links.get(conversation_id, [])
        links[conversation_id] = current + [i for i in doc_ids if i not in current]
        _write_json("conversations.json", links)


def attached(conversation_id: str) -> List[str]:
    if not conversation_id:
        return []
    known = {d["id"] for d in _index()}
    return [i for i in _read_json("conversations.json", {}).get(conversation_id, []) if i in known]


# ── Search ────────────────────────────────────────────────────────────────

def _load(doc_id: str) -> Optional[dict]:
    if doc_id in _cache:
        return _cache[doc_id]
    root = _root()
    try:
        with open(os.path.join(root, f"{doc_id}.json"), "r", encoding="utf-8") as f:
            chunks = json.load(f)
        vectors = np.load(os.path.join(root, f"{doc_id}.npy"))
    except (OSError, ValueError):
        return None
    doc = get(doc_id) or {}
    if doc.get("embedder") != _embedder()[1] or len(vectors) != len(chunks):
        vectors = _embed([c["text"] for c in chunks])         # the model changed since this was read
        np.save(os.path.join(root, f"{doc_id}.npy"), vectors)
        _update(doc_id, embedder=_embedder()[1])
    tf = [Counter(_tokens(c["text"] + " " + c.get("section", ""))) for c in chunks]
    entry = {"chunks": chunks, "vectors": vectors, "tf": tf, "lens": [sum(t.values()) for t in tf]}
    _cache[doc_id] = entry
    return entry


def wants_whole_document(query: str) -> bool:
    return bool(_WHOLE_DOC.search(query or ""))


def search(query: str, doc_ids: Optional[List[str]] = None, k: int = 8) -> List[dict]:
    """Best passages for a question, fused from keyword and meaning search. Each hit carries
    doc_id, name, label, section, text, score (cosine) and keyword (share of query terms found)."""
    names = {d["id"]: d["name"] for d in _index() if d["status"] == "ready"}
    scope = [i for i in (doc_ids or names) if i in names]
    pool = []
    for doc_id in scope:
        entry = _load(doc_id)
        if entry:
            pool += [(doc_id, n) for n in range(len(entry["chunks"]))]
    if not pool:
        return []

    terms = list(dict.fromkeys(_tokens(query)))
    qv = _embed([query])[0]
    cos = np.concatenate([_cache[d]["vectors"] @ qv for d in scope if d in _cache])

    n_docs = len(pool)
    avg = sum(_cache[d]["lens"][n] for d, n in pool) / n_docs or 1.0
    df = Counter()
    for d, n in pool:
        tf = _cache[d]["tf"][n]
        df.update(t for t in terms if t in tf)
    bm25, cover = np.zeros(n_docs), np.zeros(n_docs)
    for i, (d, n) in enumerate(pool):
        tf, length = _cache[d]["tf"][n], _cache[d]["lens"][n]
        for t in terms:
            f = tf.get(t, 0)
            if f:
                idf = math.log(1 + (n_docs - df[t] + 0.5) / (df[t] + 0.5))
                bm25[i] += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * length / avg))
                cover[i] += 1
    if terms:
        cover /= len(terms)

    rank_cos = {int(i): r for r, i in enumerate(np.argsort(-cos)[:50])}
    rank_kw = {int(i): r for r, i in enumerate(np.argsort(-bm25)[:50]) if bm25[i] > 0}
    fused = Counter()
    for ranks in (rank_cos, rank_kw):
        for i, r in ranks.items():
            fused[i] += 1.0 / (60 + r)
    hits = []
    for i, _ in fused.most_common(k):
        d, n = pool[i]
        c = _cache[d]["chunks"][n]
        hits.append({"doc_id": d, "name": names[d], "index": n, "label": c.get("label"), "section": c.get("section", ""),
                     "text": c["text"], "score": round(float(cos[i]), 3), "keyword": round(float(cover[i]), 2),
                     "matched": int(round(cover[i] * len(terms)))})
    return hits


def relevant(hits: List[dict]) -> List[dict]:
    """Hits worth showing the model when the user did not point at a document."""
    return [h for h in hits if h["score"] >= 0.4
            or (h["keyword"] >= 0.5 and (h["score"] >= 0.3 or h.get("matched", 0) >= 2))]


def spread(doc_ids: List[str], budget_chars: int) -> List[dict]:
    """Passages spread evenly across whole documents, for summaries and outlines."""
    names = {d["id"]: d["name"] for d in _index() if d["status"] == "ready"}
    picked = []
    per_doc = budget_chars // max(1, len(doc_ids))
    for doc_id in doc_ids:
        entry = _load(doc_id) if doc_id in names else None
        if not entry:
            continue
        chunks = entry["chunks"]
        take = max(1, min(len(chunks), per_doc // CHUNK_CHARS))
        step = len(chunks) / take
        for j in range(take):
            n = int(j * step)
            c = chunks[n]
            picked.append({"doc_id": doc_id, "name": names[doc_id], "index": n, "label": c.get("label"),
                           "section": c.get("section", ""), "text": c["text"], "score": 1.0, "keyword": 1.0})
    return picked


def migrate_old_library() -> int:
    """Queue files from the old knowledge base (before this library existed) once, so nothing is lost."""
    if os.environ.get("SEVEN_TEST") == "1" or _read_json("migrated.json", None) is not None:
        return 0
    queued = 0
    try:
        from seven_paths import paths
        manifest_path = os.path.join(paths.knowledge_dir, "index_manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for name, entry in manifest.items():
            path = entry.get("path", "")
            if path and os.path.isfile(path):
                try:
                    add(path, name)
                    queued += 1
                except Exception:
                    pass
    except (OSError, ValueError, ImportError):
        pass
    _write_json("migrated.json", {"at": time.time(), "files": queued})
    return queued


def start() -> None:
    """At launch: finish documents that were still being read when Seven closed, read again the ones an older
    reader handled, and bring over the old library."""
    stuck = [d["id"] for d in _index()
             if d["status"] == "reading" or (d["status"] == "ready" and d.get("reader") != READER_VERSION)]
    for doc_id in stuck:
        _jobs.put(doc_id)
    if stuck:
        _ensure_worker()
    migrate_old_library()
