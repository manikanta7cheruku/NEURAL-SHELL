"""
backend/routes/brain.py
Diagnostics for the brain. Used for testing and for support.

    GET  /api/brain/diagnostics   model residency, latencies, memory health
    GET  /api/brain/facts         what Seven has learned (structured store)
    POST /api/brain/reset-session clear conversation state, keep facts
    POST /api/brain/migrate-memory re-run the legacy memory cleanup now

Register it in backend/api_server.py (see PATCHES.md).
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/brain/diagnostics")
def diagnostics():
    """One-call health view of the brain: is it fast, warm and healthy?"""
    out = {"ok": True}
    try:
        import brain
        out["model"] = brain.MODEL_NAME
    except Exception as exc:
        out["model"] = f"unavailable: {exc}"
    try:
        from brain_modules import idle_worker, ollama_client
        out["ollama_loaded_models"] = ollama_client.loaded_models()
        out["worker_queue"] = idle_worker.queue_size()
    except Exception as exc:
        out["ollama_loaded_models"] = f"unavailable: {exc}"
    try:
        from brain_modules.observability import get_all_layer_stats
        wanted = ("llm_first_token", "llm_total")
        out["latency"] = [s for s in get_all_layer_stats() if s["layer"] in wanted]
        out["slowest_layers"] = get_all_layer_stats()[:5]
    except Exception:
        out["latency"] = []
    try:
        from memory import fact_service
        out["memory"] = fact_service.stats()
    except Exception as exc:
        out["memory"] = {"error": str(exc)}
    return out


@router.get("/api/brain/facts")
def facts(speaker: str = ""):
    """Active facts in the structured store, newest first."""
    from memory import facts_store
    rows = facts_store.all_active(speaker or None)
    return {"count": len(rows), "facts": [
        {"id": r["id"], "speaker": r["speaker_id"], "key": r.get("key"), "value": r.get("raw_value"),
         "text": r["value"], "category": r["category"], "indexed": bool(r.get("indexed")),
         "updated_at": r["updated_at"]} for r in rows if r["category"] != "style"]}


@router.post("/api/brain/reset-session")
def reset_session():
    """Clear conversation state (history, greeting streaks). Facts are kept."""
    import brain
    brain.reset_session()
    return {"ok": True}


@router.post("/api/brain/migrate-memory")
def migrate_memory():
    """Run the legacy-memory cleanup immediately."""
    from memory import fact_service
    return {"ok": True, "result": fact_service.migrate_legacy()}
