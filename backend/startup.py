"""
=============================================================================
PROJECT SEVEN - backend/startup.py
Minimal startup server for pre-setup state

PURPOSE:
    When packages are not yet installed (fresh install),
    main.py cannot import ears/brain/etc.
    This minimal FastAPI server starts INSTEAD, serves just enough
    for the setup wizard to run bootstrap.py and install packages.
    
    After packages are installed and Ollama is ready,
    the wizard calls /api/bootstrap/restart which restarts
    the full main.py process.

ENDPOINTS SERVED IN PRE-SETUP MODE:
    GET  /api/status              ← so Electron knows backend is alive
    GET  /api/config              ← so wizard reads setup_complete
    GET  /api/bootstrap/check     ← check what is installed
    POST /api/bootstrap/start     ← install packages + Ollama
    GET  /api/bootstrap/status    ← live progress
    POST /api/bootstrap/pull-model ← pull LLM model
    POST /api/setup/complete      ← save wizard data
    POST /api/bootstrap/restart   ← restart as full server
=============================================================================
"""

import sys
import os
import json
import threading
import time
import subprocess

# ── Minimal deps only — these are always available ──
# fastapi and uvicorn are installed by bootstrap FIRST
# so we need to handle the case where even they are missing

def run_minimal_server(host="127.0.0.1", port=7777):
    """
    Try to start a minimal FastAPI server.
    If FastAPI is not installed yet, use raw http.server instead.
    """
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
        _start_fastapi_server(host, port)
    except ImportError:
        print("[STARTUP] FastAPI not installed — using raw HTTP server")
        _start_raw_server(host, port)


def _start_fastapi_server(host, port):
    """Full minimal FastAPI server for pre-setup mode."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn

    from backend.bootstrap import (
        get_state, run_environment_setup, run_model_pull,
        check_packages_installed, is_ollama_installed, is_ollama_running
    )

    app = FastAPI(title="Seven Startup API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/status")
    def status():
        return {
            "listening": False, "speaking": False, "thinking": False,
            "mode": "pre-setup", "version": _get_version()
        }

    @app.get("/api/config")
    def get_config():
        return _load_config()

    @app.get("/api/bootstrap/check")
    def bootstrap_check():
        return {
            "packages_installed": check_packages_installed(),
            "ollama_installed":   is_ollama_installed(),
            "ollama_running":     is_ollama_running(),
            "needs_setup":        True
        }

    @app.post("/api/bootstrap/start")
    def bootstrap_start():
        run_environment_setup()
        return {"success": True}

    @app.get("/api/bootstrap/status")
    def bootstrap_status():
        return get_state()

    @app.post("/api/bootstrap/pull-model")
    def pull_model(data: dict):
        model = data.get("model", "").strip()
        if not model:
            return {"error": "model required"}
        run_model_pull(model)
        return {"success": True, "model": model}

    @app.post("/api/setup/voices")
    def get_voices():
        return {"voices": [], "count": 0}

    @app.get("/api/setup/voices")
    def get_voices_get():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            result = []
            for i, v in enumerate(voices or []):
                raw = v.name or f"Voice {i}"
                clean = raw.replace("Microsoft ", "").split(" Desktop")[0].split(" -")[0].strip()
                result.append({"index": i, "name": clean, "full_name": raw,
                               "gender": "Female" if any(n in clean.lower()
                               for n in ["zira","hazel","aria","jenny"]) else "Male",
                               "language": "English"})
            engine.stop()
            return {"voices": result, "count": len(result)}
        except Exception as e:
            return {"voices": [], "count": 0, "error": str(e)}

    @app.post("/api/setup/preview-voice")
    def preview_voice(data: dict):
        def _speak():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                voices = engine.getProperty('voices')
                idx = data.get("voice_index", 0)
                if voices and idx < len(voices):
                    engine.setProperty('voice', voices[idx].id)
                engine.setProperty('rate', 185)
                engine.say("Hello. I am Seven. Your private AI assistant.")
                engine.runAndWait()
            except Exception:
                pass
        threading.Thread(target=_speak, daemon=True).start()
        return {"success": True}

    @app.post("/api/setup/complete")
    def setup_complete(data: dict):
        try:
            cfg = _load_config()
            cfg["setup_complete"] = True
            cfg["email"] = data.get("email", "")
            if "identity" not in cfg:
                cfg["identity"] = {}
            cfg["identity"]["user_name"] = data.get("name", "")
            wake = data.get("wake_word", "seven").lower().strip()
            cfg["identity"]["wake_words"] = [wake, f"hey {wake}"]
            if "voice" not in cfg:
                cfg["voice"] = {}
            cfg["voice"]["voice_index"] = data.get("voice_index", 0)
            if data.get("model_name"):
                if "brain" not in cfg:
                    cfg["brain"] = {}
                cfg["brain"]["model_name"] = data["model_name"]
            _save_config(cfg)

            # Save email
            try:
                data_dir = _get_data_dir()
                with open(os.path.join(data_dir, "email.txt"), "w") as f:
                    f.write(data.get("email", ""))
            except Exception:
                pass

            return {"success": True, "message": f"Welcome to Seven, {data.get('name', '')}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @app.get("/api/hardware")
    def get_hardware():
        try:
            import brain_manager
            hw  = brain_manager.get_hardware_summary()
            rec, tier, reason = brain_manager.recommend_model(hw)
            installed = brain_manager.get_installed_models()
            return {"gpu": hw["gpu"], "ram_gb": hw["ram_gb"], "cpu": hw["cpu"],
                    "os": hw["os"], "recommended_model": rec,
                    "recommended_tier": tier, "recommendation_reason": reason,
                    "installed_models": installed}
        except Exception as e:
            return {"gpu": {"available": False}, "ram_gb": 8, "cpu": {},
                    "os": "Windows", "recommended_model": "tinyllama",
                    "recommended_tier": "minimum", "recommendation_reason": str(e),
                    "installed_models": []}

    @app.post("/api/bootstrap/restart")
    def restart_full():
        """
        Called after setup is complete.
        Signals the process to restart with full main.py.
        Electron will detect the backend went down and restart Python.
        """
        def _restart():
            time.sleep(1)
            os._exit(0)  # Force exit — Electron restarts Python
        threading.Thread(target=_restart, daemon=True).start()
        return {"success": True, "message": "Restarting..."}

    # WebSocket stub
    from fastapi import WebSocket
    import asyncio

    @app.websocket("/ws/status")
    async def ws_status(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(
                    {"listening": False, "thinking": False, "speaking": False}
                )
                await asyncio.sleep(0.5)
        except Exception:
            pass

    def _run():
        uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)

    t = threading.Thread(target=_run, daemon=True, name="SevenStartupAPI")
    t.start()
    print(f"[STARTUP] Minimal API server running on http://{host}:{port}")
    return t


def _start_raw_server(host, port):
    """
    Ultra-minimal HTTP server using only stdlib.
    Used when even FastAPI/uvicorn are not installed.
    Returns minimal JSON for /api/status so Electron knows backend is alive.
    """
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/status":
                body = json.dumps({
                    "listening": False, "speaking": False, "thinking": False,
                    "mode": "minimal", "version": "1.1.0"
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"success": true}')

        def log_message(self, *args):
            pass  # Suppress request logs

    def _run():
        with socketserver.TCPServer((host, port), Handler) as httpd:
            print(f"[STARTUP] Raw HTTP server on http://{host}:{port}")
            httpd.serve_forever()

    t = threading.Thread(target=_run, daemon=True, name="SevenRawServer")
    t.start()


# ── Helpers ──

def _get_appdata_dir():
    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
    d = os.path.join(app_data, 'SEVEN')
    os.makedirs(d, exist_ok=True)
    return d

def _get_data_dir():
    d = os.path.join(_get_appdata_dir(), 'data')
    os.makedirs(d, exist_ok=True)
    return d

def _get_config_path():
    return os.path.join(_get_appdata_dir(), 'config.json')

def _load_config():
    p = _get_config_path()
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            pass
    return {"setup_complete": False, "version": "1.1.0"}

def _save_config(cfg):
    with open(_get_config_path(), 'w') as f:
        json.dump(cfg, f, indent=4)

def _get_version():
    try:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pkg  = os.path.join(here, '..', '..', '..', '..', 'package.json')
        if os.path.exists(pkg):
            with open(pkg) as f:
                return json.load(f).get("version", "1.1.0")
    except Exception:
        pass
    return "1.1.0"