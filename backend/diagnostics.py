"""
backend/diagnostics.py
A health report for one PC: what Seven sees, what works, what does not and why, in plain text a person can paste to us.

    GET  /api/diagnostics/report      the report as text (open it in a browser, copy it, send it)
    GET  /api/diagnostics             the same as data
    python backend/diagnostics.py     works when Seven's backend is not running at all (Start menu: Seven Diagnostics)

Every check is isolated: one that fails or hangs becomes a line in the report, never an error that hides the rest. Nothing
personal is collected: no name, email, files or conversations, and the Windows user name is replaced. The slow checks
(importing the native libraries in a child process, reaching the internet) run in parallel under a time limit.
"""
import concurrent.futures
import datetime
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
_DATA = os.path.join(_APPDATA, "SEVEN")
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _c(name, status, detail=""):
    return {"name": name, "status": status, "detail": str(detail)}


def _guard(fn):
    """Run one section; whatever goes wrong becomes a line in the report."""
    try:
        return fn()
    except Exception as exc:                                  # a check must never take the report down
        return [_c("this check", WARN, f"could not run ({type(exc).__name__}: {str(exc)[:120]})")]


def _state() -> dict:
    try:
        from backend.api_server import _state
        return _state
    except Exception:
        return {}


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _tail(path, lines=25, skip="") -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 60000))
            kept = [ln for ln in f.read().decode("utf-8", "replace").splitlines() if not (skip and skip in ln)]
            return "\n".join(kept[-lines:])
    except OSError:
        return ""


# ------------------------------------------------------------------------------------------------ sections
def app_section():
    from seven_utils.version import get_version
    packaged = os.path.exists(os.path.join(_ROOT, "python", "python311.dll")) or "resources" in _ROOT.lower()
    out = [_c("Seven version", INFO, get_version()),
           _c("Installed as", INFO, "packaged app" if packaged else "development checkout"),
           _c("Windows", INFO, f"{platform.platform()} ({platform.machine()})"),
           _c("Python", INFO, f"{platform.python_version()} at {sys.executable}")]
    try:
        import psutil
        vm = psutil.virtual_memory()
        out.append(_c("Memory", OK if vm.available > 1.5 * 1024 ** 3 else WARN,
                      f"{vm.total / 1024 ** 3:.1f} GB total, {vm.available / 1024 ** 3:.1f} GB free"
                      + ("" if vm.available > 1.5 * 1024 ** 3 else ". Low: Seven and its AI model need room")))
        out.append(_c("Processor", INFO, f"{platform.processor() or 'unknown'}, {psutil.cpu_count(logical=False) or '?'} cores"
                                         f" ({psutil.cpu_count()} threads), now {psutil.cpu_percent(interval=0.3):.0f}% busy"))
        free = shutil.disk_usage(_APPDATA).free / 1024 ** 3
        out.append(_c("Free disk space", OK if free > 5 else WARN if free > 1 else FAIL, f"{free:.1f} GB on the drive Seven stores data on"))
    except Exception as exc:
        out.append(_c("Memory and disk", WARN, f"unreadable ({type(exc).__name__})"))
    try:
        from backend.api_server import _start_time
        out.append(_c("Backend running for", INFO, f"{int(time.time() - _start_time)} s"))
    except Exception:
        out.append(_c("Backend", WARN, "not running in this process (this report was made without it)"))
    return out


def state_section():
    st = _state()
    if not st:
        return [_c("Live state", INFO, "unavailable: the backend is not running")]
    out = [_c("Ready", OK if st.get("ready") else WARN, f"{st.get('ready')} (stage: {st.get('ready_stage') or '-'})"),
           _c("Listening", OK if st.get("listening") else FAIL, str(st.get("listening"))),
           _c("Status line", INFO, st.get("status_text") or "-")]
    if st.get("voice_problem"):
        out.append(_c("Hearing problem", FAIL, st["voice_problem"]))
    if st.get("safe_mode"):
        out.append(_c("Safe mode", FAIL, (st["safe_mode"] or {}).get("reason") or "on"))
    sm = st.get("speech_model") or {}
    if sm:
        out.append(_c("Speech model state", OK if sm.get("state") == "ready" else WARN if sm.get("state") != "error" else FAIL,
                      f"{sm.get('state')} {sm.get('progress', '')}% {sm.get('detail') or ''}".strip()))
    return out


def safe_mode_section():
    from main_modules.startup import safe_mode
    from seven_utils.version import get_version
    data = safe_mode.state(os.path.join(_DATA, "safe_mode.flag"), get_version())
    if not data:
        return [_c("Safe mode record", OK, "no failed starts recorded")]
    fails = int(data.get("fails", 0) or 0)
    return [_c("Safe mode record", FAIL if fails >= safe_mode.MAX_FAILS else WARN,
               f"{fails} failed start(s) in a row. Reason: {data.get('reason') or 'unknown'}")]


def microphone_section():
    out = []
    try:
        import winreg
        for label, sub in (("Windows microphone access", r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"),
                           ("Desktop apps may use the microphone", r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged")):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as key:
                    value = winreg.QueryValueEx(key, "Value")[0]
                out.append(_c(label, OK if value == "Allow" else FAIL,
                              f"{value}" + ("" if value == "Allow" else ". Windows blocks the microphone: Settings, Privacy and security, Microphone")))
            except OSError:
                out.append(_c(label, INFO, "not set (Windows default)"))
    except ImportError:
        pass
    try:
        from seven_utils import audio
        pa = audio.pa()
        names = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                names.append(info.get("name", "?"))
        default = pa.get_default_input_device_info().get("name", "?") if names else "none"
        out.append(_c("Microphones found", OK if names else FAIL, f"{len(names)}; default: {default}" if names else "none: plug one in or enable it in Windows sound settings"))
    except Exception as exc:
        out.append(_c("Microphones found", FAIL, f"could not list audio devices ({type(exc).__name__}: {str(exc)[:100]})"))
    stream = getattr(sys.modules.get("ears.stream"), "STREAM", None)
    if stream is not None:
        out.append(_c("Microphone stream", OK if not stream.last_error else FAIL,
                      "open" if not stream.last_error else f"error: {stream.last_error[:140]}"))
    return out


def speech_section():
    ears = sys.modules.get("ears.core")
    if ears is None:
        return [_c("Hearing (ears.core)", FAIL, "not loaded: Seven has not started its ears, see the safe mode and log lines")]
    out = [_c("Hearing (ears.core)", OK, "loaded"),
           _c("Listening", OK if ears.listening() else FAIL, str(ears.listening()))]
    try:
        for name in ears._needed_models():
            out.append(_c(f"Speech model {name}", OK if ears.model_cached(name) else FAIL, "on this PC" if ears.model_cached(name) else "not downloaded"))
        out.append(_c("Speech recognition on", INFO, "graphics card" if ears._gpu_available() else "processor (no usable GPU)"))
    except Exception as exc:
        out.append(_c("Speech models", WARN, f"unreadable ({type(exc).__name__})"))
    return out


def voice_section():
    from mouth import voices
    ready = voices.kokoro_ready()
    out = [_c("Natural voice", OK if ready else WARN, "installed" if ready else "not installed: Seven answers in a basic voice")]
    try:
        from backend.bootstrap import _bootstrap_state
        out.append(_c("Voice download", INFO, json.dumps(_bootstrap_state.get("voice_model", {}))[:160]))
    except Exception:
        pass
    return out


def ai_section():
    out = []
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            up = True
    except OSError:
        up = False
    out.append(_c("AI model engine (Ollama)", OK if up else WARN, "running" if up else "not running: only instant commands work"))
    if up:
        try:
            import requests
            tags = requests.get("http://127.0.0.1:11434/api/tags", timeout=2).json().get("models", [])
            out.append(_c("Models installed", OK if tags else WARN, ", ".join(m.get("name", "?") for m in tags[:6]) or "none"))
        except Exception as exc:
            out.append(_c("Models installed", WARN, f"could not ask ({type(exc).__name__})"))
    return out


_CHILD = r"""
import json, importlib
out = {}
for name in ("numpy", "pyaudio", "onnxruntime", "ctranslate2", "faster_whisper"):
    try:
        mod = importlib.import_module(name)
        out[name] = "ok " + str(getattr(mod, "__version__", ""))
    except BaseException as e:
        out[name] = "FAILED " + type(e).__name__ + ": " + str(e)[:140]
try:
    import ctranslate2
    out["ctranslate2 compute"] = ",".join(sorted(ctranslate2.get_supported_compute_types("cpu")))
except BaseException as e:
    out["ctranslate2 compute"] = "FAILED " + type(e).__name__
print(json.dumps(out))
"""


def libraries_section():
    """Import the native libraries in a child process: a library that crashes the process shows up here instead of killing Seven."""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
    try:
        run = subprocess.run([sys.executable, "-c", _CHILD], capture_output=True, text=True, timeout=45, env=env,
                             creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return [_c("Native libraries", FAIL, "importing them took over 45 seconds")]
    if run.returncode != 0 or not run.stdout.strip():
        return [_c("Native libraries", FAIL, f"the test process crashed (exit {run.returncode}): {run.stderr.strip()[-160:] or 'no message'}. "
                                             "A library does not run on this PC (often an old processor or a missing Visual C++ runtime)")]
    out = []
    for name, result in json.loads(run.stdout.strip().splitlines()[-1]).items():
        out.append(_c(name, OK if not result.startswith("FAILED") else FAIL, result))
    return out


def _reach(name, url, slow=3.0):
    start = time.time()
    try:
        import requests
        r = requests.get(url, timeout=70, headers={"User-Agent": "Seven diagnostics"})
        took = time.time() - start
        status = OK if r.status_code < 400 and took < slow else WARN
        return _c(name, status, f"HTTP {r.status_code} in {took:.1f} s" + ("" if took < slow else " (slow: a sleeping server wakes up on the first request)"))
    except Exception as exc:
        return _c(name, FAIL, f"unreachable ({type(exc).__name__}) after {time.time() - start:.0f} s")


def network_section():
    import server_sync
    checks = {"Seven server": f"{server_sync.SERVER_URL}/ping", "Hugging Face (speech models)": "https://huggingface.co/",
              "GitHub (update fallback)": "https://api.github.com/"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        out = list(pool.map(lambda kv: _reach(*kv), checks.items()))
    try:
        import telemetry
        reg = telemetry.registration_status()
        out.append(_c("Registered with the server", OK if reg["registered"] else WARN,
                      "yes" if reg["registered"] else f"not yet: {reg['last_error'] or 'waiting for setup or the server'}"))
    except Exception:
        pass
    return out


def data_section():
    out = []
    probe = os.path.join(_DATA, ".write_test")
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        out.append(_c("Data folder", OK, f"{_DATA} is writable"))
    except OSError as exc:
        out.append(_c("Data folder", FAIL, f"{_DATA} is not writable ({exc})"))
    cfg = _read_json(os.path.join(_DATA, "config.json"))
    out.append(_c("Settings file", OK if cfg is not None else FAIL, "readable" if cfg is not None else "missing or damaged"))
    if cfg:
        out.append(_c("Setup finished", OK if cfg.get("setup_complete") else WARN, str(bool(cfg.get("setup_complete")))))
        out.append(_c("Listening mode / sensitivity", INFO, f"{cfg.get('voice', {}).get('listen_mode', 'wake')} / {cfg.get('voice', {}).get('sensitivity', 'balanced')}"))
    return out


def processes_section():
    out = []
    try:
        import psutil
        rows = []
        for p in psutil.process_iter(["name", "memory_info", "cpu_percent"]):
            name = (p.info["name"] or "").lower()
            if name in ("seven.exe", "ollama.exe", "ollama app.exe", "pythonw.exe", "python.exe"):
                rows.append((name, (p.info["memory_info"].rss if p.info["memory_info"] else 0) / 1024 ** 2))
        summary = {}
        for name, mb in rows:
            n, total = summary.get(name, (0, 0))
            summary[name] = (n + 1, total + mb)
        out.append(_c("Seven-related processes", INFO, "; ".join(f"{n} x {k} ({v:.0f} MB)" for k, (n, v) in sorted(summary.items())) or "none"))
    except Exception as exc:
        out.append(_c("Processes", WARN, f"unreadable ({type(exc).__name__})"))
    return out


def logs_section():
    out = []
    for label, name, lines in (("Seven log (last lines)", "seven.log", 30), ("Native crash log (last lines)", "native_crash.log", 20),
                               ("Backend errors (last lines)", "python_crash.log", 20)):
        text = _tail(os.path.join(_DATA, "logs", name), lines, skip="[DEBUG")
        out.append(_c(label, INFO if text else OK, text or "empty"))
    return out


SECTIONS = [("Seven", app_section), ("Live state", state_section), ("Safe mode", safe_mode_section),
            ("Microphone", microphone_section), ("Speech recognition", speech_section), ("Voice", voice_section),
            ("AI model", ai_section), ("Native libraries", libraries_section), ("Network and server", network_section),
            ("Data", data_section), ("Processes", processes_section), ("Logs", logs_section)]
SLOW = {"Native libraries", "Network and server"}


def collect() -> dict:
    """Run every section (the slow ones in parallel) and return {at, sections: [{title, checks}], problems, warnings}."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(SLOW))) as pool:
        futures = {title: pool.submit(_guard, fn) for title, fn in SECTIONS if title in SLOW}
        for title, fn in SECTIONS:
            if title not in SLOW:
                results[title] = _guard(fn)
        for title, fut in futures.items():
            results[title] = fut.result()
    sections = [{"title": title, "checks": results[title]} for title, _ in SECTIONS]
    flat = [c for s in sections for c in s["checks"]]
    return {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "sections": sections,
            "problems": sum(c["status"] == FAIL for c in flat), "warnings": sum(c["status"] == WARN for c in flat)}


_MARK = {OK: "OK  ", WARN: "WARN", FAIL: "FAIL", INFO: "    "}


def render(report: dict) -> str:
    """The report as text. The Windows user name is replaced, so it can be pasted anywhere."""
    lines = [f"SEVEN DIAGNOSTICS   {report['at']}",
             f"{report['problems']} problem(s), {report['warnings']} warning(s)", ""]
    worst = [(s["title"], c) for s in report["sections"] for c in s["checks"] if c["status"] in (FAIL, WARN)]
    if worst:
        lines.append("READ THESE FIRST")
        lines += [f"  [{_MARK[c['status']]}] {title}: {c['name']}: {c['detail']}" for title, c in sorted(worst, key=lambda x: x[1]["status"] != FAIL)]
        lines.append("")
    for s in report["sections"]:
        lines.append(f"== {s['title']} ==")
        for c in s["checks"]:
            detail = c["detail"]
            if "\n" in detail:
                lines.append(f"  [{_MARK[c['status']]}] {c['name']}:")
                lines += [f"        {ln}" for ln in detail.splitlines()]
            else:
                lines.append(f"  [{_MARK[c['status']]}] {c['name']}: {detail}")
        lines.append("")
    text = "\n".join(lines)
    user = os.environ.get("USERNAME") or os.path.basename(os.path.expanduser("~"))
    return re.sub(re.escape(user), "<user>", text, flags=re.IGNORECASE) if user else text


def report_text() -> str:
    return render(collect())


if __name__ == "__main__":
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    text = report_text()
    print(text)
    if "--open" in sys.argv or "--save" in sys.argv:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        path = os.path.join(desktop if os.path.isdir(desktop) else _DATA, "Seven-Diagnostics.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            subprocess.run(["clip"], input=text.encode("utf-16"), timeout=5, creationflags=_NO_WINDOW)   # also on the clipboard: paste it
        except Exception:
            pass
        print(f"\nSaved to {path} and copied to the clipboard.")
        if "--open" in sys.argv and hasattr(os, "startfile"):
            os.startfile(path)
