"""
backend/routes/files.py
File-related endpoints: open file, get file info.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

router = APIRouter()


class OpenFileRequest(BaseModel):
    path: str


@router.post("/api/files/open",
             summary="Open a file",
             description="Opens a file with its default application. Used by chat result cards.")
def open_file_endpoint(req: OpenFileRequest):
    """Open a file at the given path."""
    if not req.path or not req.path.strip():
        raise HTTPException(status_code=400, detail="Empty path")

    if not os.path.exists(req.path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        from hands.files import open_file
        open_file(req.path)
        return {"ok": True, "opened": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))