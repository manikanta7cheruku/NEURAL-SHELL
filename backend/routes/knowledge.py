"""
backend/routes/knowledge.py
Handles: /api/knowledge/*
"""

from fastapi import APIRouter, HTTPException, Request
import os

router = APIRouter()


@router.get("/api/knowledge/stats")
def get_knowledge_stats():
    """Get knowledge base statistics."""
    try:
        from knowledge import get_knowledge_stats as _get_stats
        return _get_stats()
    except ImportError:
        return {"total_chunks": 0, "sources": [], "storage_mb": 0}


@router.get("/api/knowledge/search")
def search_knowledge(q: str):
    """Search the knowledge base."""
    try:
        from knowledge import search_knowledge as _search
        results = _search(q)
        return {"query": q, "results": results if results else "No results found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/knowledge/clear")
def clear_knowledge():
    """Clear the knowledge base."""
    try:
        from knowledge import clear_knowledge as _clear
        success = _clear()
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _register_upload_endpoint(app):
    """
    Register /api/knowledge/upload only if python-multipart is installed.
    Called from api_server.py after app creation.
    Avoids import-time crash when multipart is not installed.
    """
    try:
        import multipart  # noqa: F401
        _multipart_ok = True
    except ImportError:
        _multipart_ok = False

    if _multipart_ok:
        from fastapi import UploadFile, File as FastAPIFile
        from backend.api_server import check_limit, plan_limit_error

        @app.post("/api/knowledge/upload")
        async def upload_knowledge(file: UploadFile = FastAPIFile(...)):
            """Upload a file to the knowledge base. Enforces plan limit."""
            try:
                _appdata  = os.environ.get("APPDATA", os.path.expanduser("~"))
                _know_dir = os.path.join(_appdata, "SEVEN", "seven_data", "knowledge")
                if os.path.exists(_know_dir):
                    file_count = len([
                        f for f in os.listdir(_know_dir)
                        if os.path.isfile(os.path.join(_know_dir, f))
                    ])
                else:
                    file_count = 0

                limit_check = check_limit("knowledge_files", file_count)
                if not limit_check["allowed"]:
                    raise plan_limit_error("knowledge_files", limit_check)

                from knowledge.indexer import index_file
                os.makedirs(_know_dir, exist_ok=True)
                file_path = os.path.join(_know_dir, file.filename)
                content   = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                chunks = index_file(file_path)
                return {
                    "success":        True,
                    "filename":       file.filename,
                    "chunks_indexed": chunks,
                    "usage": {
                        "current": file_count + 1,
                        "limit":   limit_check["limit"],
                        "tier":    limit_check["tier"]
                    }
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    else:
        @app.post("/api/knowledge/upload")
        async def upload_knowledge_unavailable(request: Request):
            """Fallback when python-multipart not installed."""
            return {
                "success": False,
                "error":   "python-multipart not installed. Run setup wizard."
            }
        print("[API] python-multipart not installed — upload endpoint in fallback mode")