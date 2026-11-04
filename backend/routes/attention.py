"""
backend/routes/attention.py
What Seven can't do right now, in words a person can act on.

    GET /api/attention   [{id, level, message, action?: {label, to}}]  most important first; [] when all is well

The home screen shows the first item as a quiet strip under the header and nothing at all when the list is empty.
Without it, a missing microphone or a stopped AI model just looks like Seven ignoring you. The app adds two items of
its own from state it already has (an update is ready, a licence is about to expire).

    error   Seven can't do its main job (the microphone can't be opened)
    warn    part of Seven isn't working (the voice failed to download, the AI model isn't running)
    info    something is on its way (the voice is still downloading)
"""
import socket
import time

from fastapi import APIRouter

router = APIRouter()

OLLAMA_ADDR = ("127.0.0.1", 11434)
SETTLE_SECONDS = 90          # Ollama starts with Seven; don't report it as stopped while everything is still starting


def _mic_error() -> str:
    import sys
    mod = sys.modules.get("ears.stream")             # only if the ears are running; importing would load them
    return getattr(getattr(mod, "STREAM", None), "last_error", "") if mod else ""


def _speech() -> dict:
    """{state, progress, detail} of the speech recognition model, once the ears have been loaded."""
    import sys
    mod = sys.modules.get("ears.core")
    return mod.models_status() if mod and hasattr(mod, "models_status") else {}


def _voice() -> dict:
    """{ready, status, progress} of the natural voice."""
    from mouth import voices
    try:
        from backend.bootstrap import _bootstrap_state
        s = _bootstrap_state.get("voice_model", {})
    except Exception:
        s = {}
    return {"ready": voices.kokoro_ready(), "status": s.get("status", ""), "progress": s.get("progress", 0)}


def _ollama_up() -> bool:
    try:
        with socket.create_connection(OLLAMA_ADDR, timeout=0.3):
            return True
    except OSError:
        return False


def _uptime() -> float:
    from backend.api_server import _start_time
    return time.time() - _start_time


def _setup_done() -> bool:
    try:
        import config
        return bool(config.KEY.get("setup_complete", False))
    except Exception:
        return False


def _problem() -> dict:
    """What the voice loop reported when Seven could not load or start its hearing, and safe mode if it is on."""
    try:
        from backend.api_server import _state
        return {"problem": _state.get("voice_problem") or "", "safe_mode": (_state.get("safe_mode") or {}).get("reason", ""),
                "mic_problem": _state.get("mic_problem") or "", "mic_notice": _state.get("mic_notice") or ""}
    except Exception:
        return {"problem": "", "safe_mode": "", "mic_problem": "", "mic_notice": ""}


def _mic_blocked() -> bool:
    """Windows' privacy switch for desktop apps and the microphone: when it is off, Seven hears silence and says nothing."""
    try:
        import winreg
        sub = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
        for key_path in (sub, sub + r"\NonPackaged"):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    if winreg.QueryValueEx(key, "Value")[0] == "Deny":
                        return True
            except OSError:
                continue
    except Exception:
        pass
    return False


_FIX = {"label": "Run diagnostics", "to": "/settings?section=system"}
# What ears/doctor.py finds that the home screen should show. The others (start-up failures, safe mode, a silent or switched
# microphone) have their own messages above, and a microphone that is merely quiet is shown only in Settings, System, Hearing.
_HOME = {"loop_stuck", "mic_stream", "speaking_stuck", "ptt", "wake_word", "own_voice", "noise", "no_words", "speech_model"}


def _hearing_issues() -> list:
    try:
        from backend.routes import hearing
        return hearing.snapshot()[0]
    except Exception:
        return []


def collect(mic_error=_mic_error, voice=_voice, ollama_up=_ollama_up, uptime=_uptime, setup_done=_setup_done,
            speech=_speech, problem=_problem, mic_blocked=_mic_blocked, hearing=_hearing_issues) -> list:
    """The problems, most important first. The probes are parameters so tests can supply them."""
    if not setup_done():
        return []
    out = []
    try:
        p = problem()
        if p["safe_mode"]:
            out.append({"id": "safe-mode", "level": "error",
                        "message": f"Seven is in safe mode, so it can't hear or think. {p['safe_mode']}",
                        "action": {"label": "Try again", "to": "/settings?section=system", "retry": "safe-mode"}})
        elif p["problem"]:
            out.append({"id": "hearing-failed", "level": "error",
                        "message": f"Seven couldn't start. {p['problem']}", "action": _FIX})
    except Exception:
        pass
    try:
        p = problem()
        if p.get("mic_problem"):
            out.append({"id": "mic-silent", "level": "warn", "message": p["mic_problem"], "action": _FIX})
        elif p.get("mic_notice"):
            out.append({"id": "mic-switched", "level": "info", "message": p["mic_notice"],
                        "action": {"label": "Choose microphone", "to": "/settings?section=voice"}})
    except Exception:
        pass
    try:
        for issue in hearing():
            if issue["id"] in _HOME and issue["level"] in ("error", "warn"):
                out.append({"id": "hearing-" + issue["id"], "level": issue["level"], "message": f"{issue['title']}. {issue['fix']}",
                            "action": {"label": "See why", "to": "/settings?section=system"}})
    except Exception:
        pass
    try:
        if mic_blocked():
            out.append({"id": "mic-blocked", "level": "error",
                        "message": "Windows is blocking microphone access for desktop apps. Turn on Settings, Privacy and security, "
                                   "Microphone, Let desktop apps access your microphone."})
    except Exception:
        pass
    try:
        if mic_error():
            out.append({"id": "mic", "level": "error",
                        "message": "Seven can't use your microphone. It may be unplugged or in use by another app.",
                        "action": {"label": "Choose microphone", "to": "/settings?section=voice"}})
    except Exception:
        pass
    try:
        sp = speech() or {}
        if sp.get("state") in ("downloading", "loading") and sp.get("progress", 0) < 100:
            pct = int(sp.get("progress") or 0)
            out.append({"id": "speech-downloading", "level": "info",
                        "message": f"Seven is getting its speech recognition ready{f', {pct}%' if pct > 1 else ''}. "
                                   "It can't hear you until then; typing works."})
        elif sp.get("state") == "error":
            out.append({"id": "speech-failed", "level": "warn",
                        "message": "Speech recognition couldn't start, so Seven can't hear you. Check your internet connection and restart Seven."})
    except Exception:
        pass
    try:
        v = voice()
        if not v["ready"]:
            if v["status"] == "running":
                pct = int(v["progress"] or 0)
                out.append({"id": "voice-downloading", "level": "info",
                            "message": f"Seven's voice is downloading{f', {pct}%' if pct else ''}. Until then it answers in a basic voice."})
            else:                                    # failed, or never started
                failed = v["status"] == "error"
                out.append({"id": "voice-failed" if failed else "voice-missing", "level": "warn",
                            "message": "Seven's voice couldn't be downloaded. Check your internet connection." if failed
                                       else "Seven's natural voice isn't installed yet, so it answers in a basic voice.",
                            "action": {"label": "Open voice settings", "to": "/settings?section=voice"}})
    except Exception:
        pass
    try:
        if uptime() > SETTLE_SECONDS and not ollama_up():
            out.append({"id": "model", "level": "warn",
                        "message": "The AI model isn't running, so Seven can only do instant commands like opening apps.",
                        "action": {"label": "Open brain settings", "to": "/settings?section=brain"}})
    except Exception:
        pass
    order = {"error": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda x: order[x["level"]])


@router.get("/api/attention", summary="What needs the user's attention",
            description="Problems that stop Seven working properly (microphone, voice, AI model), most important "
                        "first. Empty when everything is fine.")
def get_attention():
    return collect()
