"""
backend/routes/knowledge.py
"""
from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi import File as FastAPIFile
import os
import shutil
import tempfile

router = APIRouter()

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx", ".xlsx"}
SUPPORTED_DISPLAY    = ".txt, .md, .pdf, .docx, .pptx, .xlsx"
MAX_FILE_MB          = 50


@router.get("/api/knowledge/stats")
def get_knowledge_stats():
    try:
        from knowledge import get_knowledge_stats as _get_stats
        from knowledge.indexer import get_index_manifest
        stats    = _get_stats()
        manifest = get_index_manifest()
        # Enrich sources with manifest metadata
        enriched = []
        for src in stats.get("sources", []):
            entry = manifest.get(src, {})
            enriched.append({
                "name":     src,
                "ext":      entry.get("ext", ""),
                "size_kb":  entry.get("size_kb", 0),
                "chunks":   entry.get("chunks", 0),
            })
        stats["source_details"] = enriched
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/knowledge/search")
def search_knowledge_endpoint(q: str):
    try:
        from knowledge import search_knowledge
        results = search_knowledge(q, top_k=5)
        return {"results": results or "No results found.", "query": q}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/knowledge/clear")
def clear_knowledge_endpoint():
    try:
        from knowledge import clear_knowledge
        clear_knowledge()
        # Also clear manifest
        from knowledge.indexer import MANIFEST_FILE
        if os.path.exists(MANIFEST_FILE):
            os.remove(MANIFEST_FILE)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/knowledge/file/{filename}")
def delete_knowledge_file(filename: str):
    try:
        from knowledge.indexer import remove_file
        success, msg = remove_file(filename)
        if not success:
            raise HTTPException(status_code=404, detail=msg)
        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/knowledge/upload")
async def upload_knowledge(file: UploadFile = FastAPIFile(...)):
    filename = file.filename or "upload"
    ext      = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {SUPPORTED_DISPLAY}"
        )

    # Size check
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.1f}MB. Max: {MAX_FILE_MB}MB"
        )

    # Save to custom dir
    from knowledge.indexer import CUSTOM_DIR
    os.makedirs(CUSTOM_DIR, exist_ok=True)
    dest = os.path.join(CUSTOM_DIR, filename)

    with open(dest, 'wb') as f:
        f.write(content)

    # Index it
    try:
        from knowledge.indexer import index_file
        success, chunks, msg = index_file(dest)
        if not success:
            raise HTTPException(status_code=422, detail=msg)
        return {
            "success":  True,
            "filename": filename,
            "chunks":   chunks,
            "message":  msg,
            "size_mb":  round(size_mb, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))