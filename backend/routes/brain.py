"""
backend/routes/brain.py
Diagnostics and transparency for the brain.

    GET    /api/brain/diagnostics      model residency, latency, memory, worker
    GET    /api/brain/settings         every Brain Configuration setting: configured vs effective
    POST   /api/brain/settings/check   validate a value before saving
    GET    /api/brain/profile          "What I know about you": facts with evidence, goals, style, open questions
    DELETE /api/brain/facts/{id}       forget one fact
    POST   /api/brain/forget-all       forget everything learned about the user (needs confirm=true)
    POST   /api/brain/reset-session    clear short-term chat state
    POST   /api/brain/migrate-memory   run the legacy-memory cleanup now
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


def _key() -> str:
    from brain_modules import session
    return session.resolve_key("default")


class SettingCheck(BaseModel):
    path: str
    value: object


@router.get("/api/brain/diagnostics")
def diagnostics():
    out = {"ok": True}
    try:
        import brain
        from brain_modules import brain_settings, idle_worker, ollama_client
        loaded = ollama_client.loaded_models()
        out["model"] = brain_settings.model_status(__import__("config"), brain.MODEL_NAME, loaded or None)
        out["ollama_loaded_models"] = loaded
        out["worker_queue"] = idle_worker.queue_size()
    except Exception as exc:
        out["model"] = f"unavailable: {exc}"
    try:
        from brain_modules.observability import get_all_layer_stats
        stats = get_all_layer_stats()
        out["latency"] = [s for s in stats if s["layer"] in ("llm_first_token", "llm_total")]
        out["slowest_layers"] = stats[:5]
    except Exception:
        out["latency"] = []
    try:
        from memory import conversation_store, fact_service, learning_store
        out["memory"] = fact_service.stats()
        out["conversations"] = {"saved": conversation_store.count_conversations(),
                                "messages": conversation_store.count_messages()}
        out["outcomes"] = learning_store.recent_outcomes(10)
        from memory import limits
        out["storage"] = {"ok": limits.can_write(force=True)[0], "message": limits.can_write()[1]}
    except Exception as exc:
        out["memory"] = {"error": str(exc)}
    return out


@router.get("/api/brain/settings")
def settings():
    import config
    from brain_modules import brain_settings
    return {"settings": brain_settings.effective(config)}


@router.post("/api/brain/settings/check")
def check(req: SettingCheck):
    from brain_modules import brain_settings
    ok, value, note = brain_settings.validate_update(req.path, req.value)
    return {"accepted": ok, "value": value, "note": note}


@router.get("/api/brain/profile")
def profile():
    from memory import facts_store, learning_store
    key = _key()
    facts = []
    for r in facts_store.all_active(key):
        if r["category"] in ("style",):
            continue
        facts.append({"id": r["id"], "key": r.get("key"), "value": r.get("raw_value"), "text": r["value"],
                      "category": r["category"], "origin": r.get("origin") or "explicit",
                      "since": r.get("valid_from") or r["created_at"], "indexed": bool(r.get("indexed")),
                      "history": [h["raw_value"] for h in facts_store.get_history(key, r["key"])[:-1]] if r.get("key") else []})
    from brain_modules import learning
    return {"facts": facts, "goals": learning_store.list_goals(key),
            "style": learning.get_profile(key, use_cache=False),
            "open_questions": learning_store.list_gaps(key, "open")}


@router.delete("/api/brain/facts/{fact_id}")
def forget_fact(fact_id: int):
    from memory import fact_service, facts_store
    row = facts_store.get_by_id(fact_id)
    if not row or row["speaker_id"] != _key():
        raise HTTPException(404, "Fact not found")
    facts_store.deactivate(fact_id)
    fact_service._unindex(row.get("chroma_id"))
    return {"ok": True}


@router.post("/api/brain/forget-all")
def forget_all(confirm: bool = False):
    if not confirm:
        raise HTTPException(400, "Pass confirm=true to forget everything Seven learned about you.")
    from memory import fact_service, facts_store, learning_store
    key = _key()
    n = 0
    for r in facts_store.all_active(key):
        facts_store.deactivate(r["id"])
        fact_service._unindex(r.get("chroma_id"))
        n += 1
    learning_store.clear_speaker(key)
    return {"ok": True, "facts_forgotten": n, "note": "Conversations are kept; delete them from the chat list."}


@router.post("/api/brain/reset-session")
def reset_session():
    import brain
    brain.reset_session()
    return {"ok": True}


@router.post("/api/brain/migrate-memory")
def migrate_memory():
    from memory import fact_service
    return {"ok": True, "result": fact_service.migrate_legacy()}
