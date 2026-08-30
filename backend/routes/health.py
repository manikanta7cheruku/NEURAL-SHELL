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


@router.get("/api/health", summary="System health check",
            description="Lightweight liveness probe. Returns 200 if the API server is running. Used by frontend to detect backend availability.")
def health_check():
    """Fast liveness check — no heavy imports, no DB queries. Returns in under 5ms."""
    return {"ok": True, "status": "running", "version": _get_version()}


@router.get("/api/health/full", summary="Full system health check",
            description="Checks all critical systems in parallel. Returns structured JSON.")
def health_check_full():
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
        here = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        )))
        vf = os.path.join(here, "version.txt")
        if os.path.exists(vf):
            return open(vf).read().strip()
    except Exception:
        pass
    return "unknown"


@router.get("/api/health/production",
            summary="Full production diagnostic",
            description="Returns complete system state for remote debugging. Includes process list, port status, daemon status, Python path, disk, memory.")
def production_health():
    """
    Deep production health check.
    Use this to remotely diagnose issues on any user machine.
    Ask user to open: http://127.0.0.1:7777/api/health/production
    and paste the JSON to you.
    """
    import sys
    import socket
    import platform
    import subprocess

    result = {
        "version":   _get_version(),
        "platform":  platform.platform(),
        "python":    sys.version,
        "exe":       sys.executable,
        "app_path":  os.environ.get('SEVEN_APP_PATH', 'not set'),
        "sys_path":  sys.path[:5],
        "ports":     {},
        "processes": {},
        "daemons":   {},
        "ollama":    {},
        "disk":      {},
        "env_vars":  {},
    }

    # Port checks
    # 7777  = Main API
    # 7778  = Panel server
    # 7779  = Panel host cmd
    # 7891  = Overlay IPC
    # 11434 = Ollama
    # 8888  = Admin dashboard
    for port in [7777, 7778, 7779, 7891, 11434, 8888]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            r = s.connect_ex(("127.0.0.1", port))
            s.close()
            result["ports"][str(port)] = "open" if r == 0 else "closed"
        except Exception:
            result["ports"][str(port)] = "error"

    # Process checks
    try:
        import psutil
        seven_procs = []
        for p in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
            try:
                name = p.info['name'] or ''
                cmd  = ' '.join(p.info['cmdline'] or [])
                if any(x in name.lower() for x in ['python', 'seven', 'ollama', 'electron']):
                    seven_procs.append({
                        "pid":    p.info['pid'],
                        "name":   name,
                        "status": p.info['status'],
                        "cmd":    cmd[:100]
                    })
            except Exception:
                pass
        result["processes"] = seven_procs
    except Exception as e:
        result["processes"] = {"error": str(e)}

    # Daemon file checks
    app_path = os.environ.get('SEVEN_APP_PATH', '')
    for daemon in [
        'schedule_daemon.py',
        'trigger_daemon.py',
    ]:
        path = os.path.join(app_path, daemon)
        result["daemons"][daemon] = os.path.exists(path)

    # Ollama check
    try:
        import urllib.request
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=3
        ) as r:
            import json
            data   = json.loads(r.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            result["ollama"] = {
                "running": True,
                "models":  models,
                "count":   len(models)
            }
    except Exception as e:
        result["ollama"] = {"running": False, "error": str(e)}

    # Key env vars
    for var in [
        'SEVEN_APP_PATH', 'SEVEN_ELECTRON_MODE',
        'APPDATA', 'LOCALAPPDATA', 'PYTHONPATH'
    ]:
        result["env_vars"][var] = os.environ.get(var, 'not set')

    # Disk
    try:
        import shutil
        appdata = os.environ.get('APPDATA', '')
        total, used, free = shutil.disk_usage(appdata or 'C:\\')
        result["disk"] = {
            "free_gb":  round(free  / (1024**3), 2),
            "total_gb": round(total / (1024**3), 2),
        }
    except Exception as e:
        result["disk"] = {"error": str(e)}

    return result

@router.get("/api/diagnostic",
            summary="User-friendly diagnostic page",
            description="Returns a human-readable diagnostic report. Open http://127.0.0.1:7777/api/diagnostic in a browser to see system status.")
def diagnostic():
    """
    Comprehensive diagnostic for remote debugging.
    Users can open this URL and paste the output to support.
    """
    import sys
    import platform
    import datetime

    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "seven_version": _get_version(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "status": "RUNNING",
        "checks": {}
    }

    # 1. Numpy
    try:
        import numpy as np
        report["checks"]["numpy"] = {
            "status": "OK",
            "version": np.__version__,
            "ndarray": hasattr(np, 'ndarray'),
            "_utils": hasattr(np, '_utils')
        }
    except Exception as e:
        report["checks"]["numpy"] = {"status": "BROKEN", "error": str(e)}

    # 2. Core packages
    for pkg in ['fastapi', 'uvicorn', 'pyttsx3', 'chromadb', 'sentence_transformers', 'faster_whisper']:
        try:
            __import__(pkg.replace('-', '_'))
            report["checks"][pkg] = {"status": "OK"}
        except Exception as e:
            report["checks"][pkg] = {"status": "MISSING", "error": str(e)[:100]}

    # 3. Ollama
    try:
        import urllib.request
        import json as _json
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            data = _json.loads(r.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            report["checks"]["ollama"] = {
                "status": "RUNNING",
                "models": models,
                "count": len(models)
            }
    except Exception as e:
        report["checks"]["ollama"] = {"status": "OFFLINE", "error": str(e)[:100]}

    # 4. Config
    try:
        import config
        report["checks"]["config"] = {
            "status": "OK",
            "setup_complete": config.KEY.get("setup_complete", False),
            "model": config.KEY.get("brain", {}).get("model_name", "unknown"),
            "tier": config.KEY.get("license", {}).get("tier", "free")
        }
    except Exception as e:
        report["checks"]["config"] = {"status": "ERROR", "error": str(e)[:100]}

    # 5. Memory
    try:
        from memory import seven_memory
        if seven_memory:
            stats = seven_memory.get_stats()
            report["checks"]["memory"] = {
                "status": "OK",
                "conversations": stats.get("total_conversations", 0),
                "facts": stats.get("total_facts", 0)
            }
        else:
            report["checks"]["memory"] = {"status": "NOT_INITIALIZED"}
    except Exception as e:
        report["checks"]["memory"] = {"status": "ERROR", "error": str(e)[:100]}

    # 6. Ports
    import socket
    for name, port in [("API", 7777), ("Ollama", 11434), ("Panel", 7778), ("Overlay", 7891)]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            r = s.connect_ex(("127.0.0.1", port))
            s.close()
            report["checks"][f"port_{name}"] = {
                "port": port,
                "status": "OPEN" if r == 0 else "CLOSED"
            }
        except Exception:
            report["checks"][f"port_{name}"] = {"port": port, "status": "ERROR"}

    # 7. Daemons
    import os
    appdata = os.environ.get('APPDATA', '')
    for daemon in ['schedule_daemon.py', 'trigger_daemon.py']:
        path = os.path.join(os.environ.get('SEVEN_APP_PATH', ''), daemon)
        report["checks"][daemon] = {
            "exists": os.path.exists(path),
            "path": path
        }

    # 8. Disk
    try:
        import shutil
        total, used, free = shutil.disk_usage(appdata or 'C:\\')
        report["checks"]["disk"] = {
            "status": "OK" if free > 500 * 1024 * 1024 else "LOW",
            "free_gb": round(free / (1024**3), 2),
            "total_gb": round(total / (1024**3), 2)
        }
    except Exception as e:
        report["checks"]["disk"] = {"status": "ERROR", "error": str(e)}

    # 9. VC++ Runtime
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.CDLL("msvcp140.dll")
            report["checks"]["vcredist"] = {"status": "INSTALLED"}
        except OSError:
            report["checks"]["vcredist"] = {"status": "MISSING"}

    # Overall health
    broken = [k for k, v in report["checks"].items() if v.get("status") in ("BROKEN", "MISSING", "OFFLINE", "ERROR")]
    report["overall"] = "HEALTHY" if not broken else f"ISSUES: {', '.join(broken)}"

    return report