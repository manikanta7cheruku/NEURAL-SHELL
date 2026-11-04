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
    busy = "thinking" if st.get("thinking") else "speaking" if st.get("speaking") else ""
    listening = (_c("Listening", OK, "True") if st.get("listening")
                 else _c("Listening", INFO, f"paused while it is {busy}: normal") if busy
                 else _c("Listening", FAIL, "False"))
    out = [_c("Ready", OK if st.get("ready") else WARN, f"{st.get('ready')} (stage: {st.get('ready_stage') or '-'})"),
           listening,
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


_IGNORE_HINTS = {
    "no wake word": "Seven is in wake-word mode and acts only after you say 'Hey Seven'. Try Always on.",
    "Seven's own voice": "Seven thinks it is hearing itself, so it throws the audio away. Check 'speaking for' above; "
                         "headphones stop it hearing its own voice.",
    "too short": "short sounds only: clicks or background noise, no sustained speech reaches the detector.",
    "no clear speech": "the speech model hears something but finds no words in it: very quiet or very noisy audio.",
    "noise": "the speech model finds no words in what it hears.",
}


def _config_voice() -> dict:
    return (_read_json(os.path.join(_DATA, "config.json")) or {}).get("voice", {}) or {}


def hearing_section():
    """What the ears are doing right now. The question this answers: Seven is 'listening' and the microphone is open, so why
    does it act on nothing? It is hearing silence, hearing noise, hearing speech it then throws away, or waiting for a key."""
    ears = sys.modules.get("ears.core")
    if ears is None or not hasattr(ears, "hearing_stats"):
        return [_c("Hearing right now", INFO, "the ears are not loaded in this process")]
    h = ears.hearing_stats()
    out = []
    mode, live = h["mode"], (_state().get("listen_mode") or "")
    saved = _config_voice().get("listen_mode", "(not set)")
    out.append(_c("Listening mode in effect", OK, f"{mode} (saved setting: {saved}; shown on screen: {live or '?'})"))
    if live and live != mode:
        out.append(_c("Mode on screen", WARN, f"the screen shows '{live}' but the ears use '{mode}': the voice loop has not refreshed it, "
                                              "which means it is busy or stuck"))
    if mode == "ptt":
        listener = h.get("push_to_talk_listener")
        out.append(_c("Push to talk", FAIL if not listener else WARN,
                      "Seven hears you only while Shift is held, and the keyboard listener is NOT running" if not listener
                      else "Seven hears you only while Shift is held. Choose Always on or Wake word to talk without a key"))
    if h["speaking_for_s"] > 120:
        out.append(_c("Seven speaking for", FAIL, f"{h['speaking_for_s']:.0f} s: Seven believes it is talking, so it throws away everything it hears"))
    mic = h["mic_stats"]
    ok_stream = mic["alive"] and mic["since_last_frame"] is not None and mic["since_last_frame"] < 2
    out.append(_c("Microphone frames arriving", OK if ok_stream else FAIL,
                  f"{mic['frames']} so far; last one {mic['since_last_frame']} s ago; device: {mic['device']}" if mic["frames"]
                  else "none yet: the microphone stream has not delivered any audio"))
    peak, avg, best = mic["peak_db"], mic["avg_db"], mic["best_speech_score"]
    if peak is not None:
        level = (FAIL, "SILENT. The microphone delivers no sound: muted, the wrong device, or blocked by Windows") if peak < -60 else \
                (WARN, "very quiet: raise the microphone volume in Windows Sound settings, Input") if peak < -40 else (OK, "good")
        out.append(_c("Microphone level (last 10 s)", level[0], f"peak {peak} dBFS, average {avg} dBFS: {level[1]}"))
        out.append(_c("Voice detector", WARN if peak > -45 and best is not None and best < 0.1 else INFO,
                      f"best speech score {best} (needs {mic['start_threshold']} to start an utterance, sensitivity {mic['sensitivity']})"
                      + (". Sound arrives but the detector finds no speech in it" if peak > -45 and best is not None and best < 0.1 else "")))
    try:
        from ears import doctor
        issues = doctor.assess(h, _state())
        for issue in issues:
            out.append(_c("Problem: " + issue["title"], WARN if issue["level"] != "info" else INFO, f"{issue['detail']}. Do this: {issue['fix']}"))
        if not [i for i in issues if i["level"] != "info"]:
            out.append(_c("Hearing doctor", OK, "no problem found with hearing right now"))
        history = doctor.recent_log(5)
        if history:
            out.append(_c("Hearing problems recorded earlier", INFO, chr(10).join(history)))
    except Exception as exc:
        out.append(_c("Hearing doctor", WARN, f"could not run ({type(exc).__name__})"))
    out.append(_c("Utterances since start", INFO, f"{mic['utterances']} became requests, {mic['too_short']} were too short"))
    outcomes = h["outcomes"]
    total = sum(outcomes.values())
    if total:
        heard = outcomes.get("heard", 0)
        ignored = {k: v for k, v in outcomes.items() if k != "heard"}
        summary = f"{heard} heard; ignored: " + (", ".join(f"{k} x{v}" for k, v in sorted(ignored.items(), key=lambda kv: -kv[1])) or "none")
        out.append(_c(f"Last {total} things it heard", WARN if total >= 5 and heard == 0 else INFO, summary))
        if total >= 5 and heard == 0:
            top = max(ignored, key=ignored.get)
            hint = next((v for k, v in _IGNORE_HINTS.items() if k in top), "")
            if hint:
                out.append(_c("Most likely reason", WARN, f"'{top}': {hint}"))
    else:
        out.append(_c("Last things it heard", INFO, "nothing yet"))
    return out


def voice_loop_section():
    """Is the loop that turns what the ears hear into actions still running? It beats about twice a second; when it stops, the
    ears keep filling a queue nobody empties and Seven looks 'listening' while acting on nothing. The report then shows where
    that thread is stuck."""
    from ears import doctor
    state = _state()
    beat = state.get("voice_loop_beat")
    if not beat:
        return [_c("Voice loop", INFO, "has not started its main loop yet (still loading, or running without the backend)")]
    age = time.time() - float(beat)
    if age < doctor.loop_limit(state):
        return [_c("Voice loop", OK, f"running (last pass {age:.1f} s ago)")]
    import threading
    import traceback
    frame = next((sys._current_frames().get(t.ident) for t in threading.enumerate() if t.name == "VoiceLoop"), None)
    where = "".join(traceback.format_stack(frame)[-6:]) if frame else "the thread is gone: it ended without restarting"
    return [_c("Voice loop", FAIL, f"STUCK: no pass for {age:.0f} s. It is waiting here:" + chr(10) + where.rstrip())]


def voice_section():
    from mouth import voices
    ready = voices.kokoro_ready()
    out = [_c("Natural voice", OK if ready else WARN, "installed" if ready else "not installed: Seven answers in a basic voice")]
    try:
        from backend.bootstrap import _bootstrap_state
        dl = _bootstrap_state.get("voice_model", {})
        if dl.get("status") in ("running", "error"):
            out.append(_c("Voice download", WARN if dl.get("status") == "error" else INFO, json.dumps(dl)[:160]))
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
        summary, overlays, panels = {}, 0, 0
        for p in psutil.process_iter(["name", "memory_info", "cmdline"]):
            name = (p.info["name"] or "").lower()
            if name not in ("seven.exe", "electron.exe", "ollama.exe", "ollama app.exe", "pythonw.exe", "python.exe"):
                continue
            mb = (p.info["memory_info"].rss if p.info["memory_info"] else 0) / 1024 ** 2
            n, total = summary.get(name, (0, 0))
            summary[name] = (n + 1, total + mb)
            cmd = " ".join(p.info["cmdline"] or [])
            if "--type=" not in cmd:
                overlays += "overlay_user_data" in cmd
                panels += "panel_user_data" in cmd
        out.append(_c("Seven-related processes", INFO, "; ".join(f"{n} x {k} ({v:.0f} MB)" for k, (n, v) in sorted(summary.items())) or "none"))
        out.append(_c("Overlay helpers", OK if overlays <= 1 else WARN,
                      f"{overlays} running" + ("" if overlays <= 1 else " (should be 1: quit Seven fully, then start it again)")))
        out.append(_c("Panel hosts", OK if panels <= 1 else WARN, f"{panels} running"))
    except Exception as exc:
        out.append(_c("Processes", WARN, f"unreadable ({type(exc).__name__})"))
    return out


# Log lines that are expected on every healthy PC and would only distract.
_NOISE = ("phonemizer", "unauthenticated requests to the HF Hub", "screen_brightness_control", "filelock", "response_latency",
          "background worker started", "warmed")
_LEVEL = re.compile(r"\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*\]")
_STAMP = re.compile(r"^\[?(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})")
KEEP_DAYS = 7
_EXIT_CODES = {3221225477: "0xC0000005: a native library crashed (access violation)", 3221225786: "0xC000013A: closed with Ctrl+C",
               1073807364: "0x40010004: the process was ended from outside (Quit, Task Manager or an installer)",
               3221226505: "0xC0000409: a native library crashed (stack buffer overrun)"}


def _recent(stamp_line, now=None):
    m = _STAMP.match(stamp_line)
    if not m:
        return True
    try:
        when = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return (now or datetime.datetime.now()) - when <= datetime.timedelta(days=KEEP_DAYS)


def _useful(path, lines, now=None):
    """The warnings and errors of the last week from a log, with their continuation lines, repeats folded into one line with a
    count, and benign noise left out. A multi-line INFO message (a DNS dump, say) is not a warning: its lines have no level of
    their own and belong to the entry above them."""
    entries = []                                  # [key, text, count]
    keep = False
    for ln in _tail(path, 1500, skip="[DEBUG").splitlines():
        if not ln.strip():
            continue
        level = _LEVEL.search(ln)
        if level or _STAMP.match(ln):
            keep = bool(level) and level.group(1) in ("WARNING", "ERROR", "CRITICAL") and not any(n in ln for n in _NOISE) and _recent(ln, now)
            if keep:
                key = ln.split("]", 2)[-1].strip()[:140]
                if entries and entries[-1][0] == key:
                    entries[-1][2] += 1
                else:
                    entries.append([key, ln, 1])
        elif keep and entries:
            entries[-1][1] += "\n" + ln          # a traceback or other continuation of the entry above
    return "\n".join(text + (f"  (x{n})" if n > 1 else "") for _, text, n in entries[-lines:])


def _crashes(base):
    """Native crashes of the last week: when, and what the crashing thread was doing. native_crash.log gets a marker line at every
    start and Python's fault handler writes the thread dump under it when the process dies."""
    text = _tail(os.path.join(base, "native_crash.log"), 4000)
    found, marker, block = [], "", []
    for ln in text.splitlines() + ["--- Seven started END (pid 0) ---"]:
        if ln.startswith("--- Seven started"):
            if marker and any(x.strip() for x in block):
                found.append((marker, block))
            marker, block = ln.replace("--- Seven started", "").replace("---", "").strip(), []
        else:
            block.append(ln)
    out = []
    for marker, block in found:
        if not _recent(marker):
            continue
        body = [x for x in block if x.strip()]
        start = next((i for i, x in enumerate(body) if "fatal exception" in x.lower()), 0)
        out.append(f"after the start at {marker}:\n" + "\n".join("    " + x for x in body[start:start + 12]))
    exits = []
    for ln in _tail(os.path.join(base, "python_crash.log"), 400).splitlines():
        m = re.search(r"EXIT code=(\d+)", ln)
        if m and _recent(ln):
            code = int(m.group(1))
            exits.append(f"{ln.split(']')[0].lstrip('[')[:19]}: the backend exited with {_EXIT_CODES.get(code, 'code ' + str(code))}")
    return out, exits


def logs_section():
    out = []
    base = os.path.join(_DATA, "logs")
    text = _useful(os.path.join(base, "seven.log"), 25)
    out.append(_c("Seven log: warnings and errors (last 7 days)", WARN if text else OK, text or "none"))
    crashes, exits = _crashes(base)
    out.append(_c("Native crashes (last 7 days)", FAIL if crashes else OK, "\n".join(crashes[-3:]) if crashes else "none recorded"))
    out.append(_c("Backend exits (last 7 days)", WARN if exits else OK, "\n".join(exits[-6:]) if exits else "none"))
    errors = _useful(os.path.join(base, "python_crash.log"), 15)
    out.append(_c("Backend error output (last 7 days)", WARN if errors else OK, errors or "none"))
    return out


SECTIONS = [("Seven", app_section), ("Live state", state_section), ("Safe mode", safe_mode_section),
            ("Microphone", microphone_section), ("Speech recognition", speech_section), ("Hearing right now", hearing_section), ("Voice loop", voice_loop_section),
            ("Voice", voice_section),
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
