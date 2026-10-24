"""
backend/routes/knowledge.py

The document library behind the Knowledge page and the Console paperclip (knowledge/store.py does the work).
Uploads return at once with status "reading"; the page polls /api/knowledge/documents for progress.
"""
import os
import tempfile
import threading
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter()

MAX_FILE_MB = 50


def _store():
    from knowledge import store
    return store


threading.Thread(target=lambda: _store().start(), name="seven-knowledge-start", daemon=True).start()


def _public(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in ("path", "hash")}


@router.get("/api/knowledge/documents", summary="Documents in the library, with reading progress")
def list_documents():
    store = _store()
    from backend.api_server import check_limit
    docs = store.documents()
    limit = check_limit("knowledge_files", len(docs))
    return {"documents": [_public(d) for d in docs], "totals": store.stats(),
            "limit": {"current": len(docs), "limit": limit["limit"], "tier": limit["tier"]}}


@router.post("/api/knowledge/documents", summary="Add a document to the library")
async def add_document(file: UploadFile = File(...), conversation_id: Optional[str] = Form(None)):
    from backend.api_server import check_limit, plan_limit_error
    from knowledge.extract import SUPPORTED, ExtractError
    store = _store()
    name = os.path.basename(file.filename or "document")
    if os.path.splitext(name)[1].lower() not in SUPPORTED:
        raise HTTPException(400, "That file type isn't supported. Use PDF, Word, PowerPoint, Excel, TXT or MD.")
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"That file is {len(content) / 1048576:.0f} MB. The limit is {MAX_FILE_MB} MB.")
    if not content:
        raise HTTPException(400, "That file is empty.")
    limit = check_limit("knowledge_files", len(store.documents()))
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(name)[1])
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        known = {d["hash"] for d in store.documents()}
        if not limit["allowed"] and store._file_hash(tmp) not in known:
            raise plan_limit_error("knowledge_files", limit)
        doc = store.add(tmp, name, conversation_id)
    except ExtractError as exc:
        raise HTTPException(400, str(exc))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return _public(doc)


@router.get("/api/knowledge/documents/{doc_id}", summary="One document with its sections and a preview")
def get_document(doc_id: str):
    store = _store()
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404, "That document isn't in your library.")
    out = _public(doc)
    entry = store._load(doc_id) if doc["status"] == "ready" else None
    out["preview"] = [{"label": c.get("label") or c.get("section") or "", "text": c["text"][:600]}
                      for c in (entry["chunks"][:3] if entry else [])]
    return out


@router.delete("/api/knowledge/documents/{doc_id}", summary="Remove a document")
def delete_document(doc_id: str):
    if not _store().remove(doc_id):
        raise HTTPException(404, "That document isn't in your library.")
    return {"success": True}


@router.post("/api/knowledge/documents/{doc_id}/retry", summary="Read a document again")
def retry_document(doc_id: str):
    doc = _store().retry(doc_id)
    if not doc:
        raise HTTPException(404, "That document isn't in your library.")
    return _public(doc)


@router.post("/api/knowledge/documents/{doc_id}/open", summary="Open the original file")
def open_document(doc_id: str):
    if not _store().open_original(doc_id):
        raise HTTPException(404, "The original file is missing.")
    return {"success": True}


@router.get("/api/knowledge/search", summary="Find passages in your documents")
def search(q: str, doc: Optional[List[str]] = None):
    hits = _store().search(q, doc or None, k=8)
    return {"query": q, "hits": [h for h in hits if h["keyword"] > 0 or h["score"] >= 0.3]}


class Attach(BaseModel):
    conversation_id: str
    documents: List[str]


@router.post("/api/knowledge/attach", summary="Attach documents to a chat")
def attach(req: Attach):
    _store().attach(req.conversation_id, req.documents)
    return {"documents": _store().attached(req.conversation_id)}


@router.get("/api/knowledge/attached", summary="Documents attached to a chat")
def attached(conversation_id: str):
    store = _store()
    return {"documents": [_public(d) for i in store.attached(conversation_id) if (d := store.get(i))]}


# ── Older endpoints still used by slash commands ─────────────────────────

@router.get("/api/knowledge/stats")
def get_knowledge_stats():
    from knowledge import get_knowledge_stats as stats
    return stats()


@router.delete("/api/knowledge/clear")
def clear_knowledge():
    _store().clear()
    return {"success": True}
