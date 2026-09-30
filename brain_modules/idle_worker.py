"""
=============================================================================
brain_modules/idle_worker.py

Background worker thread for fact extraction and memory processing.
Runs on a daemon thread with a bounded queue.
Layer 07 enqueues jobs in under 1ms and returns immediately.

The worker processes jobs during idle windows so chat latency stays flat.

Jobs supported:
    extract_facts : Run heuristic fact extraction on user input
    apply_correction : Process a detected correction into the facts store

Design principles:
    - Zero impact on hot path (enqueue is O(1), never blocks)
    - Graceful degradation (if queue is full, drop oldest job)
    - Idempotent (safe to enqueue same job twice)
    - Silent failure (worker exceptions never propagate)
=============================================================================
"""

import queue
import threading
import time
import traceback
from typing import Any, Dict, Optional
from colorama import Fore


_QUEUE_MAX_SIZE = 200
_IDLE_POLL_SECONDS = 0.5

_job_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX_SIZE)
_worker_thread: Optional[threading.Thread] = None
_worker_started = False
_start_lock = threading.Lock()
_shutdown_flag = threading.Event()


def _process_extract_facts(payload: Dict[str, Any]):
    """
    Runs heuristic fact extraction using the existing memory engine
    and mirrors the extracted fact into the structured SQLite facts store.
    """
    try:
        from memory import seven_memory, facts_store
        user_input = payload.get("user_input", "")
        speaker_id = payload.get("speaker_id", "default")
        if not user_input:
            return

        # 1. Existing ChromaDB path (semantic search backing store)
        if seven_memory:
            try:
                seven_memory.extract_and_store_facts(user_input, user_id=speaker_id)
            except Exception as chroma_err:
                print(Fore.YELLOW + f"[IDLE_WORKER] ChromaDB fact write failed: {chroma_err}")

        # 2. Structured SQLite path (mirrored for structured queries + corrections)
        try:
            extracted = _extract_structured_fact(user_input)
            if extracted:
                facts_store.add_fact(
                    value=extracted["value"],
                    speaker_id=speaker_id,
                    category=extracted["category"],
                    key=extracted.get("key"),
                    source_text=user_input,
                )
                print(Fore.CYAN + f"[IDLE_WORKER] Mirrored structured fact: {extracted['value']}")
        except Exception as sql_err:
            print(Fore.YELLOW + f"[IDLE_WORKER] Structured mirror failed: {sql_err}")
    except Exception as e:
        print(Fore.YELLOW + f"[IDLE_WORKER] extract_facts failed: {e}")


def _extract_structured_fact(user_input: str) -> Optional[Dict[str, Any]]:
    """
    Heuristic extractor for the structured SQLite store.
    Mirrors the logic in memory.core.SevenMemory.extract_and_store_facts
    but returns a structured dict instead of writing to ChromaDB.
    Returns None if no fact detected.
    """
    if not user_input:
        return None
    clean = user_input.lower().strip()

    # Name changes
    if "my name is" in clean or "call me" in clean:
        import re
        pivot = "my name is" if "my name is" in clean else "call me"
        raw = user_input.lower().split(pivot)[-1].strip()
        raw = re.split(r'\bnot\b|\bokay\b|\bplease\b|\bright\b|\bok\b', raw)[0]
        raw = raw.strip().rstrip(".,!?").strip()
        words = [w for w in raw.split()
                 if w not in {"please", "okay", "ok", "right", "now", "just"}]
        name = " ".join(words[:2]).strip().title()
        if name:
            return {"value": f"User's name is {name}", "category": "identity", "key": "name"}

    # Favorites (statements, not questions)
    if "my favorite" in clean or "my favourite" in clean:
        question_starts = ["what", "which", "who", "when", "where", "how", "do", "can", "tell"]
        if not any(clean.startswith(q) for q in question_starts):
            return {"value": f"User said: {user_input.strip()}", "category": "preference", "key": None}

    # Preferences
    if clean.startswith("i love ") or clean.startswith("i like ") or clean.startswith("i prefer "):
        return {"value": f"User said: {user_input.strip()}", "category": "preference", "key": None}

    # Personal identity
    if clean.startswith("i am a ") or clean.startswith("i am an "):
        return {"value": f"User said: {user_input.strip()}", "category": "personal", "key": None}

    # Work / study
    if "i work at" in clean or "i work as" in clean:
        return {"value": f"User said: {user_input.strip()}", "category": "personal", "key": "work"}
    if "i study at" in clean or ("i study" in clean and "studying" not in clean):
        return {"value": f"User said: {user_input.strip()}", "category": "personal", "key": "study"}

    # Explicit remember
    if clean.startswith("remember that") or clean.startswith("remember this"):
        fact = (
            user_input.split("that", 1)[-1].strip()
            if "that" in user_input
            else user_input.split("this", 1)[-1].strip()
        )
        return {"value": f"User asked to remember: {fact}", "category": "explicit", "key": None}

    # "Actually my X is Y" pattern (correction with no old value)
    if clean.startswith("actually"):
        stripped = user_input.strip()
        if len(stripped) > len("actually") + 2:
            return {"value": f"User said: {stripped}", "category": "correction", "key": None}

    return None


def _process_apply_correction(payload: Dict[str, Any]):
    """Handles a correction event by updating the structured facts store."""
    try:
        from memory import facts_store
        speaker_id = payload.get("speaker_id", "default")
        old_value = payload.get("old_value")
        new_value = payload.get("new_value")
        raw_text = payload.get("raw_text", "")

        if not new_value:
            return

        # If we know the old value, find the matching fact and supersede it
        if old_value:
            existing = facts_store.get_facts(speaker_id=speaker_id, active_only=True, limit=500)
            for fact in existing:
                if old_value.lower() in fact["value"].lower():
                    facts_store.supersede_fact(
                        old_id=fact["id"],
                        new_value=new_value,
                        source_text=raw_text
                    )
                    print(Fore.CYAN + f"[IDLE_WORKER] Superseded fact {fact['id']}: {old_value} -> {new_value}")
                    return

        # Fallback: add as a new correction fact
        facts_store.add_fact(
            value=new_value,
            speaker_id=speaker_id,
            category="correction",
            source_text=raw_text
        )
        print(Fore.CYAN + f"[IDLE_WORKER] Added correction fact: {new_value}")
    except Exception as e:
        print(Fore.YELLOW + f"[IDLE_WORKER] apply_correction failed: {e}")


_JOB_HANDLERS = {
    "extract_facts": _process_extract_facts,
    "apply_correction": _process_apply_correction,
}


def _worker_loop():
    """Main worker loop. Processes jobs off the queue until shutdown."""
    print(Fore.GREEN + "[IDLE_WORKER] Background worker started")
    while not _shutdown_flag.is_set():
        try:
            try:
                job = _job_queue.get(timeout=_IDLE_POLL_SECONDS)
            except queue.Empty:
                continue

            job_type = job.get("type")
            payload = job.get("payload", {})
            handler = _JOB_HANDLERS.get(job_type)
            if handler:
                try:
                    handler(payload)
                except Exception as e:
                    print(Fore.YELLOW + f"[IDLE_WORKER] Handler {job_type} error: {e}")
                    traceback.print_exc()
            _job_queue.task_done()
        except Exception as e:
            print(Fore.RED + f"[IDLE_WORKER] Loop error: {e}")
            time.sleep(1.0)
    print(Fore.YELLOW + "[IDLE_WORKER] Worker shut down")


def _ensure_started():
    """Lazily starts the worker thread on first enqueue."""
    global _worker_thread, _worker_started
    if _worker_started:
        return
    with _start_lock:
        if _worker_started:
            return
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="SevenIdleWorker",
            daemon=True
        )
        _worker_thread.start()
        _worker_started = True


def enqueue(job_type: str, payload: Dict[str, Any]) -> bool:
    """
    Enqueue a job for background processing. Non-blocking.

    Returns:
        True if enqueued, False if queue is full (job dropped).
    """
    _ensure_started()
    try:
        _job_queue.put_nowait({"type": job_type, "payload": payload})
        return True
    except queue.Full:
        # Drop oldest job to make room for new one
        try:
            _job_queue.get_nowait()
            _job_queue.put_nowait({"type": job_type, "payload": payload})
            return True
        except Exception:
            return False


def queue_size() -> int:
    """Current pending job count."""
    return _job_queue.qsize()


def shutdown(timeout: float = 5.0):
    """Signals worker to stop and waits for pending jobs."""
    _shutdown_flag.set()
    if _worker_thread and _worker_thread.is_alive():
        _worker_thread.join(timeout=timeout)