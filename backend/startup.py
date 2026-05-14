"""
=============================================================================
PROJECT SEVEN - backend/startup.py
Minimal startup server for pre-setup state
=============================================================================
"""

import sys
import os
import json
import threading
import time

def run_minimal_server(host="127.0.0.1", port=7777):
    """Start minimal FastAPI server or fall back to raw HTTP."""
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

    app = FastAPI(
        title="Seven Startup API",
        docs_url="/api/docs",
        redoc_url=None
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Root ──
    @app.get("/")
    def root():
        return {
            "name": "Seven Startup API",
            "mode": "pre-setup",
            "status": "running",
            "docs": "http://127.0.0.1:7777/api/docs"
        }

    # ── Status ──
    @app.get("/api/status")
    def status():
        return {
            "listening": False,
            "speaking": False,
            "thinking": False,
            "mode": "pre-setup",
            "version": _get_version()
        }

    # ── Config — always force setup wizard ──
    @app.get("/api/config")
    def get_config():
        cfg = _load_config()
        cfg["setup_complete"] = False
        cfg["pre_setup_mode"] = True
        return cfg

    # ── License stub ──
    @app.get("/api/license/status")
    def license_status():
        return {
            "tier": "free",
            "valid": True,
            "expires_at": None,
            "days_until_expiry": None,
            "offline_mode": False,
            "offline_days": 0,
            "features": {},
            "license_key": "",
            "is_trial": False,
            "device_id": "unknown"
        }

    # ── Usage stubs ──
    @app.get("/api/usage/stats")
    def usage_stats():
        return {
            "total_hours": 0,
            "total_minutes": 0,
            "display": "0 min",
            "email": None,
            "device_id": None,
            "last_seen": None
        }

    @app.get("/api/usage/history")
    def usage_history():
        return {"history": [], "total_hours": 0}

    # ── Update stubs ──
    @app.get("/api/update/status")
    def update_status():
        return {
            "update_available": False,
            "checking": False,
            "downloading": False,
            "download_progress": 0,
            "download_path": None,
            "error": None,
            "info": None,
            "current_version": _get_version()
        }

    @app.post("/api/update/check")
    def update_check():
        return {"success": True, "message": "Update check skipped in pre-setup mode"}

    @app.post("/api/update/download")
    def update_download():
        return {"success": False, "message": "Updates disabled in pre-setup mode"}

    @app.post("/api/update/install")
    def update_install():
        return {"success": False, "message": "No installer in pre-setup mode"}

    # ── Hardware ──
    @app.get("/api/hardware")
    def get_hardware():
        try:
            import brain_manager
            hw = brain_manager.get_hardware_summary()
            rec, tier, reason = brain_manager.recommend_model(hw)
            installed = brain_manager.get_installed_models()
            return {
                "gpu": hw["gpu"], "ram_gb": hw["ram_gb"],
                "cpu": hw["cpu"], "os": hw["os"],
                "recommended_model": rec,
                "recommended_tier": tier,
                "recommendation_reason": reason,
                "installed_models": installed
            }
        except Exception as e:
            return {
                "gpu": {"available": False}, "ram_gb": 8,
                "cpu": {}, "os": "Windows",
                "recommended_model": "tinyllama",
                "recommended_tier": "minimum",
                "recommendation_reason": str(e),
                "installed_models": []
            }

    # ── Voice stubs ──
    @app.get("/api/setup/voices")
    def get_voices():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            result = []
            for i, v in enumerate(voices or []):
                raw   = v.name or f"Voice {i}"
                clean = raw.replace("Microsoft ", "").split(" Desktop")[0].split(" -")[0].strip()
                result.append({
                    "index": i, "name": clean, "full_name": raw,
                    "gender": "Female" if any(
                        n in clean.lower()
                        for n in ["zira", "hazel", "aria", "jenny"]
                    ) else "Male",
                    "language": "English"
                })
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

    # ── Setup complete ──
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

            try:
                data_dir = _get_data_dir()
                with open(os.path.join(data_dir, "email.txt"), "w") as f:
                    f.write(data.get("email", ""))
            except Exception:
                pass

            return {"success": True, "message": f"Welcome to Seven, {data.get('name', '')}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Bootstrap endpoints ──
    @app.get("/api/bootstrap/check")
    def bootstrap_check():
        from backend.bootstrap import (
            check_packages_installed, is_ollama_installed, is_ollama_running
        )
        return {
            "packages_installed": check_packages_installed(),
            "ollama_installed":   is_ollama_installed(),
            "ollama_running":     is_ollama_running(),
            "needs_setup":        True
        }

    @app.post("/api/bootstrap/start")
    def bootstrap_start():
        from backend.bootstrap import run_environment_setup
        run_environment_setup()
        return {"success": True}

    @app.get("/api/bootstrap/status")
    def bootstrap_status():
        from backend.bootstrap import get_state
        return get_state()

    @app.post("/api/bootstrap/pull-model")
    def pull_model(data: dict):
        from backend.bootstrap import run_model_pull
        model = data.get("model", "").strip()
        if not model:
            return {"error": "model required"}
        run_model_pull(model)
        return {"success": True, "model": model}

    @app.post("/api/bootstrap/start-ollama")
    def start_ollama_endpoint():
        from backend.bootstrap import start_ollama as _start_ollama
        threading.Thread(target=_start_ollama, daemon=True).start()
        return {"success": True, "message": "Starting Ollama"}

    # ── WebSocket stub (GET fallback) ──
    @app.get("/ws/status")
    def ws_status_stub():
        return {"listening": False, "thinking": False, "speaking": False}

    # ── RESTART — must be last, inside this function ──
    @app.post("/api/bootstrap/restart")
    def restart_full():
        """Exit cleanly — Electron restarts Python in full mode."""
        def _do_restart():
            time.sleep(1)
            print("[STARTUP] Bootstrap complete. Restarting in full mode...")
            sys.stdout.flush()
            os._exit(0)
        threading.Thread(target=_do_restart, daemon=True).start()
        return {"success": True, "message": "Restarting..."}

    # ── Run server ──
    def _run():
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )

    t = threading.Thread(target=_run, daemon=True, name="SevenStartupAPI")
    t.start()
    print(f"[STARTUP] Minimal API server running on http://{host}:{port}")
    return t


def _start_raw_server(host, port):
    """Ultra-minimal stdlib HTTP server when FastAPI not installed."""
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/status":
                body = json.dumps({
                    "listening": False, "speaking": False,
                    "thinking": False, "mode": "minimal",
                    "version": "1.1.0"
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/config":
                body = json.dumps({
                    "setup_complete": False,
                    "pre_setup_mode": True
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
            pass

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
        pkg  = os.path.join(here, 'package.json')
        if os.path.exists(pkg):
            with open(pkg) as f:
                return json.load(f).get("version", "1.1.0")
    except Exception:
        pass
    return "1.1.0"