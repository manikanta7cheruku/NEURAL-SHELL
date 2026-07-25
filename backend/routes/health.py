"""
backend/routes/health.py
GET /api/health - System health check endpoint.

Returns status of all critical Seven subsystems.
Used for monitoring, debugging, and startup validation.
"""

import os
import time
import sqlite3
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health_check():
    """
    Check health of all Seven subsystems in parallel.
    Returns 200 always - caller reads the individual statuses.
    Response time target: under 200ms.
    """
    import concurrent.futures
    start = time.time()

    check_fns = {
        "memory_db":   _check_memory_db,
        "tasks_db":    _check_tasks_db,
        "triggers_db": _check_triggers_db,
        "ollama":      _check_ollama,
        "disk":        _check_disk,
        "config":      _check_config,
        "schedules":   _check_schedules,
    }

    checks = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            executor.submit(fn): name
            for name, fn in check_fns.items()
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                checks[name] = future.result(timeout=3)
            except Exception as e:
                checks[name] = {"ok": False, "error": str(e)}

    elapsed_ms = round((time.time() - start) * 1000, 1)
    all_ok = all(c["ok"] for c in checks.values())

    return {
        "healthy":    all_ok,
        "elapsed_ms": elapsed_ms,
        "checks":     checks,
        "version":    _get_version(),
    }


def _check_memory_db():
    try:
        from memory.core import MEMORY_DIR
        db = os.path.join(MEMORY_DIR, "chroma.sqlite3")
        if not os.path.exists(db):
            return {"ok": False, "error": "chroma.sqlite3 not found", "path": db}
        conn = sqlite3.connect(db, timeout=2)
        conv_count = 0
        fact_count = 0
        try:
            collections = {
                row[0]: row[1]
                for row in conn.execute("SELECT id, name FROM collections").fetchall()
            }
            for cid, cname in collections.items():
                seg_ids = [
                    r[0] for r in conn.execute(
                        "SELECT id FROM segments WHERE collection = ? AND scope = 'METADATA'",
                        (cid,)
                    ).fetchall()
                ]
                if seg_ids:
                    ph = ",".join("?" * len(seg_ids))
                    count = conn.execute(
                        f"SELECT COUNT(*) FROM embeddings WHERE segment_id IN ({ph})",
                        seg_ids
                    ).fetchone()[0]
                    if cname == "conversations":
                        conv_count = count
                    elif cname == "user_facts":
                        fact_count = count
        finally:
            conn.close()
        size_mb = round(os.path.getsize(db) / (1024 * 1024), 2)
        return {
            "ok":            True,
            "conversations": conv_count,
            "facts":         fact_count,
            "size_mb":       size_mb,
            "path":          MEMORY_DIR,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_tasks_db():
    try:
        from backend.routes.tasks import TASKS_DB
        if not os.path.exists(TASKS_DB):
            return {"ok": False, "error": "tasks.db not found"}
        conn = sqlite3.connect(TASKS_DB, timeout=2)
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        conn.close()
        return {"ok": True, "task_count": count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_triggers_db():
    try:
        from backend.routes.triggers import TRIGGERS_DB
        if not os.path.exists(TRIGGERS_DB):
            return {"ok": False, "error": "triggers.db not found"}
        conn = sqlite3.connect(TRIGGERS_DB, timeout=2)
        count = conn.execute("SELECT COUNT(*) FROM triggers WHERE enabled=1").fetchone()[0]
        conn.close()
        return {"ok": True, "active_triggers": count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_ollama():
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=1)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "models": models, "count": len(models)}
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": "Ollama not reachable", "detail": str(e)}


def _check_disk():
    try:
        import shutil
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        total, used, free = shutil.disk_usage(appdata)
        free_gb  = round(free  / (1024 ** 3), 2)
        total_gb = round(total / (1024 ** 3), 2)
        ok = free_gb > 0.5  # warn if less than 500MB free
        return {
            "ok":       ok,
            "free_gb":  free_gb,
            "total_gb": total_gb,
            "warning":  None if ok else "Less than 500MB free",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_config():
    try:
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        cfg_path = os.path.join(appdata, 'SEVEN', 'config.json')
        if not os.path.exists(cfg_path):
            return {"ok": False, "error": "config.json not found"}
        import json
        with open(cfg_path, 'r') as f:
            cfg = json.load(f)
        tier = cfg.get("license", {}).get("tier", "free")
        return {"ok": True, "tier": tier}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _check_schedules():
    try:
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        sched_path = os.path.join(appdata, 'SEVEN', 'schedules.json')
        if not os.path.exists(sched_path):
            return {"ok": True, "count": 0, "note": "no schedules file yet"}
        import json
        with open(sched_path, 'r') as f:
            scheds = json.load(f)
        active = sum(1 for s in scheds if s.get("status") == "active")
        return {"ok": True, "total": len(scheds), "active": active}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_version():
    try:
        here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        vf = os.path.join(here, "version.txt")
        if os.path.exists(vf):
            return open(vf).read().strip()
    except Exception:
        pass
    return "unknown"