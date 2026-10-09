"""
memory/fact_service.py

The one place that reads and writes Seven's facts.

ARCHITECTURE:
    SQLite (facts_store)  = source of truth, written synchronously and atomically.
    ChromaDB user_facts   = semantic index DERIVED from SQLite, written in the
                            background and retried until it matches.

    This replaces "dual-write with rollback". If Chroma is down, slow or
    wiped, no fact is lost and the next reindex pass repairs it. Direct
    questions ("what is my favorite framework") are answered from SQLite by
    slot, in about a millisecond, without embeddings and without the model.

RECONCILIATION:
    The Memory page deletes facts from Chroma only. Before trusting an
    indexed row, recall checks that its Chroma document still exists; if it
    was deleted there, the row is deactivated. A user deleting a fact in the
    UI therefore really makes Seven forget it.
"""

import logging
import os
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from brain_modules import fact_extractor
from brain_modules.fact_extractor import ExtractedFact
from memory import facts_store

_log = logging.getLogger("seven.fact_service")

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="seven-mem")


# --------------------------------------------------------------------------
# ChromaDB access (never triggers a model load from the hot path by accident)
# --------------------------------------------------------------------------

def _chroma_facts(load: bool = True):
    """
    The user_facts collection, or None when memory is unavailable.

    load=False never starts the embedding model: it returns None if memory has
    not been initialised yet. The hot path (reconciliation during recall) uses
    this so a direct answer is never delayed by a multi-second model load.
    """
    if os.environ.get("SEVEN_DISABLE_CHROMA") == "1":   # tests and diagnostics
        return None
    try:
        from memory import core as _core
        if not load and getattr(_core, "_instance", None) is None:
            return None
        inst = _core._get_instance()
        return inst.user_facts if inst else None
    except Exception as exc:
        _log.debug("chroma unavailable: %s", exc)
        return None


def _fact_limit() -> int:
    """Per-tier fact cap (-1 = unlimited). Mirrors the existing plan limits."""
    try:
        import voice_limits
        tier = voice_limits.get_tier()
    except Exception:
        tier = "free"
    return {"free": 7, "pro": 77, "ultimate": -1}.get(tier, 7)


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def _enforce_limit(speaker_key: str, keep_id: int) -> int:
    """Evict the least recently updated facts over the plan limit. Returns evicted count."""
    limit = _fact_limit()
    if limit == -1:
        return 0
    rows = [r for r in facts_store.all_active(speaker_key)
            if r.get("category") != "style" and r["id"] != keep_id]
    evicted = 0
    overflow = len(rows) + 1 - limit
    for row in sorted(rows, key=lambda r: r["updated_at"])[:max(0, overflow)]:
        facts_store.deactivate(row["id"])
        _unindex(row.get("chroma_id"))
        evicted += 1
    return evicted


def remember(speaker_key: str, fact: ExtractedFact, source_text: str = "",
             index: bool = True) -> Dict[str, Any]:
    """
    Persist one fact. SQLite is written before this returns; the semantic
    index update is queued for the background worker.
    """
    result = facts_store.upsert_fact(
        speaker_key, fact.key, fact.value, fact.text, category=fact.category,
        source_text=source_text, confidence=fact.confidence)
    if result["status"] != "unchanged":
        result["evicted"] = _enforce_limit(speaker_key, result["id"])
        if index:
            try:
                from brain_modules import idle_worker
                idle_worker.enqueue("index_fact", {
                    "id": result["id"], "old_chroma_id": result.get("old_chroma_id")})
            except Exception as exc:
                _log.debug("index enqueue failed (reindex will repair): %s", exc)
    return result


def index_fact(fact_id: int, old_chroma_id: Optional[str] = None) -> bool:
    """Write one fact to the semantic index and drop the superseded document."""
    row = facts_store.get_by_id(fact_id)
    if not row or not row["active"] or row.get("category") == "style":
        return False
    col = _chroma_facts()
    if col is None:
        return False
    cid = f"sqlf_{fact_id}"
    try:
        col.upsert(ids=[cid], documents=[row["value"]], metadatas=[{
            "category": row["category"], "timestamp": row["updated_at"],
            "user_id": row["speaker_id"], "type": "fact", "key": row.get("key") or "",
            "sql_id": fact_id}])
        facts_store.mark_indexed(fact_id, cid)
        if old_chroma_id and old_chroma_id != cid:
            _unindex(old_chroma_id)
        return True
    except Exception as exc:
        _log.warning("index_fact %s failed (will retry): %s", fact_id, exc)
        return False


def _unindex(chroma_id: Optional[str]) -> None:
    if not chroma_id:
        return
    col = _chroma_facts()
    if col is None:
        return
    try:
        col.delete(ids=[chroma_id])
    except Exception as exc:
        _log.debug("unindex %s failed: %s", chroma_id, exc)


def reindex_pending(limit: int = 50) -> int:
    """Index every active fact that is not in Chroma yet. Returns how many succeeded."""
    done = 0
    for row in facts_store.get_unindexed(limit):
        if index_fact(row["id"]):
            done += 1
    return done


# --------------------------------------------------------------------------
# Recall
# --------------------------------------------------------------------------

def _reconcile(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop rows whose Chroma document was deleted from the Memory page."""
    indexed = [r for r in rows if r and r.get("indexed") and r.get("chroma_id")]
    if not indexed:
        return [r for r in rows if r]
    col = _chroma_facts(load=False)
    if col is None:
        return [r for r in rows if r]
    try:
        present = set(col.get(ids=[r["chroma_id"] for r in indexed]).get("ids", []))
    except Exception:
        return [r for r in rows if r]
    alive = []
    for r in rows:
        if not r:
            continue
        if r.get("indexed") and r.get("chroma_id") and r["chroma_id"] not in present:
            facts_store.deactivate(r["id"])
            continue
        alive.append(r)
    return alive


def _join(values: List[str]) -> str:
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " and " + values[-1]


def answer_recall(speaker_key: str, recall) -> Optional[str]:
    """
    Answer a RecallQuery from stored slots. Returns the reply text or None.
    Terse by design: "What is my favorite framework?" -> "React."
    """
    if recall.kind in ("likes", "dislikes"):
        rows = _reconcile(facts_store.list_by_prefix(speaker_key, f"{recall.kind}:"))
        values = [r["raw_value"] for r in rows if r.get("raw_value")][:6]
        if not values:
            return None
        return f"You {'like' if recall.kind == 'likes' else 'dislike'} {_join(values)}."

    row = facts_store.find_by_attr(speaker_key, recall.key, recall.aliases)
    rows = _reconcile([row]) if row else []
    if not rows:
        return None
    value = rows[0].get("raw_value") or ""
    if not value:
        return None
    if recall.key == "age":
        return f"You're {value}."
    return f"{value}."


def semantic_facts(speaker_key: str, query: str, min_relevance: float = 0.70,
                   k: int = 3) -> List[str]:
    """
    Semantic search over this speaker's facts, relevance-thresholded.
    Poisoned legacy entries are filtered out before they can reach a prompt.
    """
    col = _chroma_facts()
    if col is None:
        return []
    try:
        total = col.count()
        if total == 0:
            return []
        res = col.query(query_texts=[query], n_results=min(k * 3, total),
                        where={"user_id": speaker_key})
    except Exception as exc:
        _log.debug("semantic search failed: %s", exc)
        return []

    docs = (res.get("documents") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    out: List[str] = []
    for i, doc in enumerate(docs):
        relevance = 1.0 - (dists[i] / 2.0) if i < len(dists) else 0.0
        meta = metas[i] if i < len(metas) and metas[i] else {}
        if relevance < min_relevance or meta.get("category") == "identity":
            continue
        if not fact_extractor.is_clean_fact_text(doc) or doc in out:
            continue
        out.append(doc)
        if len(out) >= k:
            break
    return out


def semantic_facts_async(speaker_key: str, query: str, min_relevance: float = 0.70,
                         k: int = 3) -> Future:
    """Start semantic search without blocking the pipeline."""
    return _pool.submit(semantic_facts, speaker_key, query, min_relevance, k)


# --------------------------------------------------------------------------
# Corrections and migration
# --------------------------------------------------------------------------

def _has_token(haystack: str, needle: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(needle)}(?![A-Za-z0-9])", haystack, re.IGNORECASE) is not None


def apply_correction(speaker_key: str, old_value: str, new_value: str,
                     raw_text: str = "") -> Optional[Dict[str, Any]]:
    """
    Replace a previously stored value. Only a fact that really contains the old
    value (as a whole token) is changed; ambiguous or missing matches do nothing.
    """
    if not old_value or not new_value or len(old_value) < 2:
        return None
    candidates = [r for r in facts_store.all_active(speaker_key)
                  if r.get("category") != "style" and r.get("key")
                  and (_has_token(r.get("raw_value") or "", old_value)
                       or _has_token(r["value"], old_value))]
    if not candidates:
        return None
    target = max(candidates, key=lambda r: r["updated_at"])
    raw_old = target.get("raw_value") or ""
    new_raw = (new_value if raw_old.strip().casefold() == old_value.strip().casefold()
               else re.sub(re.escape(old_value), new_value, raw_old, flags=re.IGNORECASE))
    new_text = re.sub(re.escape(old_value), new_value, target["value"], flags=re.IGNORECASE)
    fact = ExtractedFact(target["key"], new_raw, new_text, target["category"], 0.9, True)
    result = remember(speaker_key, fact, source_text=raw_text)
    result["text"] = new_text
    return result


def migrate_legacy() -> Dict[str, int]:
    """
    One-time repair of facts written by the old extractor.

        "User said: I love pizza"     -> re-extracted into a clean slot fact
        "User's name is What You"     -> deleted
        any other invalid legacy doc  -> deleted
    """
    stats = {"scanned": 0, "converted": 0, "removed": 0}
    col = _chroma_facts()
    if col is None:
        return stats
    try:
        data = col.get()
    except Exception as exc:
        _log.warning("migration read failed: %s", exc)
        return stats

    ids = data.get("ids") or []
    docs = data.get("documents") or []
    metas = data.get("metadatas") or []
    for i, cid in enumerate(ids):
        if cid.startswith("sqlf_"):
            continue
        doc = docs[i] if i < len(docs) else ""
        meta = (metas[i] if i < len(metas) else None) or {}
        stats["scanned"] += 1
        if fact_extractor.is_clean_fact_text(doc):
            continue
        speaker = meta.get("user_id") or "default"
        original = fact_extractor.rewrite_legacy(doc)
        converted = False
        if original:
            for f in fact_extractor.extract_facts(original):
                remember(speaker, f, source_text=original, index=True)
                converted = True
        try:
            col.delete(ids=[cid])
        except Exception as exc:
            _log.debug("legacy delete failed: %s", exc)
            continue
        stats["converted" if converted else "removed"] += 1
    return stats


def stats() -> Dict[str, Any]:
    """Counts for diagnostics."""
    col = _chroma_facts()
    try:
        chroma_count = col.count() if col is not None else None
    except Exception:
        chroma_count = None
    return {
        "sqlite_active": facts_store.count_facts(),
        "unindexed": len(facts_store.get_unindexed(1000)),
        "chroma_documents": chroma_count,
    }
