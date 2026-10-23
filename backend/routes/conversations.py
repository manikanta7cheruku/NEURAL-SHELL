"""
backend/routes/conversations.py

Saved chats: list, search, open, rename, export, delete, start a new one, and
rate a message. There is no count limit; deletion is always an explicit user action.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _key() -> str:
    from brain_modules import session
    return session.resolve_key("default")


class NewChat(BaseModel):
    title: Optional[str] = None


class Rename(BaseModel):
    title: str


class Feedback(BaseModel):
    rating: str            # up | down
    note: Optional[str] = None


@router.get("/api/conversations")
def list_conversations(q: str = "", limit: int = 50, offset: int = 0, everyone: bool = False):
    """everyone=true lists every speaker's chats (owner, older 'default' history, enrolled voices)."""
    from memory import conversation_store as cstore
    key = None if everyone else _key()
    if q.strip():
        return {"query": q, "results": cstore.search(key, q, limit)}
    return {"conversations": cstore.list_conversations(key, limit, offset),
            "total": cstore.count_conversations(key)}


@router.post("/api/conversations")
def new_chat(req: NewChat):
    import brain
    return {"conversation_id": brain.new_conversation("default", req.title)}


@router.get("/api/conversations/current")
def current():
    import brain
    return {"conversation_id": brain.resolve_conversation("default", None)}


@router.get("/api/conversations/{conv_id}")
def open_chat(conv_id: str, limit: int = 300, before_id: Optional[int] = None, everyone: bool = False):
    from memory import conversation_store as cstore
    conv = cstore.get_conversation(conv_id)
    if not conv or (not everyone and conv["speaker_key"] != _key()):
        raise HTTPException(404, "Conversation not found")
    return {"conversation": conv, "messages": cstore.get_messages(conv_id, limit, before_id)}


@router.patch("/api/conversations/{conv_id}")
def rename(conv_id: str, req: Rename):
    from memory import conversation_store as cstore
    if not cstore.rename(conv_id, req.title):
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@router.get("/api/conversations/{conv_id}/export")
def export_chat(conv_id: str):
    from memory import conversation_store as cstore
    return cstore.export(conv_id=conv_id)


@router.delete("/api/conversations/{conv_id}")
def delete_chat(conv_id: str):
    from memory import conversation_store as cstore
    if not cstore.delete_conversation(conv_id):
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@router.post("/api/messages/{msg_id}/feedback")
def rate_message(msg_id: int, req: Feedback):
    """Thumbs up/down. Recorded as an outcome; it never creates a fact about the user."""
    from memory import conversation_store as cstore, learning_store
    msg = cstore.get_message(msg_id)
    if not msg or req.rating not in ("up", "down"):
        raise HTTPException(400, "Unknown message or rating")
    learning_store.record_outcome(_key(), "feedback", "answer", req.rating, (req.note or msg["content"])[:200],
                                  msg["conversation_id"])
    return {"ok": True}
