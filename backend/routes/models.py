"""
backend/routes/models.py

Language models for Settings and the setup wizard, from the one catalog in
brain_modules/model_catalog.py:

    GET    /api/models              catalog with installed / in use / recommended / fits, plus other installed models
    POST   /api/models/pull         {"name": ...} download a model in the background (Ollama)
    GET    /api/models/pull         download progress
    DELETE /api/models/{name}       remove a downloaded model to free disk space

Switching the model is a normal settings change (brain.model_name); Seven
applies it from the next message.
"""

import logging

from fastapi import APIRouter, HTTPException

_log = logging.getLogger("seven.models")
router = APIRouter()
OLLAMA = "http://127.0.0.1:11434"


def _installed() -> tuple:
    try:
        import requests
        r = requests.get(f"{OLLAMA}/api/tags", timeout=3)
        if r.status_code == 200:
            return True, [m["name"] for m in r.json().get("models", []) if m.get("name")]
    except Exception:
        pass
    return False, []


def _hardware() -> dict:
    try:
        from brain_modules import system_info
        snap = system_info.snapshot()
        gpu = snap.get("gpu") or {}
        return {"gpu": gpu.get("name"), "vram_gb": float(gpu.get("vram_gb") or 0),
                "ram_gb": float((snap.get("ram") or {}).get("total_gb") or 0), "has_gpu": bool(gpu.get("name"))}
    except Exception:
        return {"gpu": None, "vram_gb": 0.0, "ram_gb": 0.0, "has_gpu": False}


def _bootstrap():
    try:
        from backend import bootstrap
    except ModuleNotFoundError:
        import bootstrap
    return bootstrap


@router.get("/api/models", summary="Model catalog with what is installed, in use and recommended for this PC")
def list_models():
    from brain_modules import model_catalog
    running, installed = _installed()
    hw = _hardware()
    rec = model_catalog.recommend(hw["vram_gb"], hw["ram_gb"], hw["has_gpu"])
    try:
        import config
        configured = (config.KEY.get("brain", {}).get("model_name") or "auto").strip()
    except Exception:
        configured = "auto"
    try:
        import brain
        active = brain.MODEL_NAME
    except Exception:
        active = configured
    inst_bases = {n.removesuffix(":latest"): n for n in installed}
    models = []
    for m in model_catalog.CATALOG:
        models.append({**m, "installed": m["id"] in inst_bases,
                       "in_use": m["id"] in (active.removesuffix(":latest"), configured.removesuffix(":latest")),
                       "recommended": m["id"] == rec["id"],
                       "fits": model_catalog.fits(m, hw["vram_gb"], hw["ram_gb"], hw["has_gpu"])})
    catalog_ids = {m["id"] for m in model_catalog.CATALOG}
    others = [n for n in installed if n.removesuffix(":latest") not in catalog_ids]
    return {"ollama_running": running, "models": models, "other_installed": others, "configured": configured,
            "active": active, "recommended": rec, "hardware": hw, "pull": _bootstrap().get_state().get("model_pull")}


@router.post("/api/models/pull", summary="Download a model in the background")
def pull_model(data: dict):
    name = (data or {}).get("name", "").strip()
    if not name:
        raise HTTPException(400, "Choose a model to download.")
    running, _ = _installed()
    if not running:
        raise HTTPException(503, "Ollama isn't running, so models can't be downloaded right now.")
    started = _bootstrap().run_model_pull(name)
    if started is None:
        raise HTTPException(409, "Another model is still downloading. Try again when it finishes.")
    return {"started": True, "name": name}


@router.get("/api/models/pull", summary="Progress of the current model download")
def pull_status():
    return _bootstrap().get_state().get("model_pull") or {}


@router.delete("/api/models/{name:path}", summary="Remove a downloaded model")
def delete_model(name: str):
    try:
        import config
        if (config.KEY.get("brain", {}).get("model_name") or "").removesuffix(":latest") == name.removesuffix(":latest"):
            raise HTTPException(409, "That model is in use. Switch to another one first.")
    except HTTPException:
        raise
    except Exception:
        pass
    try:
        import requests
        r = requests.delete(f"{OLLAMA}/api/delete", json={"name": name}, timeout=20)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"Ollama couldn't remove {name}.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Ollama isn't reachable: {exc}")
    return {"removed": name}
