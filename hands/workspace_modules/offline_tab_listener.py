"""
hands/workspace_modules/offline_tab_listener.py
Lightweight HTTP listener on port 7777 when Seven main backend is offline.
Receives live tab snapshots from the Seven Chrome Extension for ALL profiles.
"""
import sys
import os
import json
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

CACHE_DIR = os.path.join(os.environ.get("APPDATA", ""), "SEVEN", "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "live_chrome_tabs.json")

_tab_snapshots = {}


def get_cache_file_path() -> str:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception:
        pass
    return CACHE_FILE


def save_snapshots_to_disk():
    global _tab_snapshots
    try:
        fpath = get_cache_file_path()
        all_tabs = []
        profiles_map = {}
        for prof_name, t_list in _tab_snapshots.items():
            profiles_map[prof_name] = t_list
            all_tabs.extend(t_list)

        payload = {
            "available": bool(all_tabs),
            "profiles":  profiles_map,
            "tabs":      all_tabs,
            "count":     len(all_tabs),
            "timestamp": datetime.now().isoformat(),
        }
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def load_snapshots_from_disk():
    global _tab_snapshots
    try:
        fpath = get_cache_file_path()
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "profiles" in data and isinstance(data["profiles"], dict):
                        _tab_snapshots.update(data["profiles"])
                    elif "tabs" in data and isinstance(data["tabs"], list):
                        for t in data["tabs"]:
                            prof = t.get("profile") or "default"
                            if prof not in _tab_snapshots:
                                _tab_snapshots[prof] = []
                            _tab_snapshots[prof].append(t)
    except Exception:
        pass


def extract_tabs_from_payload(data: dict) -> list:
    tabs_list = []
    profile = (data.get("profile") or "default").strip()
    
    windows = data.get("windows") or []
    if windows:
        for win in windows:
            incognito = win.get("incognito", False)
            for t in win.get("tabs", []):
                url = (t.get("url") or "").strip()
                if not url or url.startswith(("chrome://", "edge://", "chrome-extension://", "brave://", "about:")):
                    continue
                tabs_list.append({
                    "url":       url,
                    "title":     t.get("title", ""),
                    "pinned":    t.get("pinned", False),
                    "active":    t.get("active", False),
                    "incognito": incognito,
                    "profile":   profile,
                })
        return tabs_list

    for t in data.get("tabs", []):
        url = (t.get("url") or "").strip()
        if not url or url.startswith(("chrome://", "edge://", "chrome-extension://", "brave://", "about:")):
            continue
        tabs_list.append({
            "url":       url,
            "title":     t.get("title", ""),
            "pinned":    t.get("pinned", False),
            "active":    t.get("active", False),
            "incognito": t.get("incognito", False),
            "profile":   profile,
        })
    return tabs_list


class TabHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/api/chrome/tabs"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length > 0 else b"{}"
                data = json.loads(body.decode("utf-8"))

                profile = (data.get("profile") or "default").strip()
                parsed_tabs = extract_tabs_from_payload(data)

                _tab_snapshots[profile] = parsed_tabs
                save_snapshots_to_disk()

                resp = json.dumps({
                    "status": "ok",
                    "profile": profile,
                    "tabs_received": len(parsed_tabs),
                    "total_profiles": len(_tab_snapshots),
                }).encode("utf-8")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/chrome/tabs"):
            all_tabs = []
            profiles_map = {}
            for prof_name, t_list in _tab_snapshots.items():
                profiles_map[prof_name] = t_list
                all_tabs.extend(t_list)

            data = {
                "available": bool(all_tabs),
                "profiles":  profiles_map,
                "tabs":      all_tabs,
                "total":     len(all_tabs),
                "timestamp": datetime.now().isoformat(),
            }
            resp = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        elif self.path in ("/api/status", "/status", "/health", "/api/health"):
            resp = b'{"status":"ready","mode":"offline_tab_listener"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port=7777):
    load_snapshots_from_disk()

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    try:
        httpd = ReusableHTTPServer(("127.0.0.1", port), TabHTTPHandler)
        httpd.serve_forever()
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    run_server()