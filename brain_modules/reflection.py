"""
brain_modules/reflection.py

Background self-maintenance. Runs on the idle worker, never on the reply path.

    summarize_pending()   one extractive summary per finished conversation
                          (shown in the chat list; no model call, no invention)
    consolidate()         expire stale knowledge gaps and keep memory tidy
    import_legacy_conversations()
                          move the old one-document-per-exchange history into
                          real conversations, once, without deleting anything
"""

import logging
import re
from typing import Dict

_log = logging.getLogger("seven.reflection")


def _summary(messages) -> str:
    users = [m["content"] for m in messages if m["role"] == "user"]
    if not users:
        return ""
    picks = sorted(users, key=len, reverse=True)[:3]
    picks = [re.sub(r"\s+", " ", p)[:90] for p in sorted(picks, key=users.index)]
    return f"{len(messages)} messages. You talked about: " + " | ".join(picks)


def summarize_pending(limit: int = 20) -> int:
    from memory import conversation_store
    n = 0
    for conv in conversation_store.unsummarized(limit=limit):
        text = _summary(conversation_store.get_messages(conv["id"], limit=200))
        if text:
            conversation_store.set_summary(conv["id"], text)
            n += 1
    return n


def consolidate() -> Dict[str, int]:
    from memory import learning_store
    return {"gaps_expired": learning_store.expire_old_gaps(30), "summaries": summarize_pending()}


def import_legacy_conversations() -> int:
    """Convert the old Chroma 'conversations' documents into stored conversations (idempotent)."""
    from memory import conversation_store, facts_store
    if facts_store.meta_get("legacy_conversations_imported") == "done":
        return 0
    try:
        from memory import core
        inst = core._get_instance()
        if inst is None:
            return 0
        data = inst.conversations.get()
    except Exception as exc:
        _log.debug("legacy conversations unavailable: %s", exc)
        return 0
    rows = []
    for meta in data.get("metadatas") or []:
        if meta and meta.get("user_input") and meta.get("seven_response"):
            rows.append(meta)
    rows.sort(key=lambda m: m.get("timestamp", ""))
    by_speaker: Dict[str, str] = {}
    for m in rows:
        speaker = (m.get("user_id") or "default").lower()
        if speaker not in by_speaker:
            by_speaker[speaker] = conversation_store.create_conversation(speaker, "Earlier conversations")
        conv = by_speaker[speaker]
        ts = m.get("timestamp")
        try:
            conversation_store.add_message(conv, "user", m["user_input"], source=m.get("source", "chat"), ts=ts)
            conversation_store.add_message(conv, "assistant", m["seven_response"], source=m.get("source", "chat"), ts=ts)
        except conversation_store.StorageUnavailable as exc:
            _log.warning("legacy import paused: %s", exc)
            return len(rows)
    facts_store.meta_set("legacy_conversations_imported", "done")
    return len(rows)
