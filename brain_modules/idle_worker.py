"""
brain_modules/idle_worker.py

Background worker for everything that must not slow a reply down.

JOBS:
    learn               extract and store facts from a user message
    apply_correction    replace a stored value after "actually it's X"
    index_fact          write one fact into the semantic index (ChromaDB)
    store_conversation  save a finished exchange for the Memory page
    reindex             repair any fact missing from the index
    migrate             one-time cleanup of poisoned legacy facts

Layer code enqueues in microseconds and returns. The worker is a daemon
thread with a bounded queue; a full queue drops the OLDEST job, and a handler
exception never kills the loop. Legacy job names (extract_facts) still work.
"""

import logging
import queue
import threading
from typing import Any, Dict, Optional

_log = logging.getLogger("seven.worker")

_QUEUE_MAX = 200
_POLL_SECONDS = 0.5
_STARTUP_JOBS_DELAY = 45.0   # keep CPU free while the first messages are served

_job_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX)
_worker: Optional[threading.Thread] = None
_started = False
_start_lock = threading.Lock()
_shutdown = threading.Event()


def _resolve(payload: Dict[str, Any]) -> str:
    from brain_modules import session
    return session.resolve_key(payload.get("speaker_id", "default"))


def _job_learn(payload: Dict[str, Any]) -> None:
    from brain_modules import fact_extractor
    from memory import fact_service
    text = payload.get("user_input") or payload.get("text") or ""
    key = _resolve(payload)
    for fact in fact_extractor.extract_facts(text):
        fact_service.remember(key, fact, source_text=text)


def _job_apply_correction(payload: Dict[str, Any]) -> None:
    from memory import fact_service
    old, new = payload.get("old_value"), payload.get("new_value")
    if old and new:
        fact_service.apply_correction(_resolve(payload), old, new, payload.get("raw_text", ""))


def _job_index_fact(payload: Dict[str, Any]) -> None:
    from memory import fact_service
    fact_service.index_fact(int(payload["id"]), payload.get("old_chroma_id"))


def _job_store_conversation(payload: Dict[str, Any]) -> None:
    from memory import core as memory_core
    inst = memory_core._get_instance()
    if inst:
        inst.store_conversation(
            user_input=payload["user_input"], seven_response=payload["response"],
            user_id=payload["speaker_key"], source=payload.get("source", "chat"))


def _job_reindex(payload: Dict[str, Any]) -> None:
    from memory import fact_service
    n = fact_service.reindex_pending()
    if n:
        _log.info("reindexed %d facts", n)


def _job_migrate(payload: Dict[str, Any]) -> None:
    from memory import facts_store, fact_service
    if facts_store.meta_get("legacy_migration_v2") == "done":
        return
    stats = fact_service.migrate_legacy()
    facts_store.meta_set("legacy_migration_v2", "done")
    _log.info("legacy memory migration: %s", stats)


_HANDLERS = {
    "learn": _job_learn,
    "extract_facts": _job_learn,           # legacy name
    "apply_correction": _job_apply_correction,
    "index_fact": _job_index_fact,
    "store_conversation": _job_store_conversation,
    "reindex": _job_reindex,
    "migrate": _job_migrate,
}


def _loop() -> None:
    _log.info("background worker started")
    while not _shutdown.is_set():
        try:
            job = _job_queue.get(timeout=_POLL_SECONDS)
        except queue.Empty:
            continue
        handler = _HANDLERS.get(job.get("type"))
        if handler:
            try:
                handler(job.get("payload", {}))
            except Exception as exc:
                _log.warning("job %s failed: %s", job.get("type"), exc, exc_info=True)
        _job_queue.task_done()
    _log.info("background worker stopped")


def _ensure_started() -> None:
    global _worker, _started
    if _started:
        return
    with _start_lock:
        if _started:
            return
        _worker = threading.Thread(target=_loop, name="SevenIdleWorker", daemon=True)
        _worker.start()
        _started = True
        for job_type in ("migrate", "reindex"):
            timer = threading.Timer(_STARTUP_JOBS_DELAY, enqueue, args=(job_type, {}))
            timer.daemon = True
            timer.start()


def enqueue(job_type: str, payload: Dict[str, Any]) -> bool:
    """Queue a job without blocking. Drops the oldest job if the queue is full."""
    _ensure_started()
    item = {"type": job_type, "payload": payload}
    try:
        _job_queue.put_nowait(item)
        return True
    except queue.Full:
        try:
            _job_queue.get_nowait()
            _job_queue.put_nowait(item)
            return True
        except Exception:
            return False


def queue_size() -> int:
    """Pending job count."""
    return _job_queue.qsize()


def run_sync(job_type: str, payload: Dict[str, Any]) -> None:
    """Run a job inline. Used by tests and by the memory doctor script."""
    handler = _HANDLERS[job_type]
    handler(payload)


def shutdown(timeout: float = 5.0) -> None:
    """Stop the worker and wait for it."""
    _shutdown.set()
    if _worker and _worker.is_alive():
        _worker.join(timeout=timeout)
